from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from model_bakery import baker

from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_api.exceptions import AuthenticationResponseError

GET_USER_TOKEN = "pbn_api.autoryzacja.OAuthMixin.get_user_token"
DELAY = "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"


@pytest.fixture
def uzytkownik():
    return baker.make(BppUser, username="redaktor", is_active=True)


@pytest.fixture
def uczelnia():
    return baker.make(
        Uczelnia,
        skrot="UTEST",
        pbn_api_root="https://pbn.example.com",
        pbn_app_name="test_app",
        pbn_app_token="test_token",
    )


def _run(*args):
    out = StringIO()
    call_command("pbn_ott_na_token", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_ott_wymieniony_i_zapisany(uzytkownik, uczelnia):
    with patch(GET_USER_TOKEN, return_value="tajny-token-123") as mock_get:
        out = _run("ott-1", "--user", "redaktor")

    assert mock_get.call_args.args == (
        "https://pbn.example.com",
        "test_app",
        "test_token",
        "ott-1",
    )
    uzytkownik.refresh_from_db()
    assert uzytkownik.pbn_token == "tajny-token-123"
    assert uzytkownik.pbn_token_updated is not None
    assert "redaktor" in out
    assert "tajny-token-123" not in out


@pytest.mark.django_db
def test_pokaz_token_wypisuje_token(uzytkownik, uczelnia):
    with patch(GET_USER_TOKEN, return_value="tajny-token-123"):
        out = _run("ott-1", "--user", "redaktor", "--pokaz-token")

    assert "tajny-token-123" in out


@pytest.mark.django_db
def test_token_bez_kontaktu_z_pbn(uzytkownik):
    with patch(GET_USER_TOKEN) as mock_get:
        out = _run("--user", "redaktor", "--token", "przeniesiony-token")

    mock_get.assert_not_called()
    uzytkownik.refresh_from_db()
    assert uzytkownik.pbn_token == "przeniesiony-token"
    assert "przeniesiony-token" not in out


@pytest.mark.django_db(transaction=True)
def test_kolejka_uruchomiona_po_zapisie(uzytkownik, uczelnia):
    with (
        patch(GET_USER_TOKEN, return_value="tajny-token-123"),
        patch(DELAY) as mock_delay,
    ):
        _run("ott-1", "--user", "redaktor")

    mock_delay.assert_called_once_with(uzytkownik.pk)


@pytest.mark.django_db
def test_ott_i_token_wykluczaja_sie(uzytkownik, uczelnia):
    with pytest.raises(CommandError):
        _run("ott-1", "--user", "redaktor", "--token", "x")


@pytest.mark.django_db
def test_brak_ott_i_tokenu(uzytkownik, uczelnia):
    with pytest.raises(CommandError):
        _run("--user", "redaktor")


@pytest.mark.django_db
def test_brak_uzytkownika(uczelnia):
    with patch(GET_USER_TOKEN) as mock_get, pytest.raises(CommandError):
        _run("ott-1", "--user", "nie-ma-takiego")
    mock_get.assert_not_called()


@pytest.mark.django_db
def test_wiele_uczelni_bez_wskazania(uzytkownik, uczelnia):
    baker.make(Uczelnia, skrot="DRUGA")
    with patch(GET_USER_TOKEN) as mock_get:
        with pytest.raises(CommandError, match="UTEST"):
            _run("ott-1", "--user", "redaktor")
    mock_get.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("wskazanie", ["UTEST", None])
def test_wiele_uczelni_ze_wskazaniem(uzytkownik, uczelnia, wskazanie):
    baker.make(Uczelnia, skrot="DRUGA", pbn_api_root="https://inny.example.com")
    wskazanie = wskazanie or str(uczelnia.pk)
    with patch(GET_USER_TOKEN, return_value="t") as mock_get:
        _run("ott-1", "--user", "redaktor", "--uczelnia", wskazanie)

    assert mock_get.call_args.args[0] == "https://pbn.example.com"


@pytest.mark.django_db
def test_blad_pbn(uzytkownik, uczelnia):
    with patch(GET_USER_TOKEN, side_effect=AuthenticationResponseError(b"x")):
        with pytest.raises(CommandError, match="OTT"):
            _run("ott-1", "--user", "redaktor")
    uzytkownik.refresh_from_db()
    assert not uzytkownik.pbn_token


@pytest.mark.django_db
def test_pusta_odpowiedz_pbn(uzytkownik, uczelnia):
    with patch(GET_USER_TOKEN, return_value=None):
        with pytest.raises(CommandError):
            _run("ott-1", "--user", "redaktor")
    uzytkownik.refresh_from_db()
    assert not uzytkownik.pbn_token
