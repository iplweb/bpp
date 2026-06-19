"""Testy pipeline'u post-importu (`ImportManager._run_post_import_commands`).

Reguła: błąd komendy post-importu (np. `ustaw_zwrotnie_punkty_ciaglych`)
NIE może zniknąć po cichu. Ma:
- trafić do Rollbara (`rollbar.report_exc_info`),
- zostać zapisany jako `ImportLog` (poziom "error") widoczny w UI importu,
- a mimo to NIE wywalać całego importu — pozostałe komendy lecą dalej.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError

from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.import_manager import ImportManager


def _manager():
    user = get_user_model().objects.create_user(username="testuser")
    session = ImportSession.objects.create(user=user)
    return ImportManager(session, client=None, config={})


@pytest.mark.django_db
def test_failing_post_import_command_is_reported_not_swallowed():
    manager = _manager()

    def fake_call_command(cmd, *a, **kw):
        if cmd == "ustaw_zwrotnie_punkty_ciaglych":
            raise CommandError("W systemie jest więcej niż jedna uczelnia")
        return None

    with (
        patch(
            "pbn_import.utils.import_manager.call_command",
            side_effect=fake_call_command,
        ),
        patch(
            "pbn_import.utils.import_manager.rollbar.report_exc_info"
        ) as mock_rollbar,
    ):
        manager._run_post_import_commands()

    # Błąd komendy MUSI trafić do Rollbara — nie do nikąd.
    assert mock_rollbar.called

    # ...i zostać zapisany jako log sesji widoczny w UI importu.
    error_logs = ImportLog.objects.filter(session=manager.session, level="error")
    assert error_logs.filter(
        message__icontains="ustaw_zwrotnie_punkty_ciaglych"
    ).exists()


@pytest.mark.django_db
def test_failing_post_import_command_does_not_abort_remaining():
    manager = _manager()
    attempted = []

    def fake_call_command(cmd, *a, **kw):
        attempted.append(cmd)
        if cmd == "ustaw_zwrotnie_punkty_zwartych":
            raise CommandError("boom")
        return None

    with (
        patch(
            "pbn_import.utils.import_manager.call_command",
            side_effect=fake_call_command,
        ),
        patch("pbn_import.utils.import_manager.rollbar.report_exc_info"),
    ):
        manager._run_post_import_commands()

    # Mimo błędu pierwszej komendy, kolejne nadal są uruchamiane.
    assert "ustaw_zwrotnie_punkty_ciaglych" in attempted
    assert "przypisz_rekordy_aktualnym_jednostkom_autorow" in attempted
