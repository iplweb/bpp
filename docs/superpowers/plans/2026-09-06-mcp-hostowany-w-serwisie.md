# Hostowany serwer MCP w serwisie BPP — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** BPP wystawia własny endpoint MCP pod `/mcp` (publiczny) i `/mcp/auth`
(wymagający OAuth), wykonując narzędzia z pakietu `bpp-mcp` i pobierając dane
wywołaniem własnej aplikacji Django w procesie.

**Architecture:** Do istniejącego `ProtocolTypeRouter` w `django_bpp/asgi.py`
dochodzi klucz `"lifespan"` oraz router HTTP rozdzielający `/mcp` od reszty.
Menedżer sesji MCP startuje w osobnym, długowiecznym zadaniu (bo Daphne nie
implementuje lifespanu). Każde żądanie dostaje własnego `BppClient`
skonfigurowanego na host tego żądania, wołającego `django_asgi_app` przez
`httpx.ASGITransport`.

**Tech Stack:** Django 5.2, channels 4.3, DRF 3.18, `mcp>=2,<3`
(przez `bpp-mcp>=0.4,<0.5`), `httpx`, `anyio`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-mcp-hostowany-w-serwisie-design.md`

## Global Constraints

- Wszystkie komendy przez `uv run` (`uv run pytest`, `uv run ruff …`).
- **Max długość linii: 88 znaków** (ruff).
- Komentarze i docstringi **po polsku**, w stylu repo (uzasadnienie „dlaczego").
- **NIGDY** gołe `except:` ani `except Exception: pass`.
- Testy: pytest, funkcje bez klas, `@pytest.mark.django_db`, `model_bakery.baker`.
- **Repo nie ma `pytest-asyncio`.** Korutyny odpala się przez `asyncio.run`
  w osobnym wątku (wzorzec: `src/django_bpp/tests/test_asgi_notifications.py`).
- **Nie modyfikować istniejących migracji.**
- Istniejące testy `oauth_mcp` i `api_v1` muszą przechodzić **bez zmian**.
- Nie uruchamiać `ruff check --fix` ani innych masowych auto-poprawek.
- Aplikacja MCP budowana **fabryką** `build_application()`, nigdy przy imporcie
  modułu — inaczej `settings` nadpisane w teście do niej nie dotrą.
- `ASGITransport` dostaje **`django_asgi_app`**, nigdy `application` (rekurencja).

---

## Struktura plików

```
src/mcp_server/
    __init__.py
    apps.py                 # McpServerConfig
    kontekst.py             # ContextVary + KontekstZadania + KontekstMcp
    klient.py               # BppClientInProcess + KlientScope
    auth.py                 # BramkaBearera
    routing.py              # RouterHttp + LifespanMcp
    start.py                # StartMcp
    aplikacja.py            # build_application()
    zdrowie.py              # stan dla healthchecku
    views.py                # strona /mcp/ dla człowieka
    urls.py
    templates/mcp_server/index.html
    tests/
        __init__.py
        utils.py            # uruchom(), zbuduj_scope(), wywolaj()
        test_start.py
        test_routing.py
        test_klient.py
        test_auth.py
        test_aplikacja.py
        test_bezpieczenstwo.py
        test_wielohost.py
src/oauth_mcp/views_metadata.py   # + oauth_protected_resource_metadata
src/oauth_mcp/urls.py             # + trasa PRM
src/django_bpp/asgi.py            # montaż
src/django_bpp/settings/base.py   # INSTALLED_APPS
pyproject.toml                    # bpp-mcp
```

---

## Task 1: Zależność `bpp-mcp` i szkielet aplikacji

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/django_bpp/settings/base.py` (INSTALLED_APPS)
- Create: `src/mcp_server/__init__.py`, `src/mcp_server/apps.py`
- Create: `src/mcp_server/tests/__init__.py`
- Test: `src/mcp_server/tests/test_aplikacja.py`

**Interfaces:**
- Produces: aplikacja Django `mcp_server`; dostępny import `bpp_mcp`.

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_aplikacja.py
"""Aplikacja mcp_server jest zarejestrowana, a pakiet bpp-mcp dostępny."""

from django.apps import apps


def test_aplikacja_zarejestrowana():
    assert apps.is_installed("mcp_server")


def test_pakiet_bpp_mcp_dostepny():
    from bpp_mcp import register_tools

    assert callable(register_tools)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_aplikacja.py -v`
Expected: FAIL — brak modułu `mcp_server`.

- [ ] **Step 3: Dodaj zależność**

W `pyproject.toml`, w sekcji `dependencies`, po linii z `django-multiseek`:

```toml
    # Narzędzia MCP + szwy do hostowania ich w naszym procesie (spec §2.2).
    # Ciągnie mcp>=2,<3, starlette i httpx — patrz spec §9.
    "bpp-mcp>=0.4,<0.5",
```

Następnie: `uv lock && uv sync`

- [ ] **Step 4: Utwórz aplikację**

```python
# src/mcp_server/__init__.py
"""Hostowany endpoint MCP serwisu BPP (/mcp, /mcp/auth).

Narzędzia pochodzą z pakietu ``bpp-mcp``; ta aplikacja dostarcza wyłącznie
warstwę montażu: routing ASGI, kontekst żądania, uwierzytelnianie i klienta
wołającego własną aplikację Django w procesie.
"""
```

```python
# src/mcp_server/apps.py
from django.apps import AppConfig


class McpServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mcp_server"
    verbose_name = "Serwer MCP"
```

```python
# src/mcp_server/tests/__init__.py
```

- [ ] **Step 5: Zarejestruj w INSTALLED_APPS**

W `src/django_bpp/settings/base.py`, w `INSTALLED_APPS`, bezpośrednio po
`"oauth2_provider",`:

```text
    "mcp_server",
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_aplikacja.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/django_bpp/settings/base.py src/mcp_server
git commit -m "feat(mcp_server): szkielet aplikacji + zależność bpp-mcp"
```

---

## Task 2: `StartMcp` — start menedżera sesji w osobnym zadaniu

Menedżer sesji MCP musi wejść w `session_manager.run()` dokładnie raz. Wejście
z zadania **żądania** czyni je host taskiem grupy zadań anyio — a wtedy aktywny
w tym zadaniu cancel scope (np. nasz budżet czasu) rzuca `RuntimeError` przy
wyjściu, i grupa zostaje trwale zepsuta (spec §5.1, bloker BL-3).

**Files:**
- Create: `src/mcp_server/start.py`
- Create: `src/mcp_server/tests/utils.py`
- Test: `src/mcp_server/tests/test_start.py`

**Interfaces:**
- Produces: `StartMcp(app)` z `await zapewnij()`, `wystartowany: bool`,
  `zywy: bool`.
- Produces: `mcp_server.tests.utils.uruchom(coro)` — odpala korutynę w osobnym
  wątku (repo nie ma `pytest-asyncio`).

- [ ] **Step 1: Napisz pomocnik testowy**

```python
# src/mcp_server/tests/utils.py
"""Pomocniki testowe warstwy ASGI.

Repo nie ma ``pytest-asyncio``, a ``async_to_sync`` rzuca, gdy w bieżącym
wątku biegnie już pętla (flaky zależny od kolejności testów — patrz
``django_bpp/tests/test_asgi_notifications.py``). Odpalamy więc każdą korutynę
przez ``asyncio.run`` w dedykowanym wątku ze świeżą pętlą.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor


def uruchom(coro_factory):
    """Odpal fabrykę korutyn w osobnym wątku i zwróć jej wynik.

    Przyjmujemy FABRYKĘ, nie korutynę: korutyna utworzona w wątku wołającym
    byłaby związana z jego (nieistniejącą) pętlą.
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro_factory())).result()


