from unittest.mock import MagicMock, Mock, patch

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from rozbieznosci_if.models import IgnorujRozbieznoscIf
from rozbieznosci_if.views import (
    CURRENT_YEAR,
    DEFAULT_ROK_OD,
    RozbieznosciView,
    get_base_queryset,
    ustaw_if_ze_zrodla,
)


@pytest.fixture
def wydawnictwo_z_rozbieznoscia(rok):
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, impact_factor=50)

    wydawnictwo_ciagle = baker.make(
        Wydawnictwo_Ciagle, impact_factor=10, rok=rok, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.fixture
def wydawnictwo_bez_rozbieznosci(rok):
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, impact_factor=50)

    wydawnictwo_ciagle = baker.make(
        Wydawnictwo_Ciagle, rok=rok, impact_factor=50, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.fixture
def wydawnictwo_z_rozbieznoscia_rok_2020(db):
    """Fixture for testing year filtering - creates record from 2020."""
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=2020, impact_factor=50)

    wydawnictwo_ciagle = baker.make(
        Wydawnictwo_Ciagle, impact_factor=10, rok=2020, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.fixture
def wydawnictwo_z_rozbieznoscia_rok_2023(db):
    """Fixture for testing year filtering - creates record from 2023."""
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=2023, impact_factor=75)

    wydawnictwo_ciagle = baker.make(
        Wydawnictwo_Ciagle, impact_factor=25, rok=2023, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_tak(wydawnictwo_z_rozbieznoscia):
    res = get_base_queryset()
    assert wydawnictwo_z_rozbieznoscia in res


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_ignorowane(wydawnictwo_z_rozbieznoscia):
    IgnorujRozbieznoscIf.objects.create(object=wydawnictwo_z_rozbieznoscia)
    res = get_base_queryset()
    assert wydawnictwo_z_rozbieznoscia not in res


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_nie(wydawnictwo_bez_rozbieznosci):
    res = get_base_queryset()
    assert wydawnictwo_bez_rozbieznosci not in res


@pytest.mark.django_db
def test_RozbieznosciView_dodaj_do_ignorowanych(
    wydawnictwo_z_rozbieznoscia, rf, admin_user
):
    req = rf.get("/", data={"_ignore": str(wydawnictwo_z_rozbieznoscia.pk)})
    req.user = admin_user
    req._messages = Mock()

    rv = RozbieznosciView(kwargs={}, request=req)

    rv.get(req)
    rv.get(req)
    rv.get(req)

    assert IgnorujRozbieznoscIf.objects.count() == 1


@pytest.mark.django_db
def test_RozbieznosciView_ustaw(wydawnictwo_z_rozbieznoscia, rf, admin_user):
    req = rf.get("/", data={"_set": str(wydawnictwo_z_rozbieznoscia.pk)})
    req.user = admin_user
    req._messages = Mock()

    rv = RozbieznosciView(kwargs={}, request=req)

    rv.get(req)

    wydawnictwo_z_rozbieznoscia.refresh_from_db()
    assert wydawnictwo_z_rozbieznoscia.impact_factor == 50


# Tests for year range filtering


@pytest.mark.django_db
def test_RozbieznosciView_filter_by_year_range(
    wydawnictwo_z_rozbieznoscia_rok_2020,
    wydawnictwo_z_rozbieznoscia_rok_2023,
    rf,
    admin_user,
):
    """Test filtering by year range."""
    # Filter for 2022-2024, should include 2023 but not 2020
    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2024"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    queryset = rv.get_queryset()

    assert wydawnictwo_z_rozbieznoscia_rok_2023 in queryset
    assert wydawnictwo_z_rozbieznoscia_rok_2020 not in queryset


@pytest.mark.django_db
def test_RozbieznosciView_filter_includes_2020(
    wydawnictwo_z_rozbieznoscia_rok_2020,
    wydawnictwo_z_rozbieznoscia_rok_2023,
    rf,
    admin_user,
):
    """Test filtering that includes older records."""
    # Filter for 2019-2021, should include 2020 but not 2023
    req = rf.get("/", data={"rok_od": "2019", "rok_do": "2021"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    queryset = rv.get_queryset()

    assert wydawnictwo_z_rozbieznoscia_rok_2020 in queryset
    assert wydawnictwo_z_rozbieznoscia_rok_2023 not in queryset


@pytest.mark.django_db
def test_RozbieznosciView_default_year_filter(rf, admin_user):
    """Test that default year filter is applied (2022 to current year)."""
    req = rf.get("/")
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    rok_od, rok_do, tytul, sort = rv.get_filter_params()

    assert rok_od == DEFAULT_ROK_OD
    assert rok_do == CURRENT_YEAR
    assert tytul == ""


@pytest.mark.django_db
def test_RozbieznosciView_filter_by_title(db, rf, admin_user):
    """Test filtering by title."""
    # Create two records with different titles
    zrodlo1 = baker.make(Zrodlo)
    zrodlo1.punktacja_zrodla_set.create(rok=2023, impact_factor=50)
    wc1 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Unique Title ABC",
        impact_factor=10,
        rok=2023,
        zrodlo=zrodlo1,
    )

    zrodlo2 = baker.make(Zrodlo)
    zrodlo2.punktacja_zrodla_set.create(rok=2023, impact_factor=60)
    wc2 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Different XYZ",
        impact_factor=20,
        rok=2023,
        zrodlo=zrodlo2,
    )

    # Filter by "Unique"
    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2025", "tytul": "Unique"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    queryset = rv.get_queryset()

    assert wc1 in queryset
    assert wc2 not in queryset


# Tests for sorting


@pytest.mark.django_db
def test_RozbieznosciView_sort_by_rok_asc(
    wydawnictwo_z_rozbieznoscia_rok_2020,
    wydawnictwo_z_rozbieznoscia_rok_2023,
    rf,
    admin_user,
):
    """Test sorting by year ascending."""
    req = rf.get("/", data={"rok_od": "2019", "rok_do": "2025", "sort": "rok"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    queryset = list(rv.get_queryset())

    # 2020 should come before 2023
    idx_2020 = queryset.index(wydawnictwo_z_rozbieznoscia_rok_2020)
    idx_2023 = queryset.index(wydawnictwo_z_rozbieznoscia_rok_2023)
    assert idx_2020 < idx_2023


@pytest.mark.django_db
def test_RozbieznosciView_sort_by_rok_desc(
    wydawnictwo_z_rozbieznoscia_rok_2020,
    wydawnictwo_z_rozbieznoscia_rok_2023,
    rf,
    admin_user,
):
    """Test sorting by year descending."""
    req = rf.get("/", data={"rok_od": "2019", "rok_do": "2025", "sort": "-rok"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    queryset = list(rv.get_queryset())

    # 2023 should come before 2020
    idx_2020 = queryset.index(wydawnictwo_z_rozbieznoscia_rok_2020)
    idx_2023 = queryset.index(wydawnictwo_z_rozbieznoscia_rok_2023)
    assert idx_2023 < idx_2020


@pytest.mark.django_db
def test_RozbieznosciView_invalid_sort_uses_default(rf, admin_user):
    """Test that invalid sort parameter falls back to default."""
    req = rf.get("/", data={"sort": "invalid_field"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    rok_od, rok_do, tytul, sort = rv.get_filter_params()

    assert sort == "-ostatnio_zmieniony"


# Tests for XLSX export


@pytest.mark.django_db
def test_RozbieznosciExportView(wydawnictwo_z_rozbieznoscia_rok_2023, rf, admin_user):
    """Test XLSX export returns correct content type."""
    from rozbieznosci_if.views import RozbieznosciExportView

    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2025"})
    req.user = admin_user

    view = RozbieznosciExportView()
    view.request = req
    response = view.get(req)

    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        'attachment; filename="rozbieznosci_if_2022_2025.xlsx"'
        in response["Content-Disposition"]
    )


# Tests for bulk update


@pytest.mark.django_db
def test_ustaw_if_ze_zrodla_single(wydawnictwo_z_rozbieznoscia):
    """Test updating IF for a single publication."""
    pk = wydawnictwo_z_rozbieznoscia.pk
    updated, errors = ustaw_if_ze_zrodla([pk])

    wydawnictwo_z_rozbieznoscia.refresh_from_db()

    assert updated == 1
    assert errors == 0
    assert wydawnictwo_z_rozbieznoscia.impact_factor == 50


@pytest.mark.django_db
def test_ustaw_if_ze_zrodla_multiple(
    wydawnictwo_z_rozbieznoscia_rok_2020,
    wydawnictwo_z_rozbieznoscia_rok_2023,
):
    """Test updating IF for multiple publications."""
    pks = [
        wydawnictwo_z_rozbieznoscia_rok_2020.pk,
        wydawnictwo_z_rozbieznoscia_rok_2023.pk,
    ]
    updated, errors = ustaw_if_ze_zrodla(pks)

    wydawnictwo_z_rozbieznoscia_rok_2020.refresh_from_db()
    wydawnictwo_z_rozbieznoscia_rok_2023.refresh_from_db()

    assert updated == 2
    assert errors == 0
    assert wydawnictwo_z_rozbieznoscia_rok_2020.impact_factor == 50
    assert wydawnictwo_z_rozbieznoscia_rok_2023.impact_factor == 75


@pytest.mark.django_db
def test_ustaw_if_ze_zrodla_nonexistent():
    """Test updating IF for nonexistent publication."""
    updated, errors = ustaw_if_ze_zrodla([999999])

    assert updated == 0
    assert errors == 1


@pytest.mark.django_db
def test_UstawWszystkieView_small_batch(
    wydawnictwo_z_rozbieznoscia_rok_2023, rf, admin_user
):
    """Test bulk update with small batch (direct execution)."""
    from rozbieznosci_if.views import UstawWszystkieView

    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2025"})
    req.user = admin_user
    req._messages = Mock()

    view = UstawWszystkieView()
    view.request = req
    response = view.get(req)

    wydawnictwo_z_rozbieznoscia_rok_2023.refresh_from_db()

    assert response.status_code == 302  # Redirect
    assert wydawnictwo_z_rozbieznoscia_rok_2023.impact_factor == 75


@pytest.mark.django_db
def test_UstawWszystkieView_large_batch_triggers_celery(rf, admin_user):
    """Test bulk update with large batch (Celery task)."""
    from rozbieznosci_if.views import (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
        UstawWszystkieView,
    )

    # Create many records to trigger Celery
    for i in range(OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE + 5):
        zrodlo = baker.make(Zrodlo)
        zrodlo.punktacja_zrodla_set.create(rok=2023, impact_factor=100 + i)
        baker.make(Wydawnictwo_Ciagle, impact_factor=10 + i, rok=2023, zrodlo=zrodlo)

    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2025"})
    req.user = admin_user
    req._messages = Mock()

    view = UstawWszystkieView()
    view.request = req

    with patch("rozbieznosci_if.tasks.task_ustaw_if_ze_zrodla") as mock_task:
        mock_task_result = MagicMock()
        mock_task_result.id = "test-task-id"
        mock_task.delay.return_value = mock_task_result
        response = view.get(req)

    assert response.status_code == 302  # Redirect to status page
    assert "task-status" in response.url
    mock_task.delay.assert_called_once()


@pytest.mark.django_db
def test_UstawWszystkieView_no_records(rf, admin_user):
    """Test bulk update with no matching records."""
    from rozbieznosci_if.views import UstawWszystkieView

    req = rf.get("/", data={"rok_od": "1900", "rok_do": "1901"})
    req.user = admin_user
    req._messages = Mock()

    view = UstawWszystkieView()
    view.request = req
    response = view.get(req)

    assert response.status_code == 302  # Redirect


# Tests for context data


@pytest.mark.django_db
def test_RozbieznosciView_context_data(rf, admin_user):
    """Test that context contains required data."""
    req = rf.get("/", data={"rok_od": "2020", "rok_do": "2024", "sort": "rok"})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.request = req
    rv.object_list = rv.get_queryset()
    context = rv.get_context_data()

    assert context["rok_od"] == 2020
    assert context["rok_do"] == 2024
    assert context["current_sort"] == "rok"
    assert "filter_query_string" in context


@pytest.mark.django_db
def test_task_ustaw_if_ze_zrodla(wydawnictwo_z_rozbieznoscia_rok_2023, admin_user):
    """Test Celery task for 'ustaw IF'."""
    from rozbieznosci_if.tasks import task_ustaw_if_ze_zrodla

    pk = wydawnictwo_z_rozbieznoscia_rok_2023.pk

    # Use .apply() to run task with proper Celery context
    result = task_ustaw_if_ze_zrodla.apply(
        args=([pk],), kwargs={"user_id": admin_user.id}
    ).result

    # Check result
    assert result["updated"] == 1
    assert result["errors"] == 0

    # Check IF was updated
    wydawnictwo_z_rozbieznoscia_rok_2023.refresh_from_db()
    assert wydawnictwo_z_rozbieznoscia_rok_2023.impact_factor == 75


@pytest.mark.django_db
def test_task_ustaw_if_ze_zrodla_creates_log(
    wydawnictwo_z_rozbieznoscia_rok_2023, admin_user
):
    """Test that Celery task creates log entries with user."""
    from rozbieznosci_if.models import RozbieznosciIfLog
    from rozbieznosci_if.tasks import task_ustaw_if_ze_zrodla

    pk = wydawnictwo_z_rozbieznoscia_rok_2023.pk
    old_if = wydawnictwo_z_rozbieznoscia_rok_2023.impact_factor

    # Use .apply() to run task with proper Celery context
    task_ustaw_if_ze_zrodla.apply(args=([pk],), kwargs={"user_id": admin_user.id})

    # Check log was created with correct user
    log = RozbieznosciIfLog.objects.filter(rekord_id=pk).first()
    assert log is not None
    assert log.if_before == old_if
    assert log.if_after == 75
    assert log.user == admin_user


# Tests for RozbieznosciIfLog


@pytest.mark.django_db
def test_RozbieznosciView_ustaw_creates_log(
    wydawnictwo_z_rozbieznoscia_rok_2023, rf, admin_user
):
    """Test that _set action creates a log entry."""
    from rozbieznosci_if.models import RozbieznosciIfLog

    pk = wydawnictwo_z_rozbieznoscia_rok_2023.pk
    old_if = wydawnictwo_z_rozbieznoscia_rok_2023.impact_factor

    req = rf.get("/", data={"_set": str(pk)})
    req.user = admin_user
    req._messages = Mock()

    rv = RozbieznosciView(kwargs={}, request=req)
    rv.get(req)

    # Check log was created
    log = RozbieznosciIfLog.objects.filter(rekord_id=pk).first()
    assert log is not None
    assert log.if_before == old_if
    assert log.if_after == 75
    assert log.user == admin_user
    assert log.zrodlo == wydawnictwo_z_rozbieznoscia_rok_2023.zrodlo


@pytest.mark.django_db
def test_RozbieznosciIfLog_admin_readonly(admin_client):
    """Test that RozbieznosciIfLog admin is read-only."""
    from django.urls import reverse

    # Try to access add page - should redirect or return 403
    add_url = reverse("admin:rozbieznosci_if_rozbieznosciiflog_add")
    response = admin_client.get(add_url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_RozbieznosciIfLog_str(wydawnictwo_z_rozbieznoscia_rok_2023, admin_user):
    """Test RozbieznosciIfLog __str__ method."""
    from rozbieznosci_if.models import RozbieznosciIfLog

    log = RozbieznosciIfLog.objects.create(
        rekord=wydawnictwo_z_rozbieznoscia_rok_2023,
        zrodlo=wydawnictwo_z_rozbieznoscia_rok_2023.zrodlo,
        if_before=10,
        if_after=50,
        user=admin_user,
    )

    assert "10" in str(log)
    assert "50" in str(log)


# Tests for TaskStatusView and progress tracking


@pytest.mark.django_db
def test_TaskStatusView_in_progress(client, admin_user):
    """Test TaskStatusView returns progress page when task is running."""
    client.force_login(admin_user)

    with patch("rozbieznosci_if.views.AsyncResult") as mock_result:
        mock_task = MagicMock()
        mock_task.ready.return_value = False
        mock_task.info = {
            "current": 5,
            "total": 10,
            "updated": 3,
            "errors": 0,
            "progress": 50,
        }
        mock_result.return_value = mock_task

        response = client.get("/rozbieznosci_if/task-status/test-task-123/")

        assert response.status_code == 200
        assert b"Zadanie w trakcie wykonywania" in response.content


@pytest.mark.django_db
def test_TaskStatusView_htmx_returns_partial(client, admin_user):
    """Test TaskStatusView returns partial for HTMX request."""
    client.force_login(admin_user)

    with patch("rozbieznosci_if.views.AsyncResult") as mock_result:
        mock_task = MagicMock()
        mock_task.ready.return_value = False
        mock_task.info = {"current": 5, "total": 10, "progress": 50}
        mock_result.return_value = mock_task

        response = client.get(
            "/rozbieznosci_if/task-status/test-task-123/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        # HTMX partial should not include full page structure
        assert b"<html" not in response.content
        assert b"Zadanie w trakcie wykonywania" in response.content


@pytest.mark.django_db
def test_TaskStatusView_completed_redirects(rf, admin_user):
    """Test TaskStatusView redirects when task is completed."""
    from rozbieznosci_if.views import TaskStatusView

    req = rf.get("/")
    req.user = admin_user
    req._messages = Mock()

    with patch("rozbieznosci_if.views.AsyncResult") as mock_result:
        mock_task = MagicMock()
        mock_task.ready.return_value = True
        mock_task.failed.return_value = False
        mock_task.successful.return_value = True
        mock_task.result = {"updated": 10, "errors": 0, "total": 10}
        mock_result.return_value = mock_task

        view = TaskStatusView()
        view.request = req
        response = view.get(req, task_id="test-task-123")

        assert response.status_code == 302
        assert "index" in response.url


@pytest.mark.django_db
def test_TaskStatusView_htmx_completed_uses_hx_redirect(rf, admin_user):
    """Test TaskStatusView uses HX-Redirect header for HTMX on completion."""
    from rozbieznosci_if.views import TaskStatusView

    req = rf.get("/", HTTP_HX_REQUEST="true")
    req.user = admin_user
    req._messages = Mock()

    with patch("rozbieznosci_if.views.AsyncResult") as mock_result:
        mock_task = MagicMock()
        mock_task.ready.return_value = True
        mock_task.failed.return_value = False
        mock_task.successful.return_value = True
        mock_task.result = {"updated": 10, "errors": 0, "total": 10}
        mock_result.return_value = mock_task

        view = TaskStatusView()
        view.request = req
        response = view.get(req, task_id="test-task-123")

        assert response.status_code == 200
        assert "HX-Redirect" in response


@pytest.mark.django_db
def test_TaskStatusView_failed_shows_error(client, admin_user):
    """Test TaskStatusView shows error when task failed."""
    client.force_login(admin_user)

    with patch("rozbieznosci_if.views.AsyncResult") as mock_result:
        mock_task = MagicMock()
        mock_task.ready.return_value = True
        mock_task.failed.return_value = True
        mock_task.info = "Task failed: some error"
        mock_result.return_value = mock_task

        response = client.get("/rozbieznosci_if/task-status/test-task-123/")

        assert response.status_code == 200
        assert b"Wystapil blad" in response.content
        assert b"Task failed: some error" in response.content


@pytest.mark.django_db
def test_UstawWszystkieView_large_batch_redirects_to_status(rf, admin_user):
    """Test that large batch redirects to task status page."""
    from rozbieznosci_if.views import (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
        UstawWszystkieView,
    )

    # Create many records to trigger Celery
    for i in range(OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE + 5):
        zrodlo = baker.make(Zrodlo)
        zrodlo.punktacja_zrodla_set.create(rok=2023, impact_factor=100 + i)
        baker.make(Wydawnictwo_Ciagle, impact_factor=10 + i, rok=2023, zrodlo=zrodlo)

    req = rf.get("/", data={"rok_od": "2022", "rok_do": "2025"})
    req.user = admin_user
    req._messages = Mock()

    view = UstawWszystkieView()
    view.request = req

    with patch("rozbieznosci_if.tasks.task_ustaw_if_ze_zrodla") as mock_task:
        mock_task_result = MagicMock()
        mock_task_result.id = "test-task-123"
        mock_task.delay.return_value = mock_task_result
        response = view.get(req)

    assert response.status_code == 302
    assert "task-status" in response.url
    assert "test-task-123" in response.url
