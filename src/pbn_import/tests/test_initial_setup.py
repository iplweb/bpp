"""Tests for the PBN import initial setup step."""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa, Jezyk, Uczelnia
from pbn_api.models import Institution
from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.initial_setup import InitialSetup


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia, nazwa="Uniwersytet Testowy", pbn_integracja=False)


def test_run_full_setup_uses_existing_client_and_matches_uczelnia(session, uczelnia):
    client = MagicMock()
    matched = baker.make(Institution)
    setup = InitialSetup(session, client=client, uczelnia=uczelnia)

    with patch("pbn_import.utils.initial_setup.integruj_jezyki") as jezyki:
        with patch("pbn_import.utils.initial_setup.integruj_kraje") as kraje:
            with patch("pbn_import.utils.initial_setup.pobierz_instytucje_polon"):
                with patch(
                    "pbn_import.utils.initial_setup.matchuj_uczelnie",
                    return_value=matched,
                ):
                    result = setup.run()

    jezyki.assert_called_once_with(client, create_if_not_exists=True)
    kraje.assert_called_once_with(client)
    # sync_disciplines() sam pobiera słownik — nie wołamy download_disciplines()
    # bezpośrednio (regresja: podwójny zaciąg z PBN).
    client.download_disciplines.assert_not_called()
    client.sync_disciplines.assert_called_once()
    uczelnia.refresh_from_db()
    session.refresh_from_db()
    assert uczelnia.pbn_integracja is True
    assert uczelnia.pbn_uid_id == matched.pk
    assert session.config["uczelnia_auto_matched"] is True
    assert result["languages_integrated"] is True
    assert result["uczelnia_matched"] is True


def test_run_without_client_creates_client_from_uczelnia(session, uczelnia):
    client = MagicMock()
    setup = InitialSetup(session, client=None, uczelnia=uczelnia)

    with patch.object(uczelnia, "pbn_client", return_value=client) as pbn_client:
        with patch("pbn_import.utils.initial_setup.integruj_jezyki"):
            with patch("pbn_import.utils.initial_setup.integruj_kraje"):
                with patch("pbn_import.utils.initial_setup.pobierz_instytucje_polon"):
                    with patch(
                        "pbn_import.utils.initial_setup.matchuj_uczelnie",
                        return_value=None,
                    ):
                        result = setup.run()

    pbn_client.assert_called_once_with()
    assert setup.client == client
    assert result["institutions_fetched"] is True


def test_run_without_working_client_falls_back_to_minimal_setup(session, uczelnia):
    setup = InitialSetup(session, client=None, uczelnia=uczelnia)

    with patch.object(uczelnia, "pbn_client", side_effect=RuntimeError("no config")):
        result = setup.run()

    uczelnia.refresh_from_db()
    assert uczelnia.pbn_integracja is True
    assert result["minimal_setup"] is True
    assert Jezyk.objects.filter(nazwa="polski").exists()
    assert Dyscyplina_Naukowa.objects.filter(kod="2.3").exists()


def test_language_authorization_error_stops_import(session, uczelnia):
    setup = InitialSetup(session, client=MagicMock(), uczelnia=uczelnia)

    with patch(
        "pbn_import.utils.initial_setup.integruj_jezyki",
        side_effect=RuntimeError("auth failed"),
    ):
        with patch.object(setup, "is_authorization_error", return_value=True):
            with pytest.raises(Exception, match="Brak autoryzacji PBN"):
                setup.run()

    assert ImportLog.objects.filter(session=session, level="critical").exists()


def test_language_non_authorization_error_uses_minimal_setup(session, uczelnia):
    setup = InitialSetup(session, client=MagicMock(), uczelnia=uczelnia)

    with patch(
        "pbn_import.utils.initial_setup.integruj_jezyki",
        side_effect=RuntimeError("temporary outage"),
    ):
        with patch.object(setup, "is_authorization_error", return_value=False):
            result = setup.run()

    assert result["minimal_setup"] is True
    assert ImportLog.objects.filter(
        session=session,
        level="warning",
        message__contains="Nie można zintegrować języków",
    ).exists()


def test_later_pbn_errors_are_delegated_and_import_continues(session, uczelnia):
    client = MagicMock()
    # Krok dyscyplin woła teraz tylko sync_disciplines() — tam wstrzykujemy błąd.
    client.sync_disciplines.side_effect = RuntimeError("disciplines failed")
    setup = InitialSetup(session, client=client, uczelnia=uczelnia)

    with patch("pbn_import.utils.initial_setup.integruj_jezyki"):
        with patch(
            "pbn_import.utils.initial_setup.integruj_kraje",
            side_effect=RuntimeError("countries failed"),
        ):
            with patch(
                "pbn_import.utils.initial_setup.pobierz_instytucje_polon",
                side_effect=RuntimeError("institutions failed"),
            ):
                with patch.object(setup, "handle_pbn_error") as handle_error:
                    result = setup.run()

    assert handle_error.call_count == 3
    assert result["countries_integrated"] is True
    assert result["disciplines_synced"] is True
    assert result["institutions_fetched"] is True
    assert "current_subtask" not in session.progress_data


def test_auto_match_without_result_marks_manual_match_required(session, uczelnia):
    setup = InitialSetup(session, client=MagicMock(), uczelnia=uczelnia)

    with patch("pbn_import.utils.initial_setup.matchuj_uczelnie", return_value=None):
        setup._auto_match_uczelnia(uczelnia)

    session.refresh_from_db()
    assert session.config["uczelnia_match_required"] is True
    assert session.config["uczelnia_nazwa"] == uczelnia.nazwa
    assert setup.errors == [
        f"Uczelnia '{uczelnia.nazwa}' wymaga ręcznego wyboru PBN UID"
    ]
