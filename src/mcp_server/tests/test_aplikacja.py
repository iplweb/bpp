"""Aplikacja mcp_server jest zarejestrowana, a pakiet bpp-mcp dostępny."""

from django.apps import apps

from mcp_server.aplikacja import build_application
from mcp_server.tests.utils import uruchom


def test_aplikacja_zarejestrowana():
    assert apps.is_installed("mcp_server")


def test_pakiet_bpp_mcp_dostepny():
    from bpp_mcp import register_tools

    assert callable(register_tools)


def test_zarejestrowano_komplet_narzedzi():
    """11 narzędzi + 1 prompt — tyle daje register_tools z bpp-mcp 0.4.0."""
    mcp_app, _ = build_application()

    async def scenariusz():
        serwer = mcp_app.state.serwer_mcp
        return len(await serwer.list_tools()), len(await serwer.list_prompts())

    narzedzia, prompty = uruchom(scenariusz)
    assert narzedzia == 11
    assert prompty == 1


def test_fabryka_daje_nowa_instancje_za_kazdym_razem():
    """Aplikacja MUSI powstawać fabryką: allowlista hostów liczona przy
    imporcie nie zobaczyłaby settings nadpisanych w teście (spec §11)."""
    a, _ = build_application()
    b, _ = build_application()
    assert a is not b
