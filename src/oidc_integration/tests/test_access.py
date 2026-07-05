"""Testy per-uczelnia gatingu OIDC (`oidc_enabled_for_request`) i context
processora menu (`oidc_auth_status`).
"""

import pytest
from django.test import override_settings
from model_bakery import baker

from bpp.context_processors.oidc import oidc_auth_status
from oidc_integration.access import oidc_enabled_for_request


class _Req:
    """Lekki request: get_for_request czyta tylko atrybut ``_uczelnia``."""

    def __init__(self, uczelnia):
        self._uczelnia = uczelnia


@override_settings(OIDC_LOGIN_ENABLED=False)
def test_wylaczone_oidc_zwraca_false():
    assert oidc_enabled_for_request(_Req(None)) is False


@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="")
def test_bez_skrotu_dziala_globalnie():
    # Konfiguracja bez skrótu = instalacja jedno-uczelniana → OIDC globalnie.
    assert oidc_enabled_for_request(_Req(None)) is True


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="UAFM")
def test_dopasowanie_skrotu_uczelni_true():
    uczelnia = baker.make("bpp.Uczelnia", skrot="UAFM")
    assert oidc_enabled_for_request(_Req(uczelnia)) is True


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="uafm")
def test_dopasowanie_skrotu_ignoruje_wielkosc_liter():
    uczelnia = baker.make("bpp.Uczelnia", skrot="UAFM")
    assert oidc_enabled_for_request(_Req(uczelnia)) is True


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="UAFM")
def test_inna_uczelnia_nie_widzi_oidc():
    uczelnia = baker.make("bpp.Uczelnia", skrot="INNA")
    assert oidc_enabled_for_request(_Req(uczelnia)) is False


@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="UAFM")
def test_brak_uczelni_w_requescie_false():
    assert oidc_enabled_for_request(_Req(None)) is False


@override_settings(OIDC_LOGIN_ENABLED=False)
def test_context_processor_krotkie_spiecie_gdy_wylaczone():
    out = oidc_auth_status(_Req(None))
    assert out == {"oidc_login_enabled": False, "oidc_login_skrot": ""}


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_ENABLED=True, OIDC_LOGIN_SKROT="UAFM")
def test_context_processor_per_uczelnia():
    uafm = baker.make("bpp.Uczelnia", skrot="UAFM")
    inna = baker.make("bpp.Uczelnia", skrot="INNA")

    assert oidc_auth_status(_Req(uafm))["oidc_login_enabled"] is True
    assert oidc_auth_status(_Req(inna))["oidc_login_enabled"] is False
    assert oidc_auth_status(_Req(uafm))["oidc_login_skrot"] == "UAFM"
