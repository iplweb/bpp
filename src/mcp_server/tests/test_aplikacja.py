"""Aplikacja mcp_server jest zarejestrowana, a pakiet bpp-mcp dostępny."""

from django.apps import apps


def test_aplikacja_zarejestrowana():
    assert apps.is_installed("mcp_server")


def test_pakiet_bpp_mcp_dostepny():
    from bpp_mcp import register_tools

    assert callable(register_tools)
