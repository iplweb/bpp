"""RouterHttp: dopasowanie DOKŁADNE + przepisanie ścieżki dla /mcp/auth.

SDK montuje trasę jako Starlette ``Route`` (regex ^/mcp$), nie ``Mount``, więc
bez przepisania ścieżki /mcp/auth dostałoby 404 (spec §5.1, bloker BL-1).
Dopasowanie prefiksowe byłoby dodatkowo sprzeczne z §8: /mcp/ ma iść do Django.
"""

import logging

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


@pytest.mark.django_db(transaction=True)
def test_mcp_trafia_do_aplikacji_mcp(uczelnia):
    """``uczelnia`` NIE jest ozdobnikiem: ``RouterHttp`` odrzuca 421-ką host,
    dla którego nie da się rozstrzygnąć uczelni (spec §7.2, patrz
    ``mcp_server.uczelnia``). Bez żadnej uczelni w bazie żądanie nigdy nie
    dotarłoby do aplikacji MCP."""
    status, _, tresc = uruchom(lambda: wywolaj(_router(), zbuduj_scope("/mcp")))
    assert status == 200 and tresc == "MCP:/mcp"


@pytest.mark.django_db(transaction=True)
def test_mcp_auth_ma_przepisana_sciezke_na_mcp(uczelnia):
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
def test_bearer_trafia_do_contextvara_pakietu(uczelnia):
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
def test_bearer_nie_wycieka_do_nastepnego_zadania(uczelnia):
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


@pytest.mark.django_db(transaction=True)
def test_schemat_zadania_z_naglowka_wskazanego_przez_ustawienie(settings, uczelnia):
    """``DaneZadania.scheme`` decyduje o ``base_url`` klienta w procesie, więc
    zły schemat to albo podwojone żądanie (``SECURE_SSL_REDIRECT``), albo
    adresy z ``http://`` w danych zwracanych użytkownikowi.

    Nazwa nagłówka MUSI pochodzić z ``SECURE_PROXY_SSL_HEADER`` — to samo
    źródło, z którego czyta ``auth.BramkaBearera``. Zaszycie
    ``X-Forwarded-Proto`` rozjechałoby warstwę MCP z Django w środowisku,
    w którym ustawienie mówi ``HTTP_X_FORWARDED_PROTOCOL`` (``base.py``).
    """
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")
    widziane = []

    async def _podglada(scope, receive, send):
        from mcp_server.kontekst import biezace

        widziane.append(biezace().scheme)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    router = RouterHttp(_podglada, _django, StartMcp(_AtrapaLifespanu()))

    async def scenariusz():
        await wywolaj(
            router,
            zbuduj_scope("/mcp", naglowki={"x-forwarded-protocol": "https"}),
        )
        # Nagłówek SPOZA ustawienia nie ma prawa podnieść schematu.
        await wywolaj(
            router, zbuduj_scope("/mcp", naglowki={"x-forwarded-proto": "https"})
        )

    uruchom(scenariusz)
    assert widziane == ["https", "http"]


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


@pytest.mark.django_db(transaction=True)
def test_naglowek_z_niepoprawnym_utf8_nie_wycieka_wyjatku(caplog, uczelnia):
    """Usterka 2a z self-review PR #804: ``curl -H $'Authorization: Bearer
    \\xff' https://<uczelnia>/mcp`` dawał ``UnicodeDecodeError`` z
    ``_dane()`` — wywoływanego w ``__call__`` PRZED jakąkolwiek siatką
    bezpieczeństwa, więc wyjątek wychodził poza aplikację ASGI jako gołe 500
    bez treści, bez wpisu w logu audytowym i bez Rollbara. Naprawa:
    ``errors="replace"``, tak jak już robi ``mcp_server.auth`` (patrz
    ``BramkaBearera._odmow``).

    Bearer po zamianie na znak zastępczy jest po prostu NIEPRAWIDŁOWYM
    tokenem — odpowiedź to zwykłe, kontrolowane 401, nie wyjątek."""
    scope = zbuduj_scope("/mcp")
    scope["headers"] = [*scope["headers"], (b"authorization", b"Bearer \xff")]

    caplog.set_level(logging.INFO, logger="mcp_server.routing")
    router = RouterHttp(_echo_sciezki, _django, StartMcp(_AtrapaLifespanu()))
    status, _, _ = uruchom(lambda: wywolaj(router, scope))

    assert status == 401
    # Wpis audytowy (spec §7.5) MUSI powstać, mimo błędu w nagłówku —
    # w buggy wersji finally nigdy nie był osiągany.
    assert any("mcp POST /mcp" in rekord.message for rekord in caplog.records)