def zbuduj_scope(sciezka, metoda="POST", host="bpp.example.test", naglowki=None):
    """Minimalny scope HTTP/ASGI do wołania aplikacji wprost."""
    bazowe = [(b"host", host.encode())]
    for k, v in (naglowki or {}).items():
        bazowe.append((k.lower().encode(), v.encode()))
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": metoda,
        "scheme": "http",
        "path": sciezka,
        "raw_path": sciezka.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": bazowe,
        "client": ("203.0.113.7", 54321),
        "server": (host, 80),
    }


async def wywolaj(app, scope, cialo=None):
    """Zawołaj aplikację ASGI i zwróć ``(status, naglowki, tekst)``."""
    raw = json.dumps(cialo).encode() if cialo is not None else b""
    do_odebrania = [{"type": "http.request", "body": raw, "more_body": False}]
    wyslane = []

    async def receive():
        return do_odebrania.pop(0) if do_odebrania else {"type": "http.disconnect"}

    async def send(msg):
        wyslane.append(msg)

    await app(scope, receive, send)
    start = next((m for m in wyslane if m["type"] == "http.response.start"), None)
    tresc = b"".join(
        m.get("body", b"") for m in wyslane if m["type"] == "http.response.body"
    )
    naglowki = {k.decode(): v.decode() for k, v in (start or {}).get("headers", [])}
    return (start or {}).get("status"), naglowki, tresc.decode(errors="replace")
```

- [ ] **Step 2: Write the failing test**

```python
# src/mcp_server/tests/test_start.py
"""StartMcp: wejście w lifespan aplikacji MCP dokładnie raz, w osobnym zadaniu.

Kluczowa regresja (spec §5.1, bloker BL-3): wejście w grupę zadań anyio
z zadania ŻĄDANIA czyni je host taskiem; aktywny w tym zadaniu cancel scope
rzuca wtedy RuntimeError przy wyjściu, a grupa zostaje trwale zepsuta.
"""

import asyncio
from contextlib import asynccontextmanager

import anyio
import pytest

from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom


class _AplikacjaZLifespanem:
    """Namiastka aplikacji Starlette: liczy wejścia w lifespan."""

    def __init__(self, blad=None):
        self.wejscia = 0
        self._blad = blad
        self.router = self

    @asynccontextmanager
    async def lifespan_context(self, _app):
        if self._blad is not None:
            raise self._blad
        self.wejscia += 1
        yield


def test_zapewnij_wchodzi_dokladnie_raz():
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        await start.zapewnij()
        await start.zapewnij()
        await start.zapewnij()
        return start.wystartowany

    assert uruchom(scenariusz) is True
    assert app.wejscia == 1


def test_zapewnij_pod_aktywnym_cancel_scope_nie_psuje_zadania():
    """REGRESJA BL-3: wywołanie z zadania, w którym trwa fail_after, nie może
    ani wywalić tego zadania, ani zepsuć kolejnych wywołań."""
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        with anyio.fail_after(5):
            await start.zapewnij()
        # wyjście z fail_after musi się udać — i drugie wywołanie też
        await start.zapewnij()
        return app.wejscia

    assert uruchom(scenariusz) == 1


def test_blad_startu_jest_podnoszony_i_zapamietany():
    app = _AplikacjaZLifespanem(blad=RuntimeError("brak Redisa"))
    start = StartMcp(app)

    async def scenariusz():
        with pytest.raises(RuntimeError):
            await start.zapewnij()
        return start.zywy

    assert uruchom(scenariusz) is False


def test_zadanie_przezywa_zadanie_ktore_je_utworzylo():
    """Grupa zadań ma żyć dłużej niż żądanie, z którego wystartowała."""
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        async def udaje_zadanie():
            await start.zapewnij()

        await asyncio.create_task(udaje_zadanie())
        await asyncio.sleep(0.05)
        return start.zywy

    assert uruchom(scenariusz) is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_start.py -v`
Expected: FAIL — `ModuleNotFoundError: mcp_server.start`

- [ ] **Step 4: Write implementation**

```python
# src/mcp_server/start.py
"""Jednorazowe wejście w lifespan aplikacji MCP, w osobnym zadaniu.

Menedżer sesji MCP zakłada grupę zadań anyio (``session_manager.run()``).
Zadanie, które w nią wchodzi, staje się jej HOST TASKIEM — a to ma dwie
konsekwencje, przez które nie wolno robić tego z zadania obsługującego
żądanie (spec §5.1):

* jeżeli w tym zadaniu jest aktywny inny cancel scope (nasz budżet czasu),
  wyjście z niego rzuci ``RuntimeError: Attempted to exit a cancel scope that
  isn't the current task's current cancel scope`` — a grupa jest już wtedy
  oznaczona jako wystartowana, więc padają też WSZYSTKIE kolejne żądania;
* anulowanie host taska (timeout, ``application_close_timeout`` Daphne)
  zatruwa grupę nieodwracalnie, bo ``run()`` wchodzi się raz na instancję.

Dlatego host taskiem jest zadanie tła, żyjące tyle, co proces.
"""

from __future__ import annotations

import asyncio


class StartMcp:
    """Trzyma lifespan aplikacji MCP przy życiu przez cały czas życia procesu."""

    def __init__(self, aplikacja) -> None:
        self._aplikacja = aplikacja
        self._gotowe = asyncio.Event()
        self._zadanie: asyncio.Task | None = None
        self._blad: BaseException | None = None

    @property
    def wystartowany(self) -> bool:
        """Czy lifespan został pomyślnie otwarty."""
        return self._gotowe.is_set() and self._blad is None

    @property
    def zywy(self) -> bool:
        """Czy zadanie trzymające grupę nadal działa (healthcheck, spec §10.3)."""
        if self._blad is not None:
            return False
        return self._zadanie is not None and not self._zadanie.done()

    async def zapewnij(self) -> None:
        """Wystartuj menedżera sesji, jeśli jeszcze nie działa, i poczekaj.

        Idempotentne. Wołane z ``LifespanMcp`` (uvicorn) albo z pierwszego
        żądania (Daphne — nie implementuje protokołu lifespan).
        """
        if self._zadanie is None:
            # create_task nie ma punktu przerwania między testem a przypisaniem
            # w tej samej pętli, więc blokada nie jest potrzebna.
            self._zadanie = asyncio.get_running_loop().create_task(self._trzymaj())
        await self._gotowe.wait()
        if self._blad is not None:
            raise RuntimeError("Menedżer sesji MCP nie wstał") from self._blad

    async def _trzymaj(self) -> None:
        """Host task grupy zadań — czeka w nieskończoność."""
        try:
            async with self._aplikacja.router.lifespan_context(self._aplikacja):
                self._gotowe.set()
                await asyncio.Event().wait()
        except BaseException as exc:
            self._blad = exc
            self._gotowe.set()
            raise
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_start.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server/start.py src/mcp_server/tests/
git commit -m "feat(mcp_server): StartMcp — lifespan MCP w osobnym zadaniu"
```

---

## Task 3: Kontekst żądania i `KlientScope`

**Files:**
- Create: `src/mcp_server/kontekst.py`
- Create: `src/mcp_server/klient.py` (część: `KlientScope`)
- Test: `src/mcp_server/tests/test_klient.py`

**Interfaces:**
- Produces: `kontekst.dane_zadania` (ContextVar `DaneZadania | None`),
  `kontekst.DaneZadania(host, scheme, ip, bearer, deadline)`.
- Produces: `klient.KlientScope(app)` — ASGI wrapper nadpisujący
  `scope["client"]`.

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_klient.py
"""KlientScope: wewnętrzne żądanie musi nieść PRAWDZIWE IP pytającego.

httpx.ASGITransport buduje scope sam i wpisuje tam własne ``client``
(127.0.0.1). Bez podmiany wszyscy anonimowi użytkownicy MCP dzieliliby jeden
kubełek throttlingu DRF — jeden klient DoS-owałby wszystkich (spec §7.3).
"""

import pytest

from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.klient import KlientScope
from mcp_server.tests.utils import uruchom


async def _echo_client(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(scope["client"]).encode()})


def test_klient_scope_wstawia_ip_z_kontekstu():
    app = KlientScope(_echo_client)

    async def scenariusz():
        zeton = dane_zadania.set(
            DaneZadania(
                host="bpp.example.test",
                scheme="https",
                ip="198.51.100.9",
                bearer=None,
                deadline=None,
            )
        )
        try:
            wyslane = []

            async def send(m):
                wyslane.append(m)

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            await app({"type": "http", "client": ("127.0.0.1", 123)}, receive, send)
            return b"".join(m.get("body", b"") for m in wyslane).decode()
        finally:
            dane_zadania.reset(zeton)

    assert "198.51.100.9" in uruchom(scenariusz)


def test_klient_scope_bez_kontekstu_rzuca():
    """FAIL-CLOSED: brak kontekstu to błąd programisty, nie powód do cichego
    fallbacku na 127.0.0.1 (spec §5.2)."""
    app = KlientScope(_echo_client)

    async def scenariusz():
        with pytest.raises(RuntimeError):
            await app({"type": "http", "client": ("127.0.0.1", 1)}, None, None)

    uruchom(scenariusz)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_klient.py -v`
