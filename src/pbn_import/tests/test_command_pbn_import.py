"""Tests for the modern ``pbn_import`` management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management.base import OutputWrapper
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.management.commands.pbn_import import (
    IMPORT_STEPS,
    LEGACY_ALIASES,
    Command,
    build_config_from_options,
)
from pbn_import.models import ImportSession


def command_options(**overrides):
    """Buduj słownik opcji CLI odpowiadający nowemu modelowi faz granularnych."""
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
    # Granularne flagi faz (disable_<form_field> = False domyślnie)
    for form_field, _label in IMPORT_STEPS:
        options[f"disable_{form_field}"] = False
    # Legacy aliasy (disable_<entity> = False domyślnie)
    for entity in LEGACY_ALIASES:
        options[f"disable_{entity}"] = False
    options.update(overrides)
    return options


def make_command():
    command = Command()
    command.stdout = OutputWrapper(StringIO())
    command.stderr = OutputWrapper(StringIO())
    return command


def test_build_config_from_options_maps_all_step_disable_keys():
    """Granularne disable_<form_field> trafiają do config.

    Sprawdzamy też że legacy alias disable_zrodla=True ustawia obie fazy
    oraz że config zawiera klucz dla każdej granularnej fazy.
    """
    options = command_options(
        delete_existing=True,
        disable_zrodla=True,
    )

    config = build_config_from_options(options)

    assert config["app_id"] == "app-id"
    assert config["base_url"] == "https://pbn.example.test"
    assert config["delete_existing"] is True

    # Legacy alias disable_zrodla=True → obie fazy wyłączone
    assert config["disable_zrodla_download"] is True
    assert config["disable_zrodla_process"] is True

    # Każda granularna faza ma swój klucz w config
    for form_field, _label in IMPORT_STEPS:
        assert f"disable_{form_field}" in config


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
    """run_interactive ustawia granularne flagi faz na podstawie wyboru.

    W modelu faz granularnych `selected` zawiera form_field poszczególnych faz
    (np. "initial", "publikacje_download", "publikacje_process").
    Fazy nieznajdujące się w `selected` mają disable_<form_field>=True.
    """
    command = make_command()
    # Wybieramy tylko fazę "initial" i obie fazy publikacji;
    # fazy zrodla_download/zrodla_process są NIEwybrane → disable=True.
    selected = ["initial", "publikacje_download", "publikacje_process"]

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
    # Wybrane fazy → nie wyłączone
    assert options["disable_initial"] is False
    assert options["disable_publikacje_download"] is False
    assert options["disable_publikacje_process"] is False
    # Niewybrane fazy źródeł → wyłączone
    assert options["disable_zrodla_download"] is True
    assert options["disable_zrodla_process"] is True


# --- Task 11: granularne flagi faz + legacy aliasy ---


def _base_options(**over):
    opts = {
        "app_id": None,
        "base_url": None,
        "delete_existing": False,
        "wydzial_domyslny": "X",
        "wydzial_domyslny_skrot": None,
    }
    opts.update(over)
    return opts


def test_granular_flag_disables_one_phase():
    cfg = build_config_from_options(_base_options(disable_zrodla_download=True))
    assert cfg["disable_zrodla_download"] is True
    assert cfg.get("disable_zrodla_process", False) is False


def test_legacy_flag_disables_both_phases():
    cfg = build_config_from_options(_base_options(disable_zrodla=True))
    assert cfg["disable_zrodla_download"] is True
    assert cfg["disable_zrodla_process"] is True
