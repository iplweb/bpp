"""Fail-closed na tożsamości uczelni: host bez uczelni NIE dochodzi do MCP.

Bloker, który to wymusił: ``ALLOWED_HOSTS`` na produkcji zawiera hosty
infrastrukturalne (``127.0.0.1``, ``appserver``, ``appserver:8000`` —
``settings/production.py``). Przechodziły OBIE bramki (allowlista SDK i
``get_host()`` Django), a potem ``Uczelnia.objects.get_for_request`` nie
znajdowało dla nich ``Site``. Skutek w instalacji wielouczelnianej:

* ``BramkaApiV1.has_permission`` przy ``Uczelnia=None`` zwraca ``True``
  BEZWARUNKOWO — także przy ``api_v1_wlaczone=False``;
* ``scope_rekord_do_uczelni`` staje się no-op;
* ``UkryjStatusyKorektyMixin`` przestaje wykluczać ukryte statusy korekty.

Czyli ``curl -H 'Host: appserver' https://<uczelnia>/mcp`` obchodził wyłącznik
API i filtr ukrytych statusów. Testy poniżej pilnują obu stron kontraktu:
odmowy w instalacji wielouczelnianej i ZACHOWANIA działania w jednouczelnianej,
gdzie fallback na ``SITE_ID`` jest legalny.
"""

import pytest

from mcp_server.routing import RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope

pytestmark = pytest.mark.django_db(transaction=True)


class _AtrapaLifespanu:
    def __init__(self):
        self.router = self

    def lifespan_context(self, _app):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            yield

        return _ctx()


async def _mcp(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"MCP"})


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"DJANGO"})


def _odpytaj(host, sciezka="/mcp"):
    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    return uruchom(lambda: wywolaj(router, zbuduj_scope(sciezka, host=host)))


def test_host_infrastrukturalny_odrzucony_przy_wielu_uczelniach(uczelnia1, uczelnia2):
    """DOKŁADNIE scenariusz blokera: ``Host: appserver`` jest w produkcyjnym
    ``ALLOWED_HOSTS``, nie ma swojego ``Site`` i przy dwóch uczelniach niczego
    nie rozstrzyga. Ma dostać 421, a nie obsługę z otwartą bramką."""
    status, _, tresc = _odpytaj("appserver")
    assert status == 421
    assert "MCP" not in tresc


def test_localhost_z_portem_tez_odrzucony_przy_wielu_uczelniach(uczelnia1, uczelnia2):
    """Port w nagłówku ``Host`` nie może być furtką — rozstrzyganie ``Site``
    porównuje samą nazwę, więc i bramka musi ją odcinać tak samo."""
    status, _, _ = _odpytaj("appserver:8000")
    assert status == 421


def test_host_wlasnej_uczelni_przechodzi(uczelnia1, uczelnia2):
    """Kontrola pozytywna: host, który MA swój ``Site``, przechodzi normalnie —
    bramka nie może być „odrzuca wszystko”."""
    status, _, tresc = _odpytaj("uczelnia1.localhost")
    assert status == 200 and tresc == "MCP"


def test_instalacja_jednouczelniana_dziala_z_dowolnym_dozwolonym_hostem(uczelnia):
    """NIE WOLNO zepsuć instalacji jednouczelnianej. Tam fallback na ``SITE_ID``
    (a dalej na „jedyną uczelnię”) jest legalny i tak działa cały serwis — host
    bez własnego ``Site`` musi więc dalej przechodzić."""
    status, _, tresc = _odpytaj("bpp.example.test")
    assert status == 200 and tresc == "MCP"


def test_brak_uczelni_w_bazie_odrzucony():
    """Świeża instalacja / niedokończony kreator: nie ma czego serwować, a
    ``Uczelnia=None`` to właśnie stan, w którym bramka API przepuszcza
    wszystko. Fail-closed."""
    status, _, _ = _odpytaj("bpp.example.test")
    assert status == 421


def test_bramka_dziala_takze_na_mcp_auth(uczelnia1, uczelnia2):
    """Adres z logowaniem musi mieć tę samą bramkę — inaczej zostałaby dziura
    o rozmiarze jednego znaku w ścieżce."""
    status, _, _ = _odpytaj("appserver", "/mcp/auth")
    assert status == 421


def test_strona_dla_czlowieka_nie_jest_bramkowana(uczelnia1, uczelnia2):
    """``/mcp/`` (ze slashem) idzie normalnym trybem przez Django, gdzie host
    obsługuje ``ALLOWED_HOSTS`` i ``SiteResolutionMiddleware`` — nasza bramka
    nie ma prawa go dotykać."""
    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    status, _, tresc = uruchom(
        lambda: wywolaj(router, zbuduj_scope("/mcp/", metoda="GET", host="appserver"))
    )
    assert status == 200 and tresc == "DJANGO"