Expected: FAIL — `ModuleNotFoundError: mcp_server.kontekst`

- [ ] **Step 3: Write implementation**

```python
# src/mcp_server/kontekst.py
"""Dane zewnętrznego żądania, przenoszone do warstwy wykonującej narzędzia.

Klient MCP żyje w lifespanie (jeden na proces), a host, protokół, IP i token
zależą od KONKRETNEGO żądania. Przenosimy je ContextVarem — MCP SDK celowo
kopiuje kontekst przez granicę zadań (transport zapisuje ``copy_context()``
nadawcy, dispatcher odtwarza go przy uruchamianiu handlera), więc wartość
ustawiona w warstwie ASGI jest widoczna w kodzie narzędzia.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class DaneZadania:
    """Wszystko, czego wewnętrzne żądanie nie ma skąd wziąć samo."""

    host: str
    scheme: str
    ip: str
    bearer: str | None
    deadline: float | None  # monotoniczny znacznik końca budżetu


dane_zadania: ContextVar[DaneZadania | None] = ContextVar(
    "mcp_dane_zadania", default=None
)


def biezace() -> DaneZadania:
    """Zwróć dane bieżącego żądania albo rzuć — NIGDY nie zgaduj.

    Fallback na wartości domyślne oznaczałby ciche żądanie z nieznanego hosta,
    czyli obejście bramki API i wyciek między uczelniami (spec §7.2).
    """
    dane = dane_zadania.get()
    if dane is None:
        raise RuntimeError(
            "Brak kontekstu żądania MCP — warstwa KontekstMcp nie została "
            "uruchomiona albo ContextVar został zresetowany za wcześnie."
        )
    return dane
```

```python
# src/mcp_server/klient.py
"""Klient wołający własną aplikację Django w procesie."""

from __future__ import annotations

from mcp_server.kontekst import biezace


class KlientScope:
    """Nadpisuje ``scope["client"]`` prawdziwym IP pytającego.

    ``httpx.ASGITransport`` buduje scope wewnętrznego żądania sam i wpisuje
    tam ``("127.0.0.1", 123)``. Warstwa stojąca PRZED aplikacją MCP nie ma jak
    tego dosięgnąć — to jedyne miejsce, w którym da się to poprawić. Bez tego
    ``SearchAnonThrottle`` (liczy po IP) zlewa wszystkich anonimów do jednego
    kubełka (spec §7.3).
    """

    def __init__(self, aplikacja) -> None:
        self._aplikacja = aplikacja

    async def __call__(self, scope, receive, send):
        dane = biezace()  # fail-closed
        scope = dict(scope)
        scope["client"] = (dane.ip, 0)
        await self._aplikacja(scope, receive, send)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_klient.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/kontekst.py src/mcp_server/klient.py src/mcp_server/tests/test_klient.py
git commit -m "feat(mcp_server): kontekst żądania + KlientScope z prawdziwym IP"
```

---

## Task 4: `BppClientInProcess` — klient per żądanie z budżetem czasu

**Files:**
- Modify: `src/mcp_server/klient.py`
- Test: `src/mcp_server/tests/test_klient.py` (dopisanie)

**Interfaces:**
- Consumes: `kontekst.biezace()`, `KlientScope`.
- Produces: `klient.zbuduj_klienta() -> BppClientInProcess`,
  `klient.BppClientInProcess`.

- [ ] **Step 1: Write the failing test (dopisz do pliku)**

```python
# --- dopisz na końcu src/mcp_server/tests/test_klient.py ---

import time

import httpx

from mcp_server.klient import BppClientInProcess, zbuduj_klienta


def _dane(deadline=None, host="bpp.example.test"):
    return DaneZadania(
        host=host, scheme="https", ip="198.51.100.9", bearer=None, deadline=deadline
    )


def test_api_root_bierze_sie_z_hosta_zadania():
    """Sedno D9: adres API zależy od hosta KONKRETNEGO żądania (spec §5.3)."""

    async def scenariusz():
        zeton = dane_zadania.set(_dane(host="bpp.umlub.pl"))
        try:
            klient = zbuduj_klienta()
            return str(klient._full_url("autor/"))
        finally:
            dane_zadania.reset(zeton)

    assert uruchom(scenariusz) == "https://bpp.umlub.pl/api/v1/autor/"


def test_dwa_zadania_dwa_rozne_adresy():
    async def scenariusz():
        adresy = []
        for host in ("bpp.a.test", "bpp.b.test"):
            zeton = dane_zadania.set(_dane(host=host))
            try:
                adresy.append(str(zbuduj_klienta()._full_url("autor/")))
            finally:
                dane_zadania.reset(zeton)
        return adresy

    a, b = uruchom(scenariusz)
    assert a != b
    assert "bpp.a.test" in a and "bpp.b.test" in b


def test_przekroczony_budzet_zatrzymuje_zadania():
    """REGRESJA BL-2: po wyczerpaniu budżetu klient NIE wykonuje kolejnych
    żądań — limit ma zatrzymywać pracę, nie tylko przestać na nią czekać."""
    wywolania = []

    def handler(request):
        wywolania.append(request)
        return httpx.Response(200, json={"ok": 1})

    async def scenariusz():
        zeton = dane_zadania.set(_dane(deadline=time.monotonic() - 1))
        try:
            klient = BppClientInProcess(transport=httpx.MockTransport(handler))
            with pytest.raises(Exception):
                await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    assert wywolania == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_klient.py -v`
Expected: FAIL — `ImportError: cannot import name 'BppClientInProcess'`

- [ ] **Step 3: Write implementation (dopisz do `klient.py`)**

