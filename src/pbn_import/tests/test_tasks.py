"""Tests for pbn_import Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession
from pbn_import.tasks import run_pbn_import

# ============================================================================
# run_pbn_import task tests
# ============================================================================


@pytest.mark.django_db
def test_run_pbn_import_session_not_found():
    """Test run_pbn_import handles missing session gracefully."""
    # Task doesn't raise exception, just logs error and returns
    with patch("pbn_import.tasks.logger") as mock_logger:
        run_pbn_import.apply(args=(99999,))

    # Verify the error was logged
    mock_logger.error.assert_called_once_with("Sesja 99999 nie została znaleziona")


@pytest.mark.django_db
def test_run_pbn_import_success(uczelnia, admin_user):
    """Test run_pbn_import completes successfully with mocked dependencies."""
    session = ImportSession.objects.create(
        user=admin_user, status="pending", config={"test": "config"}
    )

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.status == "completed"
    assert session.completed_at is not None

    log = ImportLog.objects.filter(session=session, step="End").first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_marks_running(uczelnia, admin_user):
    """Test run_pbn_import marks session as running."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.task_id is not None


@pytest.mark.django_db
def test_run_pbn_import_handles_no_pbn_client(uczelnia, admin_user):
    """Test run_pbn_import handles case when PBN client cannot be created."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(
            uczelnia, "pbn_client", side_effect=Exception("No PBN config")
        ):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.status == "completed"

    log = ImportLog.objects.filter(
        session=session, step="Setup", level="warning"
    ).first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_failure(uczelnia, admin_user):
    """Test run_pbn_import marks session as failed on error."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.side_effect = Exception("Import failed")

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            with patch("pbn_import.tasks.rollbar"):
                run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.status == "failed"
    assert "Import failed" in session.error_message
    assert session.error_traceback is not None

    log = ImportLog.objects.filter(session=session, level="critical").first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_cancelled(uczelnia, admin_user):
    """Test run_pbn_import respects cancelled status set during import."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    def simulate_cancellation(sess, pbn_client, config, uczelnia=None):
        """Simulate ImportManager that detects cancellation during run."""
        # During run, session gets cancelled (e.g., user cancels via UI)
        sess.status = "cancelled"
        sess.save()
        mock_manager = MagicMock()
        mock_manager.run.return_value = {"success": False}
        return mock_manager

    with patch("pbn_import.tasks.ImportManager", side_effect=simulate_cancellation):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.status == "cancelled"


@pytest.mark.django_db
def test_import_manager_uzywa_swojej_uczelni_nie_get_default(admin_user):
    """Faza 3 (multi-hosted): ImportManager propaguje SWOJĄ uczelnię do
    ``_refresh_pbn_client_after_setup``, zamiast zgadywać ``get_default()``
    (pierwszą-z-brzegu). Failowałby przed Fazą 3."""
    from bpp.models import Uczelnia
    from pbn_api.models import Institution
    from pbn_import.utils.import_manager import ImportManager

    inst1 = baker.make(Institution)
    inst2 = baker.make(Institution)
    baker.make(Uczelnia, pbn_uid=inst1)  # pierwsza-z-brzegu (gdyby ktoś zgadywał)
    u2 = baker.make(Uczelnia, pbn_uid=inst2, pbn_integracja=False)
    # Multi-hosted: są DWIE uczelnie, więc nie ma „jedynej" — ImportManager
    # MUSI użyć swojej (u2), nie zgadywać pierwszej-z-brzegu.
    assert Uczelnia.objects.get_single_uczelnia_or_none() is None

    session = baker.make(ImportSession, user=admin_user, config={})
    manager = ImportManager(session, client=None, uczelnia=u2)
    assert manager.uczelnia == u2

    manager._refresh_pbn_client_after_setup()

    # Użył pbn_uid u2 (inst2), nie get_default()=u1 (inst1).
    assert session.config["uczelnia_pbn_uid"] == inst2.pk


@pytest.mark.django_db
def test_run_pbn_import_failed_result(uczelnia, admin_user):
    """Test run_pbn_import marks session as failed when result has no success."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": False, "error": "Some error"}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    session.refresh_from_db()
    assert session.status == "failed"


@pytest.mark.django_db
def test_run_pbn_import_uses_passed_uczelnia_not_default(admin_user):
    """run_pbn_import MUSI budować klienta z uczelni przekazanej przez
    entrypoint, a NIE z pierwszej-z-brzegu (get_default()).

    Regresja błędu multi-hosted: PBN skonfigurowany w drugiej uczelni,
    a zadanie czytało konfigurację pierwszej -> 403 'token aplikacji null'.
    """
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    # Pierwsza uczelnia (get_default()) — BEZ konfiguracji PBN.
    site1, _ = Site.objects.get_or_create(
        domain="pierwsza.example.com", defaults={"name": "pierwsza"}
    )
    Uczelnia.objects.create(skrot="P1", nazwa="Pierwsza", site=site1)

    # Druga uczelnia — to ją wybiera użytkownik (ma PBN).
    site2, _ = Site.objects.get_or_create(
        domain="druga.example.com", defaults={"name": "druga"}
    )
    uczelnia2 = Uczelnia.objects.create(skrot="P2", nazwa="Druga", site=site2)

    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    recorded_pk = []

    def fake_pbn_client(self, token):
        recorded_pk.append(self.pk)
        return MagicMock()

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(Uczelnia, "pbn_client", fake_pbn_client):
            run_pbn_import.apply(args=(session.pk, uczelnia2.pk))

    assert recorded_pk == [uczelnia2.pk]


@pytest.mark.django_db
def test_run_pbn_import_without_uczelnia_id_does_not_fall_back(admin_user):
    """Bez uczelnia_id zadanie MUSI zakończyć się błędem, a nie po cichu
    użyć pierwszej uczelni (get_default()). To eliminuje wzorzec
    'default institution' z toru w tle."""
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    site1, _ = Site.objects.get_or_create(
        domain="pierwsza.example.com", defaults={"name": "pierwsza"}
    )
    Uczelnia.objects.create(skrot="P1", nazwa="Pierwsza", site=site1)

    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch("pbn_import.tasks.rollbar"):
            # brak uczelnia_id — entrypoint go nie podał
            run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "failed"


@pytest.mark.django_db
def test_run_pbn_import_creates_start_log(uczelnia, admin_user):
    """Test run_pbn_import creates start log entry."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
        with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
            run_pbn_import.apply(args=(session.pk, uczelnia.pk))

    start_log = ImportLog.objects.filter(
        session=session, step="Start", level="info"
    ).first()
    assert start_log is not None
    assert "rozpoczęty" in start_log.message
