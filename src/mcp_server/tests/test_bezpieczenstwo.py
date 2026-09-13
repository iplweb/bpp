"""Regresje bezpieczeństwa warstwy /mcp (spec §7)."""

import httpx
import pytest
from bpp_mcp.client import BppError

from mcp_server.klient import BppClientInProcess
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.tests.utils import uruchom


def _dane(host="bpp.example.test", bearer=None):
    return DaneZadania(
        host=host, scheme="https", ip="198.51.100.9", bearer=bearer, deadline=None
    )


def _przechwytujacy():
    zebrane = []

    def handler(request):
        zebrane.append(request)
        return httpx.Response(200, json={"ok": 1})

    return httpx.MockTransport(handler), zebrane


def test_cookie_nie_trafia_do_zadania_wewnetrznego():
    """Regresja na NIEOBECNOŚĆ forwardingu, nie na filtrowanie nagłówków.

    Żądanie wewnętrzne jest KONSTRUOWANE OD ZERA (nowy ``httpx.AsyncClient``
    w ``BppClientInProcess.__init__``, bez jara ciasteczek, bez kopiowania
    nagłówków zewnętrznego żądania) — nie ma w kodzie ŻADNEJ ścieżki
    (``cookies=`` czy inny mechanizm), którą ciasteczko mogłoby dotrzeć do
    tego żądania. To silniejsza gwarancja niż „filtr wycina Cookie" — nie ma
    czego filtrować. Test złapie regresję dokładnie wtedy, gdyby ktoś kiedyś
    dopisał przekazywanie nagłówków/ciasteczek zewnętrznego żądania.

    Dlaczego to ma znaczenie, GDYBY taki forwarding się pojawił: Cookie
    uwierzytelniłoby sesją przez ``SessionAuthentication`` (druga w
    ``DEFAULT_AUTHENTICATION_CLASSES``) — z pełnymi uprawnieniami, bez
    zgody, bez scope i bez możliwości revoke (spec §7.1).
    """
    transport, zebrane = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane())
        try:
            klient = BppClientInProcess(transport=transport)
            await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    assert "cookie" not in {k.lower() for k in zebrane[0].headers}


def test_basic_nie_trafia_do_zadania_wewnetrznego():
    """Regresja na NIEOBECNOŚĆ forwardingu, nie na strażnika TrybAuth.

    Dwa NIEZALEŻNE powody, dla których Basic tu nie trafi:

    1. ``BppClient._auth_kwargs`` ma jawną gałąź
       ``if self._tryb_auth is TrybAuth.W_PROCESIE: return {}`` — Basic jest
       tam świadomie pomijany.
    2. ALE nawet gdyby TĘ gałąź wycięto, Basic i tak by nie trafił: kod
       trafiłby do gałęzi ``if self._auth_tuple: return {"auth": ...}``,
       a ``BppClientInProcess.__init__`` buduje
       ``Config(base_url=..., transport="stdio")`` i NIGDY nie ustawia
       ``basic_auth`` — ``config.auth_tuple`` jest w tej konstrukcji zawsze
       ``None``. Basic nie ma więc czym trafić do żądania, niezależnie od
       strażnika (zweryfikowane mutacyjnie: wycięcie gałęzi 1. NIE psuje
       tego testu).

    Ten test pilnuje więc powodu 2. — konstrukcji ``Config`` bez
    ``basic_auth`` — a NIE gałęzi ``TrybAuth.W_PROCESIE``. UWAGA na
    przyszłość: gdyby ktoś kiedyś dopisał ``basic_auth=`` do ``Config`` w
    ``mcp_server/klient.py`` (np. z env), TEN test przestanie wystarczać —
    trzeba będzie dodać osobny test, który faktycznie ćwiczy gałąź 1.
    (np. skonfigurowany ``basic_auth`` + wycięta gałąź 1. → Basic w
    nagłówku).

    Dlaczego to ma znaczenie, GDYBY Basic trafił do żądania:
    ``BasicAuthentication`` jest trzecia w ``DEFAULT_AUTHENTICATION_CLASSES``,
    a ``ApiReadOnlyForBearerMiddleware`` sprawdza WYŁĄCZNIE prefiks
    ``bearer ``, więc dla Basica warstwa read-only w ogóle nie istnieje
    (spec §7.1).
    """
    transport, zebrane = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane(bearer=None))
        try:
            klient = BppClientInProcess(transport=transport)
            await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    naglowek = zebrane[0].headers.get("authorization", "")
    assert not naglowek.lower().startswith("basic")


def test_sciezka_spoza_api_v1_odrzucona():
    transport, _ = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane())
        try:
            klient = BppClientInProcess(transport=transport)
            with pytest.raises(BppError):
                await klient.get_json("https://bpp.example.test/admin/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)


def test_obcy_host_w_url_odrzucony():
    """_full_url przyjmuje URL-e bezwzględne wprost, a paginacyjne `next` je
    niosą — kontrola musi obejmować host, nie tylko prefiks (spec §7.4)."""
    transport, _ = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane(host="bpp.a.test"))
        try:
            klient = BppClientInProcess(transport=transport)
            with pytest.raises(BppError):
                await klient.get_json("https://bpp.zly.test/api/v1/autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
