"""Tests for the modern ``pbn_import`` management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management.base import OutputWrapper
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.management.commands.pbn_import import (
    Command,
    build_config_from_options,
)
from pbn_import.models import ImportSession
from pbn_import.utils.step_definitions import ALL_STEP_DEFINITIONS


def command_options(**overrides):
    options = {
        "app_id": "app-id",
        "app_token": "app-token",
        "base_url": "https://pbn.example.test",
        "user_token": "user-token",
        "delete_existing": False,
        "wydzial_domyslny": "Wydzial Domyslny",
        "wydzial_domyslny_skrot": "WD",
        "username": None,
        "noinput": True,
    }
    for step in ALL_STEP_DEFINITIONS:
        options[f"disable_{step['form_field']}"] = False
    options.update(overrides)
    return options


def make_command():
    command = Command()
    command.stdout = OutputWrapper(StringIO())
    command.stderr = OutputWrapper(StringIO())
    return command


def test_build_config_from_options_maps_all_step_disable_keys():
    options = command_options(
        delete_existing=True,
        disable_zrodla=True,
        disable_publikacje=True,
    )

    config = build_config_from_options(options)

    assert config["app_id"] == "app-id"
    assert config["base_url"] == "https://pbn.example.test"
    assert config["delete_existing"] is True
    assert config["disable_zrodla"] is True
    assert config["disable_publikacje"] is True

    for step in ALL_STEP_DEFINITIONS:
        assert step["disable_key"] in config


@pytest.mark.django_db
def test_get_import_user_uses_explicit_username(django_user_model):
    user = baker.make(django_user_model, username="chosen-user")

    assert make_command()._get_import_user({"username": "chosen-user"}) == user


@pytest.mark.django_db
def test_get_import_user_falls_back_to_first_superuser(django_user_model):
    baker.make(django_user_model, username="normal-user", is_superuser=False)
    superuser = baker.make(django_user_model, username="admin-user", is_superuser=True)

    assert make_command()._get_import_user({}) == superuser


@pytest.mark.django_db
def test_get_import_user_returns_none_without_superuser(django_user_model):
    baker.make(django_user_model, username="normal-user", is_superuser=False)

    assert make_command()._get_import_user({}) is None


@pytest.mark.django_db
def test_ensure_pbn_integration_enables_single_uczelnia():
    uczelnia = baker.make(Uczelnia, pbn_integracja=False)

    make_command()._ensure_pbn_integration(uczelnia)

    uczelnia.refresh_from_db()
    assert uczelnia.pbn_integracja is True


@pytest.mark.django_db
def test_handle_noinput_creates_session_and_runs_manager(django_user_model):
    user = baker.make(django_user_model, username="import-user", is_superuser=False)
    uczelnia = baker.make(Uczelnia, pbn_integracja=True)
    command = make_command()
    command._resolved_uczelnia = uczelnia
    client = MagicMock()

    with patch.object(command, "_ensure_pbn_integration") as ensure_integration:
        with patch.object(command, "get_client", return_value=client) as get_client:
            with patch(
                "pbn_import.management.commands.pbn_import.ImportManager"
            ) as manager_class:
                manager_class.return_value.run.return_value = {
                    "success": True,
                    "results": {"initial_setup": {"ok": True}},
                }

                command.handle(**command_options(username=user.username))

    ensure_integration.assert_called_once_with(uczelnia)
    get_client.assert_called_once_with(
        app_id="app-id",
        app_token="app-token",
        base_url="https://pbn.example.test",
        user_token="user-token",
    )
    session = ImportSession.objects.get(user=user)
    assert session.config["wydzial_domyslny"] == "Wydzial Domyslny"
    assert session.config["disable_initial"] is False
    manager_class.assert_called_once_with(
        session=session,
        client=client,
        config=session.config,
        uczelnia=uczelnia,
    )


@pytest.mark.django_db
def test_handle_uses_resolved_uczelnia_for_integration_and_manager(django_user_model):
    user = baker.make(django_user_model, username="import-user", is_superuser=False)
    other_uczelnia = baker.make(Uczelnia, pbn_integracja=False)
    resolved_uczelnia = baker.make(Uczelnia, pbn_integracja=False)
    command = make_command()
    command._resolved_uczelnia = resolved_uczelnia
    client = MagicMock()

    with patch.object(command, "get_client", return_value=client):
        with patch(
            "pbn_import.management.commands.pbn_import.ImportManager"
        ) as manager:
            manager.return_value.run.return_value = {
                "initial_setup": {"ok": True},
            }

            command.handle(**command_options(username=user.username))

    other_uczelnia.refresh_from_db()
    resolved_uczelnia.refresh_from_db()
    assert other_uczelnia.pbn_integracja is False
    assert resolved_uczelnia.pbn_integracja is True

    session = ImportSession.objects.get(user=user)
    manager.assert_called_once_with(
        session=session,
        client=client,
        config=session.config,
        uczelnia=resolved_uczelnia,
    )


@pytest.mark.django_db
def test_handle_interactive_cancel_does_not_create_session(django_user_model):
    baker.make(django_user_model, username="admin-user", is_superuser=True)
    command = make_command()

    with patch.object(command, "run_interactive", return_value=None):
        command.handle(**command_options(noinput=False))

    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_handle_reraises_manager_error_and_writes_session_error(django_user_model):
    user = baker.make(django_user_model, username="import-user", is_superuser=False)
    command = make_command()

    with patch.object(command, "_ensure_pbn_integration"):
        with patch.object(command, "get_client", return_value=MagicMock()):
            with patch(
                "pbn_import.management.commands.pbn_import.ImportManager"
            ) as manager_class:
                manager_class.return_value.run.side_effect = RuntimeError("boom")

                with pytest.raises(RuntimeError, match="boom"):
                    command.handle(**command_options(username=user.username))

    assert ImportSession.objects.filter(user=user).exists()
    assert "Import nieudany" in command.stderr._out.getvalue()


def test_run_interactive_cancel_on_step_selection():
    command = make_command()

    with patch(
        "pbn_import.management.commands.pbn_import.questionary.checkbox"
    ) as checkbox:
        checkbox.return_value.ask.return_value = None

        assert command.run_interactive(command_options(noinput=False)) is None

    assert "Anulowano" in command.stdout._out.getvalue()


def test_run_interactive_applies_selected_steps_and_delete_choice():
    command = make_command()
    selected = ["initial", "publikacje"]

    with patch(
        "pbn_import.management.commands.pbn_import.questionary.checkbox"
    ) as checkbox:
        with patch(
            "pbn_import.management.commands.pbn_import.questionary.confirm"
        ) as confirm:
            checkbox.return_value.ask.return_value = selected
            confirm.return_value.ask.side_effect = [True, True]

            options = command.run_interactive(command_options(noinput=False))

    assert options["delete_existing"] is True
    assert options["disable_initial"] is False
    assert options["disable_publikacje"] is False
    assert options["disable_zrodla"] is True
