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
