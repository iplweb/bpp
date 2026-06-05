"""Testy orkiestratora importu (``ImportManager``).

Pokrywają logikę decyzyjną, która wcześniej była prawie nietknięta testami
(plik na ~21% pokrycia): autoryzacja PBN, pomijanie kroków bez autoryzacji,
ekstrakcja komunikatów błędów, anulowanie oraz pełny przebieg ``run()`` na
lekkich krokach-atrapach (bez prawdziwych wywołań PBN).
"""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.import_manager import ImportManager


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, status="pending", config={})


def make_manager(session, client, **kwargs):
    """ImportManager z pominięciem realnego sprawdzania autoryzacji w __init__.

    __init__ woła ``_check_pbn_authorization`` (uderza w klienta) — w testach
    chcemy kontrolować ``pbn_authorized`` ręcznie, więc patchujemy tę metodę
    na czas konstrukcji.
    """
    with patch.object(ImportManager, "_check_pbn_authorization"):
        return ImportManager(session, client, **kwargs)


# ---------------------------------------------------------------------------
# Atrapy kroków: instancjonowane przez orkiestrator jak prawdziwe step-klasy
# (session=, client=, uczelnia=, **args), wołane jako callable.
# ---------------------------------------------------------------------------


class _SuccessStep:
    def __init__(self, session, client, uczelnia=None, **kwargs):
        self.session = session

    def __call__(self):
        return {"ok": True}


class _RaisingStep:
    def __init__(self, session, client, uczelnia=None, **kwargs):
        self.session = session

    def __call__(self):
        raise ValueError("krok się wywalił")


def step_cfg(klass, name="zrodla", display="Źródła", required=False):
    return {
        "name": name,
        "display": display,
        "class": klass,
        "args": {},
        "required": required,
    }


# ===========================================================================
# _check_pbn_authorization
# ===========================================================================


def test_no_client_means_unauthorized(session):
    manager = ImportManager(session, client=None)

    assert manager.pbn_authorized is False
    assert manager.pbn_error_message == "Brak konfiguracji klienta PBN"


def test_working_client_means_authorized(session):
    client = MagicMock()
    client.get_languages.return_value = ["pol", "eng"]

    manager = ImportManager(session, client=client)

    assert manager.pbn_authorized is True
    client.get_languages.assert_called_once()


def test_failing_client_means_unauthorized_with_message(session):
    client = MagicMock()
    client.get_languages.side_effect = RuntimeError("token wygasł")

    manager = ImportManager(session, client=client)

    assert manager.pbn_authorized is False
    assert "token wygasł" in manager.pbn_error_message


# ===========================================================================
# _extract_error_message
# ===========================================================================


def test_extract_error_message_prefers_json_description(session):
    manager = make_manager(session, client=None)
    exc = MagicMock()
    exc.content = '{"description": "opis błędu", "message": "msg"}'

    assert manager._extract_error_message(exc) == "opis błędu"


def test_extract_error_message_falls_back_to_json_message(session):
    manager = make_manager(session, client=None)
    exc = MagicMock()
    exc.content = '{"message": "tylko message"}'

    assert manager._extract_error_message(exc) == "tylko message"


def test_extract_error_message_raw_content_when_not_json(session):
    manager = make_manager(session, client=None)
    exc = MagicMock()
    exc.content = "zwykły tekst, nie JSON"

    assert manager._extract_error_message(exc) == "zwykły tekst, nie JSON"


def test_extract_error_message_plain_exception(session):
    manager = make_manager(session, client=None)

    assert manager._extract_error_message(ValueError("boom")) == "boom"


# ===========================================================================
# _validate_pbn_authorization
# ===========================================================================


def test_validate_raises_when_pbn_needed_but_unauthorized(session):
    manager = make_manager(session, client=None)
    manager.pbn_authorized = False
    manager.pbn_error_message = "brak tokenu"
    manager.steps = [step_cfg(_SuccessStep, name="zrodla")]

    with pytest.raises(Exception, match="brak tokenu"):
        manager._validate_pbn_authorization()

    assert ImportLog.objects.filter(
        session=session, level="critical", step="Authorization Check"
    ).exists()


