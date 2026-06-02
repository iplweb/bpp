"""Task function tests for pbn_wysylka_oswiadczen app."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from bpp.models import Uczelnia, Wydawnictwo_Ciagle
from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask
from pbn_wysylka_oswiadczen.queries import get_publications_queryset
from pbn_wysylka_oswiadczen.tasks import (
    _delete_existing_statements,
    _handle_http_400_error,
    _send_statements_with_retry,
    get_pbn_client,
    process_single_publication,
)

User = get_user_model()


@pytest.mark.django_db
def test_get_publications_queryset_empty(uczelnia):
    """Test get_publications_queryset returns empty when no matching publications."""
    ciagle_qs, zwarte_qs = get_publications_queryset(rok_od=2022, rok_do=2025)
    assert ciagle_qs.count() == 0
    assert zwarte_qs.count() == 0


@pytest.mark.django_db
def test_get_pbn_client_no_token():
    """Test get_pbn_client raises error when user has no token."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = None

    user.get_pbn_user = lambda: MockPbnUser()

    with pytest.raises(ValueError) as exc_info:
        get_pbn_client(user, 1)

    assert "tokenu" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_get_pbn_client_expired_token():
    """Test get_pbn_client raises error when token is expired."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "some-token"

        def pbn_token_possibly_valid(self):
            return False

    user.get_pbn_user = lambda: MockPbnUser()

    with pytest.raises(ValueError) as exc_info:
        get_pbn_client(user, 1)

    assert "wygasl" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_get_pbn_client_unknown_uczelnia_id():
    """Nieistniejące uczelnia_id => Uczelnia.DoesNotExist (bez fallbacku)."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    user.get_pbn_user = lambda: MockPbnUser()

    with pytest.raises(Uczelnia.DoesNotExist):
        get_pbn_client(user, 999999)


@pytest.mark.django_db
def test_get_pbn_client_requires_uczelnia_id(uczelnia):
    """Bez uczelnia_id get_pbn_client rzuca (brak fallbacku do get_default)."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    user.get_pbn_user = lambda: MockPbnUser()

    with pytest.raises(ValueError) as exc_info:
        get_pbn_client(user, None)

    assert "uczelni" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_get_pbn_client_uses_passed_uczelnia(uczelnia):
    """get_pbn_client buduje klienta z PRZEKAZANEJ uczelni (po id),
    przez kanoniczną Uczelnia.pbn_client()."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    user.get_pbn_user = lambda: MockPbnUser()

    uczelnia.pbn_app_name = "APP"
    uczelnia.pbn_app_token = "TOK"
    uczelnia.pbn_api_root = "https://x.example/"
    uczelnia.save()

    recorded = []

    def fake_pbn_client(self, token):
        recorded.append(self.pk)
        return MagicMock()

    with patch.object(Uczelnia, "pbn_client", fake_pbn_client):
        client = get_pbn_client(user, uczelnia.pk)

    assert client is not None
    assert recorded == [uczelnia.pk]


@pytest.mark.django_db
def test_start_task_view_passes_uczelnia_id(uczelnia):
    """Entrypoint wysyłki oświadczeń MUSI przekazać id uczelni do zadania."""
    from django.contrib.auth.models import Group
    from django.test import RequestFactory

    from bpp.const import GR_WPROWADZANIE_DANYCH
    from pbn_wysylka_oswiadczen.views import StartTaskView

    request = RequestFactory().post("/start/", {"rok_od": "2022", "rok_do": "2025"})
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    pbn_user = MagicMock()
    pbn_user.pbn_token = "valid-token"
    pbn_user.pbn_token_possibly_valid.return_value = True
    user.get_pbn_user = lambda: pbn_user

    with patch(
        "pbn_wysylka_oswiadczen.views.wysylka_oswiadczen_task"
    ) as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-123")
        StartTaskView().post(request)

    mock_task.delay.assert_called_once()
    call = mock_task.delay.call_args
    passed = call.kwargs.get("uczelnia_id")
    if passed is None and len(call.args) > 1:
        passed = call.args[1]
    assert passed == uczelnia.pk


@pytest.mark.django_db
def test_delete_existing_statements_cannot_delete():
    """Test _delete_existing_statements handles CannotDeleteStatementsException."""
    from pbn_api.exceptions import CannotDeleteStatementsException

    mock_client = MagicMock()
    mock_client.delete_all_publication_statements.side_effect = (
        CannotDeleteStatementsException("Test")
    )

    mock_publication = MagicMock()
    mock_publication.pbn_uid_id = "test-uid"

    mock_log_entry = MagicMock()

    # Should not raise exception
    _delete_existing_statements(mock_publication, mock_client, mock_log_entry)

    # Log entry should not have error message set (CannotDelete is OK)
    assert mock_log_entry.error_message != "Blad usuwania oswiadczen"


@pytest.mark.django_db
def test_delete_existing_statements_http_error():
    """Test _delete_existing_statements handles HttpException."""
    from pbn_api.exceptions import HttpException

    mock_client = MagicMock()
    mock_client.delete_all_publication_statements.side_effect = HttpException(
        500, "http://test/", "Server Error"
    )

    mock_publication = MagicMock()
    mock_publication.pbn_uid_id = "test-uid"

    mock_log_entry = MagicMock()
    mock_log_entry.error_message = ""

    _delete_existing_statements(mock_publication, mock_client, mock_log_entry)

    # Error message should be set
    assert "Blad usuwania" in mock_log_entry.error_message


