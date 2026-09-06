"""RouterHttp: dopasowanie DOKŁADNE + przepisanie ścieżki dla /mcp/auth.

SDK montuje trasę jako Starlette ``Route`` (regex ^/mcp$), nie ``Mount``, więc
bez przepisania ścieżki /mcp/auth dostałoby 404 (spec §5.1, bloker BL-1).
Dopasowanie prefiksowe byłoby dodatkowo sprzeczne z §8: /mcp/ ma iść do Django.
"""

import pytest

from mcp_server.routing import LifespanMcp, RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


def _token(raw: str, *, scope: str = "read", aktywny: bool = True):
    """Realny access token w bazie — jak w ``test_auth.py`` (Task 5).

    ``BramkaBearera`` sprawdza WAŻNOŚĆ tokenu w bazie niezależnie od
    ``wymagany`` (spec §5.4, tabela D10: „zły / wygasły / bez scope" → 401
    na OBU adresach). Testy poniżej, które przepuszczają bearer przez
    prawdziwą bramkę, muszą więc dać jej token, który faktycznie istnieje —
    zmyślony ciąg zostałby odrzucony 401-ką, zanim aplikacja MCP go zobaczy.
    """
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from model_bakery import baker
    from oauth2_provider.models import get_access_token_model, get_application_model

    user = baker.make(get_user_model(), is_active=aktywny)
    app = get_application_model().objects.create(
        name=f"test-{raw}",
        client_type="public",
        authorization_grant_type="authorization-code",
    )
    return get_access_token_model().objects.create(
        user=user,
        application=app,
        token=raw,
        scope=scope,
        expires=timezone.now() + timedelta(seconds=3600),
    )


class _AtrapaLifespanu:
    def __init__(self):
        self.router = self

    def lifespan_context(self, _app):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            yield

        return _ctx()


async def _echo_sciezki(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"MCP:" + scope["path"].encode()})


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send(
        {"type": "http.response.body", "body": b"DJANGO:" + scope["path"].encode()}
    )


def _router():
    return RouterHttp(_echo_sciezki, _django, StartMcp(_AtrapaLifespanu()))


def test_mcp_trafia_do_aplikacji_mcp():
    status, _, tresc = uruchom(lambda: wywolaj(_router(), zbuduj_scope("/mcp")))
    assert status == 200 and tresc == "MCP:/mcp"


@pytest.mark.django_db(transaction=True)
def test_mcp_auth_ma_przepisana_sciezke_na_mcp():
    """REGRESJA BL-1: bez przepisania SDK oddałoby 404.

    ``/mcp/auth`` bez ważnego tokenu to zawsze 401 (spec §5.4, D10) — bez
    tokenu bramka odrzuciłaby żądanie PRZED aplikacją MCP niezależnie od
    przepisania ścieżki, więc dowodem na BL-1 może być tylko przejście
    z WAŻNYM tokenem.
    """
    _token("TOKEN-BL1")
    scope = zbuduj_scope("/mcp/auth", naglowki={"authorization": "Bearer TOKEN-BL1"})
    status, _, tresc = uruchom(lambda: wywolaj(_router(), scope))
    assert status == 200 and tresc == "MCP:/mcp"


def test_mcp_ze_slashem_idzie_do_django():
    status, _, tresc = uruchom(
        lambda: wywolaj(_router(), zbuduj_scope("/mcp/", metoda="GET"))
    )
    assert tresc == "DJANGO:/mcp/"


def test_reszta_idzie_do_django():
    status, _, tresc = uruchom(
        lambda: wywolaj(_router(), zbuduj_scope("/api/v1/", metoda="GET"))
    )
    assert tresc == "DJANGO:/api/v1/"


def test_get_mcp_z_przegladarki_przekierowuje_na_slash():
    """Człowiek wkleja adres z instrukcji; bez tego SDK oddałby 406."""
    scope = zbuduj_scope("/mcp", metoda="GET", naglowki={"accept": "text/html"})
    status, naglowki, _ = uruchom(lambda: wywolaj(_router(), scope))
    assert status == 307 and naglowki["location"] == "/mcp/"


@pytest.mark.django_db(transaction=True)
def test_bearer_trafia_do_contextvara_pakietu():
    """`BppClient` czyta token z WŁASNEGO ContextVara pakietu bpp_mcp, nie
    z naszego. Bez tego mostka zalogowany użytkownik po cichu leciałby
    anonimowo, a warstwa OAuth byłaby dekoracją.

    Token musi być WAŻNY (patrz ``_token``) — bramka na ``/mcp`` przepuszcza
    anonima, ale zły/nieznany bearer odrzuca 401-ką (spec §5.4) i mock
    aplikacji MCP (``_podglada``) nigdy by nie został wywołany.
    """
    from bpp_mcp.auth import current_bearer

    _token("TOKEN-XYZ")
    widziany = []

    async def _podglada(scope, receive, send):
        widziany.append(current_bearer())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    router = RouterHttp(_podglada, _django, StartMcp(_AtrapaLifespanu()))
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN-XYZ"})
    uruchom(lambda: wywolaj(router, scope))
    assert widziany == ["TOKEN-XYZ"]


@pytest.mark.django_db(transaction=True)
def test_bearer_nie_wycieka_do_nastepnego_zadania():
    """Po zakończeniu żądania ContextVar pakietu musi być wyczyszczony."""
    from bpp_mcp.auth import current_bearer

    _token("T1")
    widziany = []

    async def _podglada(scope, receive, send):
        widziany.append(current_bearer())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def scenariusz():
        router = RouterHttp(_podglada, _django, StartMcp(_AtrapaLifespanu()))
        z_tokenem = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer T1"})
        await wywolaj(router, z_tokenem)
        await wywolaj(router, zbuduj_scope("/mcp"))

    uruchom(scenariusz)
    assert widziany == ["T1", None]


def test_lifespan_startup_complete():
    start = StartMcp(_AtrapaLifespanu())
    app = LifespanMcp(start)

    async def scenariusz():
        zdarzenia = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
        odpowiedzi = []

        async def receive():
            return zdarzenia.pop(0)

        async def send(m):
            odpowiedzi.append(m)

        await app({"type": "lifespan"}, receive, send)
        return [m["type"] for m in odpowiedzi]

    assert uruchom(scenariusz) == [
        "lifespan.startup.complete",
        "lifespan.shutdown.complete",
    ]
