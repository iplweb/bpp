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

from unittest.mock import Mock

import pytest
from django.db import OperationalError
from redis.exceptions import ConnectionError as BladRedisa

from mcp_server import routing
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


async def _wybuchaj_baza(_host):
    """Zastępuje ``host_rozstrzyga_uczelnie`` — symuluje padniętą bazę."""
    raise OperationalError("baza nie odpowiada")


def test_awaria_bazy_w_bramce_daje_503_nie_wyciekajacy_wyjatek(monkeypatch):
    """Bloker: ``host_rozstrzyga_uczelnie`` sięga do bazy, a wywołanie w
    ``_obsluz`` nie miało żadnej obsługi błędu — ``OperationalError`` wychodził
    poza aplikację ASGI jako gołe 500 bez treści i bez zgłoszenia do Rollbara
    (middleware Django nie jest na tej ścieżce). To jest NOWY tryb awarii:
    przed falą naprawczą anonimowe żądanie na ``/mcp`` wcale nie dotykało
    bazy w warstwie routingu. Ma dać kontrolowane 503, tak jak awaria startu
    menedżera (B3), z zgłoszeniem do Rollbara."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_baza)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    status, _, tresc = uruchom(lambda: wywolaj(router, zbuduj_scope("/mcp")))

    assert status == 503
    assert "MCP" not in tresc
    mock_rollbar.report_exc_info.assert_called_once()


def test_awaria_bazy_w_bramce_zglaszana_raz_na_epizod_nie_na_zadanie(monkeypatch):
    """Nie odtwarzaj B2: gdy baza leży dłużej niż jedno żądanie, Rollbar ma
    dostać JEDNO zgłoszenie na epizod awarii, a nie jedno na każde odrzucone
    żądanie w pętli — inaczej martwa baza sama wyczerpałaby kwotę Rollbara
    (tak jak `BppError` przed B2, zmierzone: 4 zgłoszenia na 4 wywołania)."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_baza)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))

    async def scenariusz():
        for _ in range(3):
            await wywolaj(router, zbuduj_scope("/mcp"))

    uruchom(scenariusz)
    mock_rollbar.report_exc_info.assert_called_once()


def test_awaria_bazy_w_bramce_zglaszana_ponownie_po_odzyskaniu(monkeypatch):
    """Po powrocie bazy do życia flaga rate-limitu wraca do zera — kolejny,
    ODRĘBNY epizod awarii musi znowu trafić do Rollbara, inaczej pierwsza
    awaria na wiele godzin uciszałaby monitoring na resztę życia workera."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_baza)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))

    async def zdrowa(_host):
        return True

    async def scenariusz():
        await wywolaj(router, zbuduj_scope("/mcp"))
        monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", zdrowa)
        await wywolaj(router, zbuduj_scope("/mcp"))
        monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_baza)
        await wywolaj(router, zbuduj_scope("/mcp"))

    uruchom(scenariusz)
    assert mock_rollbar.report_exc_info.call_count == 2


async def _wybuchaj_redis(_host):
    """Zastępuje ``host_rozstrzyga_uczelnie`` — symuluje padłego Redisa pod
    cacheops (nie bazę: to jest INNY typ wyjątku od ``_wybuchaj_baza``)."""
    raise BladRedisa("Redis nie odpowiada")


def test_awaria_redis_w_bramce_daje_503_tak_jak_awaria_bazy(monkeypatch):
    """Usterka 2c z self-review PR #804: ``sites.site`` i ``bpp.uczelnia``
    są w ``CACHEOPS`` (``production.py``), a ``CACHEOPS_DEGRADE_ON_FAILURE``
    nie jest ustawione — leżący Redis daje ``redis.exceptions.ConnectionError``
    Z SAMEGO ORM-u, nie ``django.db.Error``. Wąski ``except BladBazy`` (przed
    poprawką) tego NIE łapał, więc ta awaria wychodziła poza aplikację ASGI
    jako gołe 500 — mimo że to dokładnie ten sam epizod „infrastruktura pod
    /mcp nie odpowiada", który ``except BladBazy`` miał obsłużyć. Musi dać
    to samo kontrolowane 503 + zgłoszenie, co awaria bazy."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_redis)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    status, _, tresc = uruchom(lambda: wywolaj(router, zbuduj_scope("/mcp")))

    assert status == 503
    assert "MCP" not in tresc
    mock_rollbar.report_exc_info.assert_called_once()


def test_awaria_redis_w_bramce_zglaszana_raz_na_epizod_nie_na_zadanie(monkeypatch):
    """Rozstrzyga, KTÓRY except faktycznie złapał ``BladRedisa`` — jedno
    żądanie (test wyżej) dałoby 503 + jedno zgłoszenie NIEZALEŻNIE od tego,
    czy złapał go rate-limitowany ``except (BladBazy, BladRedisa)`` w
    ``_obsluz``, czy ogólna siatka bezpieczeństwa w ``__call__`` (ta zgłasza
    BEZ rate-limitu). Trzy żądania w tym samym epizodzie odróżniają te dwa
    przypadki: rate-limitowany except da JEDNO zgłoszenie (jak dla
    ``BladBazy`` — patrz ``test_awaria_bazy_w_bramce_zglaszana_raz_na_epizod_
    nie_na_zadanie``), a sama ogólna siatka dałaby TRZY."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_redis)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))

    async def scenariusz():
        for _ in range(3):
            await wywolaj(router, zbuduj_scope("/mcp"))

    uruchom(scenariusz)
    mock_rollbar.report_exc_info.assert_called_once()


async def _wybuchaj_niespodziewanie(_host):
    """Symuluje błąd PROGRAMISTYCZNY (np. literówkę w nowym kodzie), nie
    znaną awarię infrastruktury — ma sprawdzić SZERSZĄ siatkę bezpieczeństwa
    w ``RouterHttp.__call__``, różną od wąskiego
    ``except (BladBazy, BladRedisa)`` w ``_obsluz``."""
    raise RuntimeError("błąd programistyczny w host_rozstrzyga_uczelnie")


def test_niespodziewany_wyjatek_w_obsludze_daje_503_i_trafia_do_rollbara(
    monkeypatch,
):
    """Usterka 2c z self-review PR #804: komentarz przy wąskim
    ``except BladBazy`` uzasadniał go obawą o przykrycie błędów
    programistycznych — ale błąd programistyczny wychodzący do uvicorna jako
    gołe 500 bez Rollbara jest GORSZY niż zaraportowane 503. Siatka
    bezpieczeństwa w ``__call__`` (``except Exception``) ma złapać WSZYSTKO,
    co nie trafiło do węższych except-ów — zaraportować i odpowiedzieć
    kontrolowanym 503, a nie połknąć po cichu jako gołe 500."""
    mock_rollbar = Mock()
    monkeypatch.setattr(routing, "host_rozstrzyga_uczelnie", _wybuchaj_niespodziewanie)
    monkeypatch.setattr(routing, "rollbar", mock_rollbar)

    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    status, _, tresc = uruchom(lambda: wywolaj(router, zbuduj_scope("/mcp")))

    assert status == 503
    assert "MCP" not in tresc
    mock_rollbar.report_exc_info.assert_called_once()
