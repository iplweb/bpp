"""``stan_mcp()`` odróżnia „proces działa" od „endpoint MCP działa" (spec §10.3).

Testy podstawiają FAŁSZYWY moduł pod ``django_bpp.asgi`` w ``sys.modules`` —
import prawdziwego modułu wykonuje ``build_application()`` przy imporcie
i ta jedna instancja żyje tyle, co proces (patrz komentarz w
``test_asgi_montaz.py``); podstawienie unika triggerowania tego kosztu/efektu
w każdym teście tego pliku.
"""

import sys
import types

from mcp_server.zdrowie import stan_mcp


class _FalszywyStart:
    def __init__(self, wystartowany: bool, zywy: bool) -> None:
        self.wystartowany = wystartowany
        self.zywy = zywy


def _podstaw_asgi(monkeypatch, start) -> None:
    falszywy_modul = types.ModuleType("django_bpp.asgi")
    falszywy_modul._mcp_start = start
    monkeypatch.setitem(sys.modules, "django_bpp.asgi", falszywy_modul)


def test_wystartowany_i_zywy(monkeypatch):
    _podstaw_asgi(monkeypatch, _FalszywyStart(wystartowany=True, zywy=True))
    assert stan_mcp() == {"wystartowany": True, "zywy": True}


def test_zatruta_grupa_zadan_wystartowany_ale_nie_zywy(monkeypatch):
    """Grupa zadań zdechła po zatruciu wyjątkiem dziecka — proces wciąż
    żyje, ale ``/mcp`` już nie odpowie, aż do recyklingu workera."""
    _podstaw_asgi(monkeypatch, _FalszywyStart(wystartowany=True, zywy=False))
    assert stan_mcp() == {"wystartowany": True, "zywy": False}


def test_jeszcze_nie_wystartowany(monkeypatch):
    _podstaw_asgi(monkeypatch, _FalszywyStart(wystartowany=False, zywy=False))
    assert stan_mcp() == {"wystartowany": False, "zywy": False}
