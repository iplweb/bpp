"""Testy helpera ``czy_zwijac_liste_autorow`` — rozstrzyganie efektywnej
wartości ustawienia „zwijaj długie listy autorów" wg kolejności:
preferencja zalogowanego użytkownika → ustawienie uczelni → domyślnie True."""

from types import SimpleNamespace

import pytest

from bpp.models.profile import ZwijanieAutorow
from bpp.templatetags.prace import czy_zwijac_liste_autorow

ANONIM = SimpleNamespace(is_authenticated=False)


def _req(user):
    return SimpleNamespace(user=user)


def _uczelnia(flag):
    return SimpleNamespace(zwijaj_dlugie_listy_autorow=flag)


def _user(pref):
    return SimpleNamespace(is_authenticated=True, zwijaj_dlugie_listy_autorow=pref)


@pytest.mark.parametrize("flag,expected", [(True, True), (False, False)])
def test_anonim_dziedziczy_z_uczelni(flag, expected):
    assert czy_zwijac_liste_autorow(_req(ANONIM), _uczelnia(flag)) is expected


def test_brak_requestu_dziedziczy_z_uczelni():
    assert czy_zwijac_liste_autorow(None, _uczelnia(True)) is True
    assert czy_zwijac_liste_autorow(None, _uczelnia(False)) is False


def test_user_zawsze_nadpisuje_uczelnie():
    req = _req(_user(ZwijanieAutorow.ZAWSZE))
    assert czy_zwijac_liste_autorow(req, _uczelnia(False)) is True


def test_user_nigdy_nadpisuje_uczelnie():
    req = _req(_user(ZwijanieAutorow.NIGDY))
    assert czy_zwijac_liste_autorow(req, _uczelnia(True)) is False


@pytest.mark.parametrize("flag,expected", [(True, True), (False, False)])
def test_user_domyslne_dziedziczy_z_uczelni(flag, expected):
    req = _req(_user(ZwijanieAutorow.DOMYSLNE))
    assert czy_zwijac_liste_autorow(req, _uczelnia(flag)) is expected


def test_brak_uczelni_domyslnie_zwija():
    assert czy_zwijac_liste_autorow(None, None) is True
