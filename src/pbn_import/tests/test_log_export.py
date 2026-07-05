"""Testy symulowanego „raw logu" tekstowego sesji importu (``log_export``)."""

import datetime

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.log_export import render_session_log_text


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, status="completed")


def test_includes_time_class_module_details_and_traceback(session):
    baker.make(
        ImportLog,
        session=session,
        level="error",
        step="publication_import",
        message="Nie znaleziono domyślnej jednostki",
        details={
            "exception": "ValueError",
            "context": "Krytyczny błąd w publication_import",
            "traceback": (
                "Traceback (most recent call last):\n"
                '  File "x.py", line 96, in run\n'
                "ValueError: Nie znaleziono domyślnej jednostki"
            ),
        },
    )

    text = render_session_log_text(session)

    # czas (rok z timestampu), poziom, klasa błędu, moduł, message, context
    assert "[ERROR]" in text
    assert "exception=ValueError" in text
    assert "step=publication_import" in text
    assert "Nie znaleziono domyślnej jednostki" in text
    assert "context: Krytyczny błąd w publication_import" in text
    # cały traceback w logu
    assert "traceback:" in text
    assert "ValueError: Nie znaleziono domyślnej jednostki" in text
    assert 'File "x.py", line 96, in run' in text


def test_only_errors_and_warnings_included(session):
    baker.make(ImportLog, session=session, level="info", step="s", message="INFO_MSG")
    baker.make(ImportLog, session=session, level="debug", step="s", message="DEBUG_MSG")
    baker.make(ImportLog, session=session, level="success", step="s", message="OK_MSG")
    baker.make(
        ImportLog, session=session, level="warning", step="s", message="WARN_MSG"
    )
    baker.make(ImportLog, session=session, level="error", step="s", message="ERR_MSG")
    baker.make(
        ImportLog, session=session, level="critical", step="s", message="CRIT_MSG"
    )

    text = render_session_log_text(session)

    assert "WARN_MSG" in text
    assert "ERR_MSG" in text
    assert "CRIT_MSG" in text
    assert "INFO_MSG" not in text
    assert "DEBUG_MSG" not in text
    assert "OK_MSG" not in text


def test_entries_in_chronological_order_oldest_first(session):
    older = baker.make(
        ImportLog, session=session, level="error", step="a", message="FIRST"
    )
    newer = baker.make(
        ImportLog, session=session, level="error", step="b", message="SECOND"
    )
    # timestamp ma auto_now_add — wymuszamy kolejność przez UPDATE w bazie.
    now = timezone.now()
    ImportLog.objects.filter(pk=older.pk).update(
        timestamp=now - datetime.timedelta(hours=1)
    )
    ImportLog.objects.filter(pk=newer.pk).update(timestamp=now)

    text = render_session_log_text(session)

    assert text.index("FIRST") < text.index("SECOND")


def test_empty_when_no_errors_or_warnings(session):
    baker.make(ImportLog, session=session, level="info", step="s", message="INFO_MSG")

    text = render_session_log_text(session)

    assert "brak błędów i ostrzeżeń" in text.lower()
    assert "INFO_MSG" not in text


def test_empty_completed_claims_success(session):
    # ``session`` fixture jest ``completed`` — tu wolno powiedzieć „pomyślnie".
    text = render_session_log_text(session)

    assert "przebieg" in text.lower()
    assert "pomyślnie" in text.lower()


@pytest.mark.parametrize("status", ["pending", "running", "paused"])
def test_empty_active_session_does_not_claim_success(session, status):
    # Import wciąż trwa: brak wpisów ≠ sukces. Nie wolno twierdzić „pomyślnie".
    session.status = status
    session.save(update_fields=["status"])

    text = render_session_log_text(session)

    assert "pomyślnie" not in text.lower()
    assert "wciąż trwa" in text.lower()


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_empty_failed_or_cancelled_does_not_claim_success(session, status):
    # Zakończony, ale nie sukcesem — nie udajemy, że „przebiegł pomyślnie".
    session.status = status
    session.save(update_fields=["status"])

    text = render_session_log_text(session)

    assert "pomyślnie" not in text.lower()
    assert session.get_status_display().lower() in text.lower()


def test_handles_missing_details_without_crashing(session):
    baker.make(
        ImportLog,
        session=session,
        level="error",
        step="zrodla",
        message="goły błąd bez details",
        details=None,
    )

    text = render_session_log_text(session)

    assert "goły błąd bez details" in text
    assert "step=zrodla" in text


def test_header_contains_session_identity(session):
    text = render_session_log_text(session)

    assert str(session.id) in text
    assert str(session.user) in text


def _make_errors(session, n):
    for i in range(n):
        baker.make(
            ImportLog, session=session, level="error", step="s", message=f"ERR_{i}"
        )


def test_limit_caps_preview_and_notes_truncation(session):
    _make_errors(session, 5)

    text = render_session_log_text(session, limit=3)

    # tylko pierwsze 3 wpisy (chronologicznie ERR_0..ERR_2), nagłówek = total 5
    assert "ERR_0" in text and "ERR_1" in text and "ERR_2" in text
    assert "ERR_3" not in text and "ERR_4" not in text
    assert "Wpisy (błędy + ostrzeżenia): 5" in text
    assert "podgląd przycięty" in text.lower()
    assert "pierwsze 3 z 5" in text


def test_no_truncation_note_when_within_limit(session):
    _make_errors(session, 2)

    text = render_session_log_text(session, limit=3)

    assert "ERR_0" in text and "ERR_1" in text
    assert "podgląd przycięty" not in text.lower()


def test_full_render_without_limit_has_no_truncation_note(session):
    _make_errors(session, 5)

    text = render_session_log_text(session)  # limit=None → pełny log (pobranie)

    assert all(f"ERR_{i}" in text for i in range(5))
    assert "podgląd przycięty" not in text.lower()


def test_count_log_entries_counts_only_errors_and_warnings(session):
    _make_errors(session, 3)
    baker.make(ImportLog, session=session, level="warning", step="s", message="w")
    baker.make(ImportLog, session=session, level="info", step="s", message="i")
    baker.make(ImportLog, session=session, level="success", step="s", message="ok")

    from pbn_import.utils.log_export import count_log_entries

    assert count_log_entries(session) == 4