def test_validate_passes_for_setup_only_steps_without_auth(session):
    manager = make_manager(session, client=None)
    manager.pbn_authorized = False
    manager.steps = [
        step_cfg(_SuccessStep, name="initial_setup"),
        step_cfg(_SuccessStep, name="institution_setup"),
    ]

    # Kroki konfiguracyjne nie wymagają PBN — brak wyjątku.
    manager._validate_pbn_authorization()


# ===========================================================================
# _should_skip_step
# ===========================================================================


def test_should_skip_non_setup_step_when_unauthorized(session):
    manager = make_manager(session, client=None)
    manager.pbn_authorized = False
    results = {}

    assert manager._should_skip_step(step_cfg(_SuccessStep, name="zrodla"), results)
    assert results["zrodla"]["skipped"] is True


@pytest.mark.parametrize("step_name", ["initial_setup", "institution_setup"])
def test_setup_steps_not_skipped_when_unauthorized(session, step_name):
    manager = make_manager(session, client=None)
    manager.pbn_authorized = False

    assert not manager._should_skip_step(step_cfg(_SuccessStep, name=step_name), {})


def test_no_step_skipped_when_authorized(session):
    manager = make_manager(session, client=None)
    manager.pbn_authorized = True

    assert not manager._should_skip_step(step_cfg(_SuccessStep, name="zrodla"), {})


# ===========================================================================
# _has_error_logs
# ===========================================================================


def test_has_error_logs_detects_error_and_critical(session):
    manager = make_manager(session, client=None)
    assert manager._has_error_logs() is False

    baker.make(ImportLog, session=session, level="info")
    assert manager._has_error_logs() is False

    baker.make(ImportLog, session=session, level="error")
    assert manager._has_error_logs() is True


# ===========================================================================
# run() — pełne przebiegi na atrapach kroków
# ===========================================================================


@patch.object(ImportManager, "_run_post_import_commands")
def test_run_happy_path_marks_completed(_post, session):
    manager = make_manager(session, client=MagicMock())
    manager.pbn_authorized = True
    manager.steps = [step_cfg(_SuccessStep, name="zrodla")]

    result = manager.run()

    assert result["success"] is True
    assert result["results"]["zrodla"] == {"ok": True}
    session.refresh_from_db()
    assert session.status == "completed"


@patch.object(ImportManager, "_run_post_import_commands")
def test_run_cancelled_before_steps_does_not_execute(_post, session):
    manager = make_manager(session, client=MagicMock())
    manager.pbn_authorized = True
    manager.steps = [step_cfg(_SuccessStep, name="zrodla")]

    # Symuluj anulowanie przez użytkownika W TRAKCIE startu importu: run() sam
    # ustawia status="running" i zapisuje, więc cancel musi trafić do bazy PO
    # tym zapisie, a PRZED pętlą kroków. _validate_pbn_authorization biegnie
    # dokładnie w tym oknie — używamy go jako punktu wstrzyknięcia. Pierwsze
    # _check_cancellation (refresh_from_db) zobaczy "cancelled".
    def cancel_in_db():
        ImportSession.objects.filter(pk=session.pk).update(status="cancelled")

    with patch.object(manager, "_validate_pbn_authorization", side_effect=cancel_in_db):
        result = manager.run()

    assert result["cancelled"] is True
    assert result["success"] is False
    assert "zrodla" not in result["results"]


@patch("pbn_import.utils.import_manager.rollbar")
@patch.object(ImportManager, "_run_post_import_commands")
def test_run_required_step_error_marks_failed(_post, _rollbar, session):
    manager = make_manager(session, client=MagicMock())
    manager.pbn_authorized = True
    manager.steps = [step_cfg(_RaisingStep, name="zrodla", required=True)]

    result = manager.run()

    assert result["success"] is False
    assert "krok się wywalił" in result["message"]
    session.refresh_from_db()
    assert session.status == "failed"


# ===========================================================================
# pause / resume / cancel
# ===========================================================================


def test_pause_resume_cancel_set_status(session):
    manager = make_manager(session, client=None)

    manager.pause()
    session.refresh_from_db()
    assert session.status == "paused"

    manager.resume()
    session.refresh_from_db()
    assert session.status == "running"

    manager.cancel()
    session.refresh_from_db()
    assert session.status == "cancelled"
    assert session.completed_at is not None