```python
# --- dopisz na końcu src/mcp_server/klient.py ---

import time

import httpx
from bpp_mcp.client import BppClient, BppError, TrybAuth
from bpp_mcp.config import Config


class BppClientInProcess(BppClient):
    """``BppClient`` wołający własną aplikację Django, bez gniazda TCP.

    Tworzony PER ŻĄDANIE (spec D9): ``BppClient`` zapamiętuje ``api_root``
    w ``__init__``, a adres zależy od nagłówka ``Host`` konkretnego żądania.
    Przy okazji rozwiązuje to izolację cache (świeży klient = świeży słownik)
    i sprowadza semafor do zasięgu jednego wywołania narzędzia.
    """

    def __init__(self, *, transport=None) -> None:
        dane = biezace()
        if transport is None:
            from django_bpp.asgi import django_asgi_app

            transport = httpx.ASGITransport(
                app=KlientScope(django_asgi_app),
                # 500 z aplikacji ma wrócić jako BppNetworkError z czytelnym
                # komunikatem, a nie jako surowy traceback w wyniku narzędzia.
                raise_app_exceptions=False,
            )
        super().__init__(
            Config(base_url=f"{dane.scheme}://{dane.host}", transport="stdio"),
            transport=transport,
            tryb_auth=TrybAuth.W_PROCESIE,
            max_retries=0,  # nie ma sieci, która mogłaby zamigotać
        )
        # Przekierowania WYŁĄCZONE (spec D12): SECURE_SSL_REDIRECT po cichu
        # podwajałby każde żądanie, a FirstRunWizardMiddleware przekierowuje
        # /api/v1/ na HTML kreatora, co kończyłoby się ValueError w resp.json().
        self._client.follow_redirects = False

    async def _request(self, full, *, retry_5xx=True):
        """Egzekwuj budżet czasu PRZED wykonaniem żądania.

        Limit wokół aplikacji MCP nie działa (spec §5.2, BL-2): handler biegnie
        w zadaniu grupy menedżera, więc anulowanie zadania żądania odcina tylko
        odpowiedź. Sprawdzenie musi być tutaj, gdzie faktycznie wykonuje się
        praca.
        """
        dane = biezace()
        if dane.deadline is not None and time.monotonic() >= dane.deadline:
            raise BppError(
                "Przekroczono budżet czasu wywołania narzędzia — zawęź "
                "zapytanie albo poproś o mniej danych."
            )
        if not str(full.path).startswith("/api/v1/"):
            raise BppError(f"Ścieżka spoza /api/v1/ jest niedozwolona: {full.path}")
        if full.host and full.host != dane.host:
            raise BppError(
                f"Host spoza bieżącego żądania jest niedozwolony: {full.host}"
            )
        return await super()._request(full, retry_5xx=retry_5xx)


def zbuduj_klienta() -> BppClientInProcess:
    """Zbuduj klienta dla bieżącego żądania."""
    return BppClientInProcess()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_klient.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/klient.py src/mcp_server/tests/test_klient.py
git commit -m "feat(mcp_server): BppClientInProcess per żądanie z budżetem czasu"
```

---

## Task 5: `BramkaBearera` — 401 z `WWW-Authenticate`

SDK nie zna trybu „anonim dozwolony, zły token odrzucony": `RequireAuthMiddleware`
montuje się tylko z `token_verifier` i wtedy odrzuca **każde** żądanie bez
tożsamości. Piszemy własną warstwę (spec §5.4, D10).

**Files:**
- Create: `src/mcp_server/auth.py`
- Test: `src/mcp_server/tests/test_auth.py`

**Interfaces:**
- Produces: `auth.BramkaBearera(app, *, wymagany: bool)`,
  `auth.zweryfikuj_token(raw) -> User | None` (async).

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_auth.py
"""BramkaBearera: 401 z WWW-Authenticate, przy zachowaniu dostępu anonimowego.

Bramka MUSI sprawdzać dokładnie to, co StrictOAuth2Authentication: ważność
tokenu, aktywność konta ORAZ scope ``read``. Gdyby sprawdzała mniej, token bez
scope'u przeszedłby tutaj i padł dopiero w DRF — czyli wróciłby jako błąd
w treści JSON-RPC z HTTP 200 i klient nigdy nie ponowiłby autoryzacji
(spec §5.4).
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from oauth2_provider.models import get_access_token_model, get_application_model

from mcp_server.auth import BramkaBearera
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


async def _ok(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"PRZESZLO"})


def _token(scope="read", aktywny=True, wygasly=False):
    from datetime import timedelta

    from django.utils import timezone

    user = baker.make(get_user_model(), is_active=aktywny)
    app = get_application_model().objects.create(
        name="test", client_type="public", authorization_grant_type="authorization-code"
    )
    return get_access_token_model().objects.create(
        user=user,
        application=app,
        token="TOKEN123",
        scope=scope,
        expires=timezone.now() + timedelta(seconds=-1 if wygasly else 3600),
    )


@pytest.mark.django_db(transaction=True)
def test_publiczny_bez_naglowka_przepuszcza():
    app = BramkaBearera(_ok, wymagany=False)
    status, _, tresc = uruchom(lambda: wywolaj(app, zbuduj_scope("/mcp")))
    assert status == 200 and tresc == "PRZESZLO"


@pytest.mark.django_db(transaction=True)
def test_wymagany_bez_naglowka_daje_401_z_naglowkiem():
    app = BramkaBearera(_ok, wymagany=True)
    status, naglowki, _ = uruchom(lambda: wywolaj(app, zbuduj_scope("/mcp/auth")))
    assert status == 401
    assert "resource_metadata=" in naglowki["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_zly_token_daje_401_takze_na_publicznym():
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer NIEISTNIEJE"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_token_bez_scope_read_odrzucony_juz_w_bramce():
    _token(scope="write")
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_konto_nieaktywne_odrzucone():
    _token(aktywny=False)
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_wazny_token_przechodzi():
    _token()
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, tresc = uruchom(lambda: wywolaj(app, scope))
    assert status == 200 and tresc == "PRZESZLO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: mcp_server.auth`

- [ ] **Step 3: Write implementation**

```python
# src/mcp_server/auth.py
"""Weryfikacja bearera przed aplikacją MCP.

SDK MCP montuje ``RequireAuthMiddleware`` wyłącznie przy podanym
``token_verifier``, a ten odrzuca 401-ką KAŻDE żądanie bez tożsamości — czyli
wyklucza dostęp anonimowy, na którym nam zależy. Stąd własna warstwa
(spec §5.4).
"""

from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from django.db import close_old_connections

WYMAGANY_SCOPE = "read"


def _sprawdz(raw: str) -> bool:
    """Czy token jest ważny wg TYCH SAMYCH reguł, co DRF.

    ``StrictOAuth2Authentication`` wymaga ważnego tokenu, aktywnego konta ORAZ
    scope'u ``read``. Sprawdzanie tu mniej oznaczałoby, że token bez scope'u
    przechodzi bramkę i pada dopiero w DRF — czyli wraca jako błąd w treści
    JSON-RPC z HTTP 200, a klient nigdy nie ponawia autoryzacji.
    """
    from oauth2_provider.models import get_access_token_model

    close_old_connections()  # poza cyklem żądania Django — brak sygnałów
    try:
        token = (
            get_access_token_model()
            .objects.select_related("user")
            .filter(token=raw)
            .first()
        )
        if token is None or not token.is_valid():
            return False
        if token.user is None or not token.user.is_active:
            return False
        return bool(token.allow_scopes([WYMAGANY_SCOPE]))
    finally:
        close_old_connections()


zweryfikuj_token = sync_to_async(_sprawdz, thread_sensitive=False)


class BramkaBearera:
    """Przepuszcza anonima (gdy wolno) i odrzuca nieważny token 401-ką."""

    def __init__(self, aplikacja, *, wymagany: bool) -> None:
        self._aplikacja = aplikacja
        self._wymagany = wymagany

    async def __call__(self, scope, receive, send):
        naglowki = {k.lower(): v for k, v in scope.get("headers", [])}
        surowy = naglowki.get(b"authorization", b"").decode(errors="replace")
        schemat, _, wartosc = surowy.partition(" ")

        if not surowy:
            if self._wymagany:
                await self._odmow(scope, send)
                return
            await self._aplikacja(scope, receive, send)
            return

        if schemat.lower() != "bearer" or not await zweryfikuj_token(wartosc.strip()):
            await self._odmow(scope, send)
            return

        await self._aplikacja(scope, receive, send)

    async def _odmow(self, scope, send) -> None:
        naglowki = {k.lower(): v for k, v in scope.get("headers", [])}
        host = naglowki.get(b"host", b"localhost").decode()
        schemat = "https" if scope.get("scheme") in ("https", "wss") else "http"
        prm = f"{schemat}://{host}/.well-known/oauth-protected-resource"
        cialo = json.dumps(
            {
                "error": "invalid_token",
                "error_description": "Wymagany ważny token OAuth.",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", f'Bearer resource_metadata="{prm}"'.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": cialo})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_auth.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/auth.py src/mcp_server/tests/test_auth.py
git commit -m "feat(mcp_server): BramkaBearera — 401 z PRM przy zachowaniu anonima"
```

---

## Task 6: `RouterHttp` i `LifespanMcp`

**Files:**
- Create: `src/mcp_server/routing.py`
- Test: `src/mcp_server/tests/test_routing.py`

**Interfaces:**
- Consumes: `StartMcp`, `BramkaBearera`, `kontekst.DaneZadania`.
- Produces: `routing.RouterHttp(mcp_app, django_app, start)`,
  `routing.LifespanMcp(start)`.

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_routing.py
"""RouterHttp: dopasowanie DOKŁADNE + przepisanie ścieżki dla /mcp/auth.