@pytest.mark.django_db
def test_delete_existing_statements_prace_serwisowe():
    """Test _delete_existing_statements re-raises PraceSerwisoweException."""
    from pbn_api.exceptions import PraceSerwisoweException

    mock_client = MagicMock()
    mock_client.delete_all_publication_statements.side_effect = PraceSerwisoweException(
        "Prace serwisowe"
    )

    mock_publication = MagicMock()
    mock_publication.pbn_uid_id = "test-uid"

    mock_log_entry = MagicMock()

    with pytest.raises(PraceSerwisoweException):
        _delete_existing_statements(mock_publication, mock_client, mock_log_entry)


@pytest.mark.django_db
def test_handle_http_400_error():
    """Test _handle_http_400_error function."""
    from pbn_api.exceptions import HttpException

    mock_log_entry = MagicMock()

    error = HttpException(400, "http://test/", '{"error": "Bad Request"}')

    status, log = _handle_http_400_error(error, mock_log_entry)

    assert status == "error"
    assert mock_log_entry.json_response == {"error": "Bad Request"}
    assert "HTTP 400" in mock_log_entry.error_message
    mock_log_entry.save.assert_called_once()


@pytest.mark.django_db
def test_handle_http_400_error_invalid_json():
    """Test _handle_http_400_error with invalid JSON response."""
    from pbn_api.exceptions import HttpException

    mock_log_entry = MagicMock()

    error = HttpException(400, "http://test/", "Invalid response - not JSON")

    status, log = _handle_http_400_error(error, mock_log_entry)

    assert status == "error"
    assert "raw_error" in mock_log_entry.json_response


@pytest.mark.django_db
def test_send_statements_with_retry_success():
    """Test _send_statements_with_retry succeeds on first try."""
    mock_client = MagicMock()
    mock_client.post_discipline_statements.return_value = {"status": "ok"}

    mock_log_entry = MagicMock()
    json_data = {"test": "data"}

    status, log = _send_statements_with_retry(mock_client, json_data, mock_log_entry)

    assert status == "success"
    assert mock_log_entry.status == "success"
    assert mock_log_entry.retry_count == 0
    mock_log_entry.save.assert_called_once()


@pytest.mark.django_db
def test_send_statements_with_retry_500_error():
    """Test _send_statements_with_retry retries on HTTP 500."""
    from pbn_api.exceptions import HttpException

    mock_client = MagicMock()
    # Fail twice with 500, then succeed
    mock_client.post_discipline_statements.side_effect = [
        HttpException(500, "http://test/", "Server Error"),
        HttpException(500, "http://test/", "Server Error"),
        {"status": "ok"},
    ]

    mock_log_entry = MagicMock()
    json_data = {"test": "data"}

    with patch("pbn_wysylka_oswiadczen.tasks.time.sleep"):
        status, log = _send_statements_with_retry(
            mock_client, json_data, mock_log_entry
        )

    assert status == "success"
    assert mock_client.post_discipline_statements.call_count == 3


@pytest.mark.django_db
def test_send_statements_with_retry_exhausted():
    """Test _send_statements_with_retry exhausts all retries."""
    from pbn_api.exceptions import HttpException

    mock_client = MagicMock()
    mock_client.post_discipline_statements.side_effect = HttpException(
        500, "http://test/", "Server Error"
    )

    mock_log_entry = MagicMock()
    json_data = {"test": "data"}

    with patch("pbn_wysylka_oswiadczen.tasks.time.sleep"):
        status, log = _send_statements_with_retry(
            mock_client, json_data, mock_log_entry
        )

    assert status == "error"
    assert "Wszystkie proby nieudane" in mock_log_entry.error_message
    assert mock_client.post_discipline_statements.call_count == 5


@pytest.mark.django_db
def test_send_statements_with_retry_prace_serwisowe():
    """Test _send_statements_with_retry raises PraceSerwisoweException."""
    from pbn_api.exceptions import PraceSerwisoweException

    mock_client = MagicMock()
    mock_client.post_discipline_statements.side_effect = PraceSerwisoweException(
        "Prace serwisowe"
    )

    mock_log_entry = MagicMock()
    json_data = {"test": "data"}

    with pytest.raises(PraceSerwisoweException):
        _send_statements_with_retry(mock_client, json_data, mock_log_entry)

    # Check that log entry was updated before re-raising
    assert mock_log_entry.status == "maintenance"
    assert "Prace serwisowe" in mock_log_entry.error_message
    mock_log_entry.save.assert_called_once()


@pytest.mark.django_db
def test_process_single_publication_no_przypiete_returns_synchronized():
    """Test process_single_publication returns synchronized when no przypiete authors."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnWysylkaOswiadczenTask.objects.create(user=user)

    # Create mock publication with no przypiete authors
    mock_publication = MagicMock()
    mock_publication.pk = 1
    mock_publication.pbn_uid_id = "test-pbn-uid-123"
    mock_publication.tytul_oryginalny = "Test Publication"

    # Mock autorzy_set to return False for przypieta=True filter
    mock_autorzy_set = MagicMock()
    mock_autorzy_set.filter.return_value.exists.return_value = False
    mock_publication.autorzy_set = mock_autorzy_set

    mock_client = MagicMock()

    # Mock ContentType.objects.get_for_model to return a real ContentType
    mock_content_type = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    with patch(
        "django.contrib.contenttypes.models.ContentType.objects.get_for_model",
        return_value=mock_content_type,
    ):
        status, log_entry = process_single_publication(
            mock_publication, mock_client, task, PbnWysylkaLog
        )

    assert status == "synchronized"
    assert log_entry.status == "synchronized"
    assert "przypieta" in log_entry.error_message.lower()
    assert "skasowane" in log_entry.error_message.lower()