SDK montuje trasę jako Starlette ``Route`` (regex ^/mcp$), nie ``Mount``, więc
bez przepisania ścieżki /mcp/auth dostałoby 404 (spec §5.1, bloker BL-1).
Dopasowanie prefiksowe byłoby dodatkowo sprzeczne z §8: /mcp/ ma iść do Django.
"""

from mcp_server.routing import LifespanMcp, RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


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


def test_mcp_auth_ma_przepisana_sciezke_na_mcp():
    """REGRESJA BL-1: bez przepisania SDK oddałoby 404."""
    scope = zbuduj_scope("/mcp/auth")
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


def test_bearer_trafia_do_contextvara_pakietu():
    """`BppClient` czyta token z WŁASNEGO ContextVara pakietu bpp_mcp, nie
    z naszego. Bez tego mostka zalogowany użytkownik po cichu leciałby
    anonimowo, a warstwa OAuth byłaby dekoracją."""
    from bpp_mcp.auth import current_bearer

    widziany = []

    async def _podglada(scope, receive, send):
        widziany.append(current_bearer())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    router = RouterHttp(_podglada, _django, StartMcp(_AtrapaLifespanu()))
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN-XYZ"})
    uruchom(lambda: wywolaj(router, scope))
    assert widziany == ["TOKEN-XYZ"]


def test_bearer_nie_wycieka_do_nastepnego_zadania():
    """Po zakończeniu żądania ContextVar pakietu musi być wyczyszczony."""
    from bpp_mcp.auth import current_bearer

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_routing.py -v`
Expected: FAIL — `ModuleNotFoundError: mcp_server.routing`

- [ ] **Step 3: Write implementation**

```python
# src/mcp_server/routing.py
"""Routing ASGI: rozdział /mcp od reszty serwisu oraz obsługa lifespanu."""

from __future__ import annotations

import time

from django.conf import settings

from bpp_mcp.auth import set_current_bearer

from django_bpp.client_ip import get_client_ip
from mcp_server.auth import BramkaBearera
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.start import StartMcp

#: Budżet czasu jednego wywołania narzędzia (spec D11).
BUDZET_SEKUND = getattr(settings, "MCP_BUDZET_SEKUND", 25.0)

SCIEZKA_PUBLICZNA = "/mcp"
SCIEZKA_Z_LOGOWANIEM = "/mcp/auth"


class LifespanMcp:
    """Obsługuje scope ``lifespan``, którego ProtocolTypeRouter nie zna.

    Klucza ``"lifespan"`` po prostu nie ma dziś w mapie routera, więc uvicorn
    dostaje ValueError, loguje „lifespan appears unsupported" i jedzie dalej —
    a menedżer sesji MCP nigdy nie wstaje (spec §2.4).
    """

    def __init__(self, start: StartMcp) -> None:
        self._start = start

    async def __call__(self, scope, receive, send):
        while True:
            komunikat = await receive()
            if komunikat["type"] == "lifespan.startup":
                try:
                    await self._start.zapewnij()
                except Exception as exc:
                    # Świadomie NIE połykamy: pod gunicornem worker padnie
                    # i zostanie respawnowany, czyli awaria będzie widoczna
                    # jako boot-loop, a nie jako cisza (spec §5.1).
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif komunikat["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


class RouterHttp:
    """Kieruje ``/mcp`` i ``/mcp/auth`` do MCP, resztę do Django."""

    def __init__(self, mcp_app, django_app, start: StartMcp) -> None:
        self._django = django_app
        self._start = start
        self._publiczny = BramkaBearera(mcp_app, wymagany=False)
        self._z_logowaniem = BramkaBearera(mcp_app, wymagany=True)

    async def __call__(self, scope, receive, send):
        sciezka = scope.get("path", "")
        if sciezka not in (SCIEZKA_PUBLICZNA, SCIEZKA_Z_LOGOWANIEM):
            await self._django(scope, receive, send)
            return

        if scope.get("method") == "GET" and self._chce_html(scope):
            await self._przekieruj(send, "/mcp/")
            return

        # PIERWSZA instrukcja i POZA jakimkolwiek cancel scope'em (spec §5.1).
        await self._start.zapewnij()
        if not self._start.zywy:
            await self._niedostepny(send)
            return

        dane = self._dane(scope)
        zeton = dane_zadania.set(dane)
        # DWA ContextVary, nie jeden. `BppClient._auth_kwargs` czyta token
        # z WŁASNEGO ContextVara pakietu bpp_mcp (`bpp_mcp.auth`), nie
        # z naszego. Bez tej linii `DaneZadania.bearer` nie ma żadnej drogi
        # do żądania wychodzącego i KAŻDE wywołanie leci anonimowo — czyli
        # zalogowany użytkownik po cichu traci dostęp do swoich danych,
        # a cała warstwa OAuth staje się dekoracją.
        set_current_bearer(dane.bearer)
        try:
            if sciezka == SCIEZKA_Z_LOGOWANIEM:
                # SDK montuje trasę jako Route (^/mcp$), nie Mount — bez
                # przepisania drugi adres dostałby 404 (spec §5.1, BL-1).
                scope = dict(scope, path=SCIEZKA_PUBLICZNA, raw_path=b"/mcp")
                await self._z_logowaniem(scope, receive, send)
            else:
                await self._publiczny(scope, receive, send)
        finally:
            dane_zadania.reset(zeton)
            # set_current_bearer nie zwraca tokenu resetu, więc czyścimy
            # jawnie — inaczej token wyciekłby do następnego żądania
            # obsłużonego w tym samym kontekście.
            set_current_bearer(None)

    @staticmethod
    def _chce_html(scope) -> bool:
        for klucz, wartosc in scope.get("headers", []):
            if klucz.lower() == b"accept" and b"text/html" in wartosc.lower():
                return True
        return False

    @staticmethod
    def _dane(scope) -> DaneZadania:
        # Klucze nagłówków w ASGI to BYTES — bez .decode() na kluczu
        # każdy odczyt po stringu chybia i bearer cicho ginie.
        naglowki = {k.lower().decode(): v.decode() for k, v in scope.get("headers", [])}
        host = naglowki.get("host", "localhost")
        # nginx→uvicorn jest plaintext; prawdziwy schemat niesie
        # X-Forwarded-Proto (spec §7.6). Nagłówka NIE przekazujemy dalej —
        # służy wyłącznie do zbudowania adresu bazowego.
        scheme = naglowki.get("x-forwarded-proto", scope.get("scheme", "http"))
        bearer = None
        surowy = naglowki.get("authorization", "")
        if surowy.lower().startswith("bearer "):
            bearer = surowy.split(" ", 1)[1].strip()
        return DaneZadania(
            host=host,
            scheme="https" if scheme == "https" else "http",
            ip=get_client_ip(_UdajeRequest(scope, naglowki)),
            bearer=bearer,
            deadline=time.monotonic() + BUDZET_SEKUND,
        )

    @staticmethod
    async def _przekieruj(send, gdzie: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [(b"location", gdzie.encode())],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    @staticmethod
    async def _niedostepny(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {"type": "http.response.body", "body": b'{"error":"mcp_unavailable"}'}
        )


class _UdajeRequest:
    """Minimalny obiekt zgodny z tym, czego oczekuje ``get_client_ip``."""

    def __init__(self, scope, naglowki):
        klient = scope.get("client") or ("", 0)
        self.META = {"REMOTE_ADDR": klient[0]}
        xff = naglowki.get("x-forwarded-for")
        if xff:
            self.META["HTTP_X_FORWARDED_FOR"] = xff
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_routing.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/routing.py src/mcp_server/tests/test_routing.py
git commit -m "feat(mcp_server): RouterHttp z przepisaniem /mcp/auth + LifespanMcp"
```

---

## Task 7: `build_application()` — aplikacja MCP z narzędziami

**Files:**
- Create: `src/mcp_server/aplikacja.py`
- Test: `src/mcp_server/tests/test_aplikacja.py` (dopisanie)

**Interfaces:**
- Consumes: `zbuduj_klienta`, `StartMcp`, `RouterHttp`, `LifespanMcp`.
- Produces: `aplikacja.build_application() -> (mcp_app, start)`,
  `aplikacja.KontekstZadania`.

- [ ] **Step 1: Write the failing test (dopisz do pliku)**

```python
# --- dopisz na końcu src/mcp_server/tests/test_aplikacja.py ---

from mcp_server.aplikacja import build_application
from mcp_server.tests.utils import uruchom


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_aplikacja.py -v`
Expected: FAIL — `ModuleNotFoundError: mcp_server.aplikacja`

- [ ] **Step 3: Write implementation**

```python
# src/mcp_server/aplikacja.py
"""Budowa aplikacji MCP: serwer SDK + narzędzia z bpp-mcp + polityka hostów."""

from __future__ import annotations

from contextlib import asynccontextmanager

from bpp_mcp import register_tools
from django.conf import settings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.klient import zbuduj_klienta
from mcp_server.start import StartMcp


class KontekstZadania:
    """Kontrakt lifespanu ``register_tools``, ale klient jest PER ŻĄDANIE.

    ``register_tools`` dokumentuje, że lifespan ma oddać ``KontekstApp`` *albo
    obiekt o tych samych atrybutach*. Korzystamy z tej furtki: ``client`` jest
    property, więc wrappery narzędzi — które czytają go przy każdym wywołaniu —
    dostają klienta zbudowanego dla bieżącego żądania (spec D9).
    """

    #: Host wielo-użytkownikowy: token jednej osoby nie może trafić do żądania
    #: innej, więc NIGDY nie sięgamy do lokalnego cache tokenów.
    bearer_provider = None

    @property
    def client(self):
        return zbuduj_klienta()


def _dozwolone_hosty() -> list[str]:
    """Przetłumacz ``ALLOWED_HOSTS`` na semantykę SDK.

    SDK dopasowuje host dokładnie albo wzorcem ``host:*`` — Django-owe
    ``.domena`` i ``*`` nie działają (spec §6.1). ``*`` w ALLOWED_HOSTS
    (używane w testach) mapujemy na wyłączenie sprawdzania, bo nie ma dla
    niego odpowiednika.
    """
    hosty: list[str] = []
    for wpis in settings.ALLOWED_HOSTS:
        if wpis == "*":
            return []
        hosty.append(wpis.lstrip("."))
        hosty.append(f"{wpis.lstrip('.')}:*")
    return hosty


def build_application():
    """Zbuduj aplikację ASGI serwera MCP i jej ``StartMcp``.

    FABRYKA, nie moduł: allowlista hostów jest liczona z ``settings``, więc
    zbudowanie aplikacji przy imporcie uniemożliwiłoby testom nadpisanie
    ``ALLOWED_HOSTS`` (spec §11).
    """

    @asynccontextmanager
    async def lifespan(_serwer):
        yield KontekstZadania()

    serwer = MCPServer("bpp", version="1", lifespan=lifespan)
    register_tools(serwer)

    hosty = _dozwolone_hosty()
    bezpieczenstwo = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(hosty),
        allowed_hosts=hosty,
        allowed_origins=[f"https://{h}" for h in hosty if not h.endswith(":*")],
    )

    aplikacja = serwer.streamable_http_app(
        streamable_http_path="/mcp",
        # Bezstanowo: recykling workera (--max-requests) zabiłby sesję
        # stateful w środku pracy użytkownika. json_response znosi SSE, więc
        # proxy_read_timeout nginksa przestaje być tematem (spec D3).
        stateless_http=True,
        json_response=True,
        transport_security=bezpieczenstwo,
    )
    aplikacja.state.serwer_mcp = serwer
    return aplikacja, StartMcp(aplikacja)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_aplikacja.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/aplikacja.py src/mcp_server/tests/test_aplikacja.py
git commit -m "feat(mcp_server): build_application z narzędziami i polityką hostów"
```

---

## Task 8: Montaż w `asgi.py` — test end-to-end

**Files:**
- Modify: `src/django_bpp/asgi.py`
- Test: `src/mcp_server/tests/test_e2e.py`

**Interfaces:**
- Consumes: `build_application`, `RouterHttp`, `LifespanMcp`.
- Produces: `django_bpp.asgi.application` z kluczem `"lifespan"`.

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_e2e.py
"""Pełna ścieżka: POST /mcp → initialize → tools/list, bez sieci."""

import pytest

from mcp_server.aplikacja import build_application
from mcp_server.routing import RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _router(settings):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    mcp_app, start = build_application()
    return RouterHttp(mcp_app, _django, start)


@pytest.mark.django_db(transaction=True)
def test_initialize_zwraca_serverinfo(settings):
    router = _router(settings)
    scope = zbuduj_scope(
        "/mcp",
        naglowki={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
    )
    cialo = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }
    status, _, tresc = uruchom(lambda: wywolaj(router, scope, cialo))
    assert status == 200
    assert '"serverInfo"' in tresc and '"bpp"' in tresc


@pytest.mark.django_db(transaction=True)
def test_zle_host_daje_421(settings):
    """Ochrona przed DNS-rebinding SDK działa niezależnie od ALLOWED_HOSTS."""
    router = _router(settings)
    scope = zbuduj_scope(
        "/mcp",
        host="zly.host",
        naglowki={"content-type": "application/json"},
    )
    status, _, _ = uruchom(
        lambda: wywolaj(router, scope, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
    )
    assert status in (403, 421)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_e2e.py -v`
Expected: FAIL — brak `state.serwer_mcp` / brak montażu.

- [ ] **Step 3: Zmodyfikuj `src/django_bpp/asgi.py`**

Zastąp blok `application = ProtocolTypeRouter({...})` na końcu pliku:

```python
# Aplikacja MCP i jej routing. Import PO get_asgi_application() — mcp_server
# sięga po modele przez klienta w procesie.
from mcp_server.aplikacja import build_application  # noqa: E402
from mcp_server.routing import LifespanMcp, RouterHttp  # noqa: E402

_mcp_app, _mcp_start = build_application()

application = ProtocolTypeRouter(
    {
        "http": RouterHttp(_mcp_app, django_asgi_app, _mcp_start),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
        # ProtocolTypeRouter nie „nie obsługuje" lifespanu — po prostu nie ma
        # dla niego klucza i rzuca ValueError, który uvicorn loguje jako
        # „appears unsupported" i ignoruje. Menedżer sesji MCP nigdy wtedy nie
        # wstaje (spec §2.4, §5.1).
        "lifespan": LifespanMcp(_mcp_start),
    }
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_e2e.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Sprawdź, że nic się nie zepsuło**

Run: `uv run pytest src/django_bpp/tests/ src/oauth_mcp/ -q`
Expected: PASS bez zmian w tych plikach.

- [ ] **Step 6: Commit**

```bash
git add src/django_bpp/asgi.py src/mcp_server/tests/test_e2e.py
git commit -m "feat(asgi): zamontuj /mcp obok Django, dopisz klucz lifespan"
```

---

## Task 9: Metadane Protected Resource (RFC 9728)

**Files:**
- Modify: `src/oauth_mcp/views_metadata.py`
- Modify: `src/oauth_mcp/urls.py`
- Test: `src/oauth_mcp/tests/test_metadata_prm.py`

**Interfaces:**
- Produces: `GET /.well-known/oauth-protected-resource`.

- [ ] **Step 1: Write the failing test**

```python
# src/oauth_mcp/tests/test_metadata_prm.py
"""PRM (RFC 9728) — wskazuje klientowi, gdzie jest serwer autoryzacji."""

import pytest


@pytest.mark.django_db
def test_prm_zwraca_wlasciwe_urle(client):
    odp = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="bpp.example.test"
    )
    assert odp.status_code == 200
    dane = odp.json()
    assert dane["resource"] == "http://bpp.example.test/mcp"
    assert dane["authorization_servers"] == ["http://bpp.example.test"]
    assert dane["scopes_supported"] == ["read"]


@pytest.mark.django_db
def test_prm_jest_per_host(client):
    """Wielo-domenowość: każda uczelnia widzi swój adres."""
    a = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="uczelnia1.localhost"
    ).json()
    b = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="uczelnia2.localhost"
    ).json()
    assert a["resource"] != b["resource"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/oauth_mcp/tests/test_metadata_prm.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Dopisz widok do `src/oauth_mcp/views_metadata.py`**

```python
def oauth_protected_resource_metadata(request):
    """RFC 9728 — mówi klientowi MCP, który serwer autoryzacji obsługuje /mcp.

    Poprzedni spec przypisywał ten dokument pakietowi bpp-mcp; odkąd Resource
    Serverem jest sama instancja BPP, mieszka on tutaj. URL-e przez
    build_absolute_uri — poprawny scheme z SECURE_PROXY_SSL_HEADER, host
    per-request (wielo-domenowość).
    """
    return JsonResponse(
        {
            "resource": request.build_absolute_uri("/mcp"),
            "authorization_servers": [request.build_absolute_uri("/").rstrip("/")],
            "scopes_supported": ["read"],
            "bearer_methods_supported": ["header"],
        }
    )
```

- [ ] **Step 4: Dopisz trasę w `src/oauth_mcp/urls.py`**

W `urlpatterns`, po wpisie `oauth-as-metadata`:

```text
    path(
        ".well-known/oauth-protected-resource",
        oauth_protected_resource_metadata,
        name="oauth-prm",
    ),
```

oraz rozszerz import na górze pliku:

```python
from oauth_mcp.views_metadata import (
    oauth_authorization_server_metadata,
    oauth_protected_resource_metadata,
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/oauth_mcp/tests/test_metadata_prm.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/oauth_mcp/views_metadata.py src/oauth_mcp/urls.py src/oauth_mcp/tests/test_metadata_prm.py
git commit -m "feat(oauth_mcp): metadane protected-resource (RFC 9728)"
```

---

## Task 10: Strona `/mcp/` dla człowieka

**Files:**
- Create: `src/mcp_server/views.py`, `src/mcp_server/urls.py`
- Create: `src/mcp_server/templates/mcp_server/index.html`
- Modify: `src/django_bpp/urls.py`
- Test: `src/mcp_server/tests/test_strona.py`

- [ ] **Step 1: Write the failing test**

```python
# src/mcp_server/tests/test_strona.py
"""Strona /mcp/ — instrukcja podłączenia dla człowieka."""

import pytest


@pytest.mark.django_db
def test_strona_pokazuje_oba_adresy(client):
    odp = client.get("/mcp/", HTTP_HOST="bpp.example.test")
    assert odp.status_code == 200
    tresc = odp.content.decode()
    assert "http://bpp.example.test/mcp" in tresc
    assert "http://bpp.example.test/mcp/auth" in tresc


@pytest.mark.django_db
def test_adresy_sa_per_host(client):
    a = client.get("/mcp/", HTTP_HOST="uczelnia1.localhost").content.decode()
    assert "uczelnia1.localhost/mcp" in a
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/mcp_server/tests/test_strona.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Write implementation**

```python
# src/mcp_server/views.py
from django.views.generic import TemplateView


class StronaMcp(TemplateView):
    """Instrukcja podłączenia klienta AI — adresy składane per host."""

    template_name = "mcp_server/index.html"

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        kontekst["adres_publiczny"] = self.request.build_absolute_uri("/mcp")
        kontekst["adres_z_logowaniem"] = self.request.build_absolute_uri("/mcp/auth")
        return kontekst
```

```python
# src/mcp_server/urls.py
from django.urls import path

from mcp_server.views import StronaMcp

app_name = "mcp_server"

urlpatterns = [
    path("", StronaMcp.as_view(), name="strona"),
]
```

```html
{# src/mcp_server/templates/mcp_server/index.html #}
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<div class="row">
  <div class="large-12 columns">
    <h1>{% trans "Bibliografia w Twoim asystencie AI" %}</h1>

    <p>{% trans "Wklej adres poniżej do klienta AI obsługującego zdalne serwery MCP." %}</p>

    <h2>{% trans "Dostęp publiczny" %}</h2>
    <p><code>{{ adres_publiczny }}</code></p>
    <p>{% trans "Bez logowania. Widzi to samo, co publiczna część bibliografii." %}</p>

    <h2>{% trans "Dostęp z logowaniem" %}</h2>
    <p><code>{{ adres_z_logowaniem }}</code></p>
    <p>{% trans "Poprosi o zalogowanie w przeglądarce. Odblokowuje dane niepubliczne." %}</p>

    <h2>{% trans "Claude Code" %}</h2>
    <pre>claude mcp add bpp --transport http {{ adres_publiczny }}</pre>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Zamontuj w `src/django_bpp/urls.py`**

W `urlpatterns`, obok innych `path(...)`:

```text
        path("mcp/", include("mcp_server.urls", namespace="mcp_server")),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/mcp_server/tests/test_strona.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server/views.py src/mcp_server/urls.py src/mcp_server/templates src/django_bpp/urls.py src/mcp_server/tests/test_strona.py
git commit -m "feat(mcp_server): strona /mcp/ z instrukcją podłączenia"
```

---

## Task 11: Testy bezpieczeństwa i wielo-hostowe

Każdy z tych testów pilnuje konkretnej dziury z recenzji specu. Bez nich
projekt nie ma prawa wejść.

**Files:**
- Test: `src/mcp_server/tests/test_bezpieczenstwo.py`
- Test: `src/mcp_server/tests/test_wielohost.py`

- [ ] **Step 1: Write the tests**

```python
# src/mcp_server/tests/test_bezpieczenstwo.py
"""Regresje bezpieczeństwa warstwy /mcp (spec §7)."""

import httpx
import pytest

from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.klient import BppClientInProcess
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
    """Cookie uwierzytelniłoby sesją przez SessionAuthentication — z pełnymi
    uprawnieniami, bez zgody, bez scope i bez revoke (spec §7.1)."""
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
    """BasicAuthentication jest trzecia w DEFAULT_AUTHENTICATION_CLASSES,
    a ApiReadOnlyForBearerMiddleware sprawdza tylko prefiks 'bearer ', więc
    dla Basica warstwa read-only NIE istnieje (spec §7.1)."""
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
            with pytest.raises(Exception):
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
            with pytest.raises(Exception):
                await klient.get_json("https://bpp.zly.test/api/v1/autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
```

```python
# src/mcp_server/tests/test_wielohost.py
"""Wewnętrzne żądanie musi nieść Host zewnętrznego — inaczej Uczelnia=None,
BramkaApiV1 przepuszcza bezwarunkowo i wyciekają ukryte statusy (spec §7.2)."""

import pytest

from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.klient import BppClientInProcess
from mcp_server.tests.utils import uruchom

pytestmark = pytest.mark.django_db(transaction=True)


def _pobierz(host):
    async def scenariusz():
        zeton = dane_zadania.set(
            DaneZadania(
                host=host, scheme="http", ip="198.51.100.9", bearer=None, deadline=None
            )
        )
        try:
            klient = BppClientInProcess()
            return await klient.get_json("uczelnia/")
        finally:
            dane_zadania.reset(zeton)

    return uruchom(scenariusz)


def test_kazdy_host_widzi_swoja_uczelnie(settings, uczelnia1, uczelnia2):
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    a = _pobierz("uczelnia1.localhost")
    b = _pobierz("uczelnia2.localhost")
    assert a["results"][0]["nazwa"] != b["results"][0]["nazwa"]


def test_wylaczone_api_odmawia_takze_przez_mcp(settings, uczelnia1):
    """Dowód, że BramkaApiV1 działa na tej ścieżce."""
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost"]
    uczelnia1.api_v1_wlaczone = False
    uczelnia1.save(update_fields=["api_v1_wlaczone"])
    with pytest.raises(Exception):
        _pobierz("uczelnia1.localhost")
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest src/mcp_server/tests/test_bezpieczenstwo.py src/mcp_server/tests/test_wielohost.py -v`
Expected: PASS. Jeśli któryś padnie — **to jest realna dziura**, napraw kod,
nie test.

- [ ] **Step 3: Commit**

```bash
git add src/mcp_server/tests/test_bezpieczenstwo.py src/mcp_server/tests/test_wielohost.py
git commit -m "test(mcp_server): regresje bezpieczeństwa i wielo-hostowe"
```

---

## Task 12: Rollbar, healthcheck, newsfragment, dokumentacja

**Files:**
- Modify: `src/mcp_server/aplikacja.py` (wrapper Rollbar)
- Create: `src/mcp_server/zdrowie.py`
- Create: `src/bpp/newsfragments/mcp-hostowany.feature.rst`
- Modify: `docs/deweloper/mapa-kodu.md`

- [ ] **Step 1: Wrapper Rollbar w `aplikacja.py`**

SDK zamienia każdy wyjątek narzędzia na `CallToolResult(is_error=True)`, więc
do warstwy ASGI **nic nie dociera** — bez tego awarie narzędzi są całkowicie
niewidoczne w monitoringu (spec §7.5).

Dopisz przed `register_tools(serwer)`:

```python
def _z_raportowaniem(serwer):
    """Owija zarejestrowane narzędzia raportowaniem do Rollbara.

    SDK przechwytuje wyjątki handlerów i zamienia je na wynik z flagą błędu,
    więc CustomRollbarNotifierMiddleware ich nie zobaczy — musimy zgłosić je
    sami, zanim SDK je pochłonie (spec §7.5).
    """
    import functools

    import rollbar

    oryginalny = serwer.tool

    def tool(*args, **kwargs):
        dekorator = oryginalny(*args, **kwargs)

        def opakuj(fn):
            @functools.wraps(fn)
            async def wrapper(*a, **kw):
                try:
                    return await fn(*a, **kw)
                except Exception:
                    rollbar.report_exc_info()
                    raise

            return dekorator(wrapper)

        return opakuj

    serwer.tool = tool
    return serwer
```

i zmień wywołanie na:

```text
    register_tools(_z_raportowaniem(serwer))
```

- [ ] **Step 2: Healthcheck**

```python
# src/mcp_server/zdrowie.py
"""Stan endpointu MCP dla monitoringu.

Grupa zadań menedżera może zostać zatruta wyjątkiem dziecka — proces wtedy
żyje, ale każde /mcp zwraca błąd aż do recyklingu workera. Healthcheck musi
więc odróżniać „proces działa" od „endpoint MCP działa" (spec §10.3).
"""

from __future__ import annotations


def stan_mcp() -> dict:
    """Zwróć stan startu serwera MCP."""
    from django_bpp.asgi import _mcp_start

    return {
        "wystartowany": _mcp_start.wystartowany,
        "zywy": _mcp_start.zywy,
    }
```

- [ ] **Step 3: Newsfragment**

```rst
.. src/bpp/newsfragments/mcp-hostowany.feature.rst

Serwis wystawia własny serwer MCP pod adresem ``/mcp`` (publiczny) oraz
``/mcp/auth`` (z logowaniem OAuth). Asystenci AI obsługujący zdalne serwery
MCP łączą się jednym adresem — bez instalowania czegokolwiek i bez podawania
adresu uczelni. Instrukcja podłączenia jest na stronie ``/mcp/``.
```

- [ ] **Step 4: Uruchom pełną suitę**

```bash
uv run pytest src/mcp_server/ src/oauth_mcp/ src/api_v1/ -q
uv run ruff format .
uv run ruff check .
uv run pre-commit
```

Expected: wszystko zielone. **`pre-commit` bez argumentów.**

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/ src/bpp/newsfragments/ docs/
git commit -m "feat(mcp_server): raportowanie błędów narzędzi, healthcheck, newsfragment"
```

---

## Self-review planu

**Pokrycie specu.** §1 → Task 10 (strona z oboma adresami). §2 → kontekst,
nie kod. §4 D1 → Task 1+7; D2 → Task 2+6+8; D3 → Task 7; D4/D9/D12 → Task 4;
D5 → Task 3+6; D6 → Task 11; D7/D10 → Task 5+6; D8 → narzędzia są read-only
z pakietu; D11 → Task 4+6. §5 → Tasks 2–8. §6 → Task 9 + `_dozwolone_hosty`
w Task 7. §7 → Task 11 (+ §7.5 w Task 12). §8 → Task 10. §9 → Task 1.
§10 → Task 12 (healthcheck); ModSecurity i `limit_req` są w `bpp-deploy`,
poza tym repo — **do zgłoszenia przy wdrożeniu, odnotowane w §15 specu**.
§11 → Tasks 2–11. §12 → kryteria pokryte testami.

**Placeholdery.** Brak — każdy krok ma kod albo dokładną komendę.

**Spójność typów.** `StartMcp.zapewnij/wystartowany/zywy` używane w Task 6, 8
i 12 zgodnie z definicją z Task 2. `DaneZadania(host, scheme, ip, bearer,
deadline)` konstruowane identycznie w Taskach 3, 4, 6, 11. `build_application()`
zwraca krotkę `(aplikacja, start)` — rozpakowywaną tak samo w Taskach 7 i 8.

**Luka świadoma:** `limit_req` i ModSecurity wymagają zmian w repozytorium
`bpp-deploy`; nie da się ich wykonać w tym planie. Wchodzą jako osobne
zadanie wdrożeniowe po scaleniu.
