# Przełączniki konfiguracyjne REST API `/api/v1/` — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozbudować pojedynczy przełącznik `Uczelnia.api_v1_wlaczone` do sześciu pól konfiguracyjnych (ograniczenie do zalogowanych + cztery grupy endpointów), tak żeby administrator instalacji mógł wyłączyć dowolną część REST API, a domyślnie nic się nie zmieniało.

**Architecture:** Bramka `BramkaApiV1` (DRF `BasePermission`) doklejana do każdego viewsetu przez podmieniony `CustomRouter`, z grupą deklarowaną jako wymagany kwarg przy rejestracji. Odpowiedzi odmowne niosą klucz `powod`, po którym widget do osadzania odróżnia decyzję administratora od nieistniejącej encji. Endpointy kafelkowe dostają nagłówki CORS także na odpowiedziach błędów.

**Tech Stack:** Django 5.x, Django REST Framework 3.17, pytest + model_bakery, vitest + jsdom, PostgreSQL (testcontainers).

**Spec:** `docs/superpowers/specs/2026-08-05-api-v1-przelaczniki-design.md`

**Worktree:** `~/Programowanie/bpp-api-v1-przelaczniki`, gałąź `feat/api-v1-przelaczniki`, odgałęziona od `dev` @ `2bf58407d`.

## Global Constraints

- **Wszystkie polecenia Pythona przez `uv run`.** Nigdy gołe `python`/`pytest`.
- **Max długość linii: 88 znaków** (egzekwowane przez ruff).
- **NIGDY nie modyfikuj istniejących plików migracji** w `src/*/migrations/`.
- **Zakaz `except: pass` i `except Exception: pass`** — każdy `except` loguje, re-raise'uje albo zwraca sensowny błąd.
- **Testy w konwencji pytest** — funkcje, bez klas, `@pytest.mark.django_db` dla bazy, `model_bakery.baker.make` do obiektów.
- **Komentarze Django `{# … #}` są jednoliniowe** — każda linia własne otwarcie i zamknięcie.
- **Nowe pola `BooleanField` mają defaulty zachowujące obecne zachowanie**: `api_v1_tylko_zalogowani=False`, wszystkie cztery grupy `True`.
- **Baseline odświeżamy wyłącznie przez `make baseline-update`** — nigdy gołe `manage.py baseline_update` (pomija `fix-baseline-search-path`, przez co kontener testowej bazy nie wstaje).
- **Pre-commit: poprawki ręcznie przez Edit**, nigdy `ruff check --fix` ani batch-fixy.
- Teksty użytkownika po polsku.

## File Structure

| Plik | Odpowiedzialność | Akcja |
|---|---|---|
| `src/bpp/models/uczelnia.py` | enum `GrupaApiV1`, pięć nowych pól, metoda `api_v1_grupa_wlaczona` | modyfikacja |
| `src/bpp/migrations/0480_api_v1_przelaczniki.py` | `AddField` × 5 | utworzenie (przez `makemigrations`) |
| `src/api_v1/permissions.py` | bramka z grupami, komunikaty, klucz `powod` | modyfikacja |
| `src/api_v1/urls.py` | `CustomRouter` z wymaganym `grupa=`, mapa prefiks→grupa, przypisanie 37 prefiksów | modyfikacja |
| `src/api_v1/views.py` | filtr listingu root wg włączonych grup | modyfikacja |
| `src/api_v1/viewsets/recent_publications_common.py` | `CorsNaBledachMixin` | modyfikacja |
| `src/api_v1/viewsets/recent_author_publications.py` | użycie mixina | modyfikacja |
| `src/api_v1/viewsets/recent_unit_publications.py` | użycie mixina | modyfikacja |
| `src/bpp/admin/uczelnia.py` | przeniesiony i przemianowany fieldset | modyfikacja |
| `src/django_bpp/templates/multiseek/common-results.html` | warunkowe linki do API | modyfikacja |
| `src/bpp/static/embed/bpp-publikacje.js` | rozróżnianie 404 po `powod` | modyfikacja |
| `src/api_v1/tests/test_przelaczniki.py` | testy wszystkich przełączników | utworzenie |
| `src/cerif_export/tests/test_przelaczniki.py` | zostaje sama część CERIF | modyfikacja |
| `tests/js/embed-publikacje.test.js` | testy widgetu | utworzenie |
| `docs/administrator/rest-api.md` | dokumentacja administratora | utworzenie |
| `mkdocs.yml` | wpis w nawigacji | modyfikacja |
| `src/bpp/newsfragments/api-v1-przelaczniki.feature.rst` | newsfragment | utworzenie |
| `baseline-sql/baseline.sql`, `baseline-sql/baseline.meta.json` | odświeżony baseline | regeneracja |

---

### Task 1: Model — enum grup, pięć pól, migracja, baseline

**Files:**
- Modify: `src/bpp/models/uczelnia.py` (okolice linii 586 — pole `api_v1_wlaczone`)
- Create: `src/api_v1/tests/test_przelaczniki.py`
- Regenerate: `baseline-sql/baseline.sql`, `baseline-sql/baseline.meta.json`

**Interfaces:**
- Produces: `bpp.models.uczelnia.GrupaApiV1` (`models.TextChoices` o wartościach `dane_bibliograficzne`, `wyszukiwanie`, `kafelki`, `narzedzia_redaktorskie`); pola `Uczelnia.api_v1_tylko_zalogowani`, `api_v1_dane_bibliograficzne`, `api_v1_wyszukiwanie`, `api_v1_kafelki`, `api_v1_narzedzia_redaktorskie`; metoda `Uczelnia.api_v1_grupa_wlaczona(grupa: GrupaApiV1) -> bool`.

- [ ] **Step 1: Napisz failujące testy modelu**

Utwórz `src/api_v1/tests/test_przelaczniki.py`:

```python
"""Przełączniki konfiguracyjne REST API ``/api/v1/`` na obiekcie ``Uczelnia``.

Sześć pól: główny wyłącznik, ograniczenie do zalogowanych i cztery grupy
endpointów. Wszystkie defaulty zachowują dotychczasowe zachowanie — jedyne
domyślnie wyłączone to ograniczenie do zalogowanych.
"""

import pytest

from bpp.models import Uczelnia
from bpp.models.uczelnia import GrupaApiV1


def test_defaulty_zachowuja_obecne_zachowanie(uczelnia):
    """Wdrożenie sprzed tej zmiany nie traci żadnej funkcji."""
    assert uczelnia.api_v1_wlaczone is True
    assert uczelnia.api_v1_dane_bibliograficzne is True
    assert uczelnia.api_v1_wyszukiwanie is True
    assert uczelnia.api_v1_kafelki is True
    assert uczelnia.api_v1_narzedzia_redaktorskie is True


def test_tylko_zalogowani_domyslnie_wylaczone(uczelnia):
    """Jedyne pole, którego włączenie zmienia zachowanie — więc domyślnie
    wyłączone."""
    assert uczelnia.api_v1_tylko_zalogowani is False


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_kazda_grupa_ma_pole_na_uczelni(grupa):
    """Wartość enuma jest sufiksem nazwy pola (``api_v1_<value>``).

    Wiązanie idzie przez ``getattr``, więc nie ma kontroli statycznej —
    literówka w enumie wybuchłaby dopiero na produkcji, przy pierwszym
    żądaniu do danej grupy.
    """
    assert hasattr(Uczelnia, f"api_v1_{grupa.value}")


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_api_v1_grupa_wlaczona_czyta_wlasciwe_pole(uczelnia, grupa):
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is True

    setattr(uczelnia, f"api_v1_{grupa.value}", False)
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is False
```

- [ ] **Step 2: Uruchom testy — mają paść**

```bash
cd ~/Programowanie/bpp-api-v1-przelaczniki
uv run pytest src/api_v1/tests/test_przelaczniki.py -v
```

Oczekiwane: `ImportError: cannot import name 'GrupaApiV1'`.

- [ ] **Step 3: Dodaj enum `GrupaApiV1`**

W `src/bpp/models/uczelnia.py`, na poziomie modułu, **przed** `class Uczelnia`:

```python
class GrupaApiV1(models.TextChoices):
    """Grupy endpointów ``/api/v1/`` — po jednej na przełącznik na ``Uczelnia``.

    Wartość enuma jest jednocześnie sufiksem nazwy pola: ``api_v1_<value>``.
    Kontrakt pilnuje ``test_kazda_grupa_ma_pole_na_uczelni`` — bez niego
    literówka wyszłaby dopiero na produkcji.
    """

    DANE_BIBLIOGRAFICZNE = "dane_bibliograficzne", "dane bibliograficzne"
    WYSZUKIWANIE = "wyszukiwanie", "wyszukiwanie"
    KAFELKI = "kafelki", "kafelki do osadzania"
    NARZEDZIA_REDAKTORSKIE = "narzedzia_redaktorskie", "narzędzia redaktorskie"
```

- [ ] **Step 4: Zaktualizuj `help_text` istniejącego pola i dodaj pięć nowych**

Zamień istniejące pole `api_v1_wlaczone` (ok. linii 586) na poniższy blok:

```python
    api_v1_wlaczone = models.BooleanField(
        "Włącz REST API (/api/v1/)",
        default=True,
        help_text="Gdy odznaczone, publiczne REST API tej uczelni "
        "(/api/v1/) przestaje odpowiadać. NIE dotyczy kafelków do "
        "osadzania — te mają własny przełącznik niżej i działają "
        "niezależnie, żeby wyłączenie API nie psuło widgetów wklejonych "
        "na stronach WWW jednostek.",
    )

    api_v1_tylko_zalogowani = models.BooleanField(
        "REST API tylko dla zalogowanych",
        default=False,
        help_text="Gdy zaznaczone, niezalogowany klient dostaje 401 zamiast "
        "danych. Nie dotyczy kafelków do osadzania — te z założenia wiszą "
        "na publicznych stronach.",
    )

    api_v1_dane_bibliograficzne = models.BooleanField(
        "Udostępniaj dane bibliograficzne",
        default=True,
        help_text="Słowniki, struktura uczelni, autorzy, rekordy publikacji, "
        "źródła i wydawcy.",
    )

    api_v1_wyszukiwanie = models.BooleanField(
        "Udostępniaj wyszukiwanie",
        default=True,
        help_text="Endpoint /api/v1/szukaj/ — pełnotekstowe wyszukiwanie po "
        "wszystkich publikacjach. Kosztowny, objęty osobnym limitem zapytań.",
    )

    api_v1_kafelki = models.BooleanField(
        "Udostępniaj kafelki do osadzania",
        default=True,
        help_text="Endpointy /api/v1/recent_author_publications/ i "
        "/api/v1/recent_unit_publications/, z których korzysta widget "
        "bpp-publikacje.js. UWAGA: odznaczenie zgasi listy publikacji "
        "wklejone na stronach WWW jednostek i wydziałów.",
    )

    api_v1_narzedzia_redaktorskie = models.BooleanField(
        "Udostępniaj narzędzia redaktorskie",
        default=True,
        help_text="Zapytania DjangoQL (/api/v1/zapytanie/) i raport slotów "
        "uczelni. Wymagają konta redaktora także wtedy, gdy to pole jest "
        "zaznaczone — decyduje ono wyłącznie o tym, czy endpointy w ogóle "
        "istnieją.",
    )
```

- [ ] **Step 5: Dodaj metodę na `Uczelnia`**

Obok istniejącej metody `ukryte_statusy` (ok. linii 977):

```python
    def api_v1_grupa_wlaczona(self, grupa: GrupaApiV1) -> bool:
        """Czy dana grupa endpointów ``/api/v1/`` jest włączona.

        Nazwa pola wyprowadzana z wartości enuma — jedno miejsce zamiast
        czterech gałęzi ``if``.
        """
        return getattr(self, f"api_v1_{grupa.value}")
```

- [ ] **Step 6: Wygeneruj migrację**

```bash
cd ~/Programowanie/bpp-api-v1-przelaczniki
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp \
    --name api_v1_przelaczniki
```

Oczekiwane: jeden plik `src/bpp/migrations/0480_api_v1_przelaczniki.py` z pięcioma `AddField` i jednym `AlterField` (zmieniony `help_text` pola `api_v1_wlaczone`). Wszystkie mają `default`, więc **żadnej data-migracji ani pytania o wartość domyślną**.

- [ ] **Step 7: Uruchom testy — mają przejść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -v
```

Oczekiwane: 12 PASSED (2 + 4 + 4 sparametryzowane, plus 2 z parametryzacji drugiego testu).

- [ ] **Step 8: Odśwież baseline**

```bash
uv sync --extra baseline-rebuild
make baseline-update
```

Wymaga działającego Dockera. **Nigdy `manage.py baseline_update`** — target `make` dokłada `fix-baseline-search-path`, bez którego ładowanie baseline pod `ON_ERROR_STOP=1` wywala się na triggerach `hstore` i kontener testowej bazy nie wstaje.

Oczekiwane: mały diff (delta nowych migracji) w `baseline-sql/baseline.sql`.

- [ ] **Step 9: Commit**

```bash
git add src/bpp/models/uczelnia.py src/bpp/migrations/0480_api_v1_przelaczniki.py \
    src/api_v1/tests/test_przelaczniki.py baseline-sql/
git commit -m "feat(uczelnia): pięć przełączników konfiguracyjnych REST API

Enum GrupaApiV1 + pola api_v1_tylko_zalogowani i cztery grupy endpointów.
Wartość enuma jest sufiksem nazwy pola, więc api_v1_grupa_wlaczona()
zastępuje cztery gałęzie if; kontrakt pilnuje test.

Wszystkie defaulty zachowują obecne zachowanie."
```

---

### Task 2: Bramka z grupami, `powod` i `NotAuthenticated`

**Files:**
- Modify: `src/api_v1/permissions.py` (całość klasy `ApiV1Wlaczone` i helperów)
- Modify: `src/api_v1/urls.py` (`CustomRouter`, 37 wywołań `register`, `whoami`)
- Test: `src/api_v1/tests/test_przelaczniki.py` (dopisanie)

**Interfaces:**
- Consumes: `GrupaApiV1`, `Uczelnia.api_v1_grupa_wlaczona` z Taska 1.
- Produces: `api_v1.permissions.BramkaApiV1(grupa)`, `BramkaApiV1Mixin` (atrybut klasy `bramka_api_v1_grupa`), `z_bramka_api_v1(view_cls, grupa)` — `grupa` **wymagana**; stałe `KOMUNIKAT_GLOWNY`, `KOMUNIKAT_GRUPA`, `KOMUNIKAT_ZALOGOWANI`; `CustomRouter.register(prefix, viewset, basename=None, *, grupa)` i atrybut `CustomRouter.grupy_endpointow: dict[str, GrupaApiV1]`.

- [ ] **Step 1: Napisz failujące testy bramki**

Dopisz do `src/api_v1/tests/test_przelaczniki.py`:

```python
from django.urls import reverse

from api_v1.permissions import (
    KOMUNIKAT_GLOWNY,
    KOMUNIKAT_GRUPA,
    KOMUNIKAT_ZALOGOWANI,
)

# Po jednym reprezentatywnym endpoincie z każdej grupy. Zapytanie DjangoQL
# i raport slotów wymagają konta także przy włączonej grupie, więc dla nich
# sprawdzamy wyłącznie, że NIE dostajemy 404.
ENDPOINT_GRUPY = {
    GrupaApiV1.DANE_BIBLIOGRAFICZNE: "api_v1:jednostka-list",
    GrupaApiV1.WYSZUKIWANIE: "api_v1:szukaj-list",
    GrupaApiV1.NARZEDZIA_REDAKTORSKIE: "api_v1:zapytanie_rekord-list",
}


@pytest.mark.django_db
@pytest.mark.parametrize("grupa,nazwa_url", list(ENDPOINT_GRUPY.items()))
def test_grupa_wlaczona_endpoint_istnieje(client, uczelnia, grupa, nazwa_url):
    assert client.get(reverse(nazwa_url)).status_code != 404


@pytest.mark.django_db
@pytest.mark.parametrize("grupa,nazwa_url", list(ENDPOINT_GRUPY.items()))
def test_grupa_wylaczona_daje_404(client, uczelnia, grupa, nazwa_url):
    setattr(uczelnia, f"api_v1_{grupa.value}", False)
    uczelnia.save()

    res = client.get(reverse(nazwa_url))
    assert res.status_code == 404
    assert res.json()["powod"] == "grupa_wylaczona"
    assert res.json()["grupa"] == grupa.value
    assert res.json()["detail"] == KOMUNIKAT_GRUPA


@pytest.mark.django_db
def test_wylaczenie_grupy_nie_rusza_pozostalych(client, uczelnia):
    """Regresja w mapowaniu prefiks→grupa inaczej przeszłaby niezauważona."""
    uczelnia.api_v1_wyszukiwanie = False
    uczelnia.save()

    assert client.get(reverse("api_v1:szukaj-list")).status_code == 404
    assert client.get(reverse("api_v1:jednostka-list")).status_code == 200


@pytest.mark.django_db
def test_glowny_wylacznik_daje_404_z_powodem(client, uczelnia):
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 404
    assert res.json()["powod"] == "api_wylaczone"
    assert res.json()["detail"] == KOMUNIKAT_GLOWNY


@pytest.mark.django_db
def test_tylko_zalogowani_anonim_dostaje_401(client, uczelnia):
    """401, nie 403 — kontrakt whoami/ dla bpp-mcp (spec §5.4d) wymaga kodu
    mapowalnego na ponowne logowanie. PermissionDenied dałby 403."""
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 401
    assert res.has_header("WWW-Authenticate")
    assert res.json()["powod"] == "wymagane_zalogowanie"
    assert res.json()["detail"] == KOMUNIKAT_ZALOGOWANI


@pytest.mark.django_db
def test_tylko_zalogowani_zalogowany_widzi_dane(admin_client, uczelnia):
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    assert admin_client.get(reverse("api_v1:jednostka-list")).status_code == 200


@pytest.mark.django_db
def test_kafelki_zyja_mimo_wylaczonego_api(client, uczelnia, autor_jan_nowak):
    """Jedyne złamanie hierarchii — przybite testem, nie komentarzem.

    Widget wisi na publicznych stronach WWW jednostek, których administrator
    BPP nie kontroluje; wyłączenie API nie może po cichu psuć cudzych stron.
    """
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    url = reverse(
        "api_v1:recent_author_publications-detail", args=(autor_jan_nowak.pk,)
    )
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_kafelki_zyja_mimo_tylko_zalogowanych(client, uczelnia, autor_jan_nowak):
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    url = reverse(
        "api_v1:recent_author_publications-detail", args=(autor_jan_nowak.pk,)
    )
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_kafelki_wylaczone_daja_404_z_powodem(client, uczelnia, autor_jan_nowak):
    uczelnia.api_v1_kafelki = False
    uczelnia.save()

    url = reverse(
        "api_v1:recent_author_publications-detail", args=(autor_jan_nowak.pk,)
    )
    res = client.get(url)
    assert res.status_code == 404
    assert res.json()["powod"] == "grupa_wylaczona"
    assert res.json()["grupa"] == GrupaApiV1.KAFELKI.value


@pytest.mark.django_db
def test_404_encji_nie_ma_klucza_powod(client, uczelnia):
    """Druga połowa kontraktu: 404 z ``pobierz_encje_lub_404`` NIE jest
    decyzją administratora, więc widget ma go pokazać, a nie wyciszyć."""
    url = reverse("api_v1:recent_author_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert "powod" not in res.json()


def test_rejestracja_bez_grupy_jest_bledem():
    """Wartość domyślna po cichu odtworzyłaby furtkę przy każdym nowym
    viewsecie — dlatego ``grupa`` jest keyword-only bez defaultu."""
    from api_v1.urls import CustomRouter
    from api_v1.viewsets.struktura import JednostkaViewSet

    router = CustomRouter()
    with pytest.raises(TypeError):
        router.register(r"test", JednostkaViewSet, basename="test_bez_grupy")
```

- [ ] **Step 2: Uruchom testy — mają paść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -v
```

Oczekiwane: `ImportError: cannot import name 'KOMUNIKAT_GLOWNY'`.

- [ ] **Step 3: Przepisz `src/api_v1/permissions.py`**

Zastąp `ApiV1Wlaczone`, `BramkaApiV1Mixin` i `z_bramka_api_v1` (linie 1–58) poniższym. Klasy `IsGrupaRaportyWyswietlanie` i `MoznaUzywacZapytania` **zostają bez zmian**.

```python
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import BasePermission

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Uczelnia
from bpp.models.uczelnia import GrupaApiV1
from bpp.views.zapytanie import user_can_use_query_editor

KOMUNIKAT_GLOWNY = "REST API tego serwisu zostało wyłączone przez administratora."
KOMUNIKAT_GRUPA = (
    "Ta część REST API została wyłączona przez administratora tego serwisu."
)
KOMUNIKAT_ZALOGOWANI = (
    "REST API tego serwisu jest dostępne wyłącznie dla zalogowanych "
    "użytkowników."
)


class BramkaApiV1(BasePermission):
    """Bramka ``/api/v1/`` — sześć przełączników z obiektu ``Uczelnia``.

    Kolejność rozstrzygania:

    1. uczelnia nierozstrzygnięta (pusta baza, kreator konfiguracji, brak
       mapowania Site→Uczelnia) → przepuszczamy, bo nie ma kto podjąć
       decyzji, a świeża instalacja musi działać;
    2. grupa ``KAFELKI`` → rozstrzyga wyłącznie ``api_v1_kafelki``;
    3. główny wyłącznik → 404;
    4. przełącznik grupy → 404;
    5. ograniczenie do zalogowanych → 401.

    Krok 2 świadomie łamie hierarchię: widget ``embed/bpp-publikacje.js``
    wisi na publicznych stronach WWW jednostek, których administrator BPP
    nie kontroluje, więc wyłączenie API nie może po cichu psuć cudzych
    stron. Jest pierwszym testem przełączników i kończy się wcześnie po to,
    żeby wyjątek był widoczny w jednym miejscu.

    Kolejność 4 → 5 pozwala anonimowi poznać stan grup (404 vs 401).
    Przyjęte świadomie: stan grup nie jest tajemnicą, a odwrotna kolejność
    byłaby myląca — anonim dostawałby „zaloguj się" pod adresem, który po
    zalogowaniu i tak zwraca 404.

    Odmowy niosą klucz ``powod``. ``exception_handler`` DRF renderuje
    ``exc.detail`` bezpośrednio, gdy jest słownikiem, więc nie potrzeba
    własnego handlera. Kontrakt: **obecność klucza ``powod`` znaczy „to
    decyzja konfiguracyjna administratora, nie błąd"** — 404 spoza bramki
    (nieistniejąca encja) tego klucza nie mają.

    ``NotAuthenticated``, nie ``PermissionDenied``: rzucenie wyjątku wprost
    omija ``APIView.permission_denied()``, więc ``PermissionDenied`` dałby
    zawsze 403 i zepsuł kontrakt ``whoami/`` (spec bpp-mcp §5.4d: brak
    tokenu → 401 mapowalne na re-auth). ``NotAuthenticated`` oddaje decyzję
    DRF-owi, a ``StrictOAuth2Authentication`` jako pierwszy authenticator
    dostarcza challenge ``Bearer``, więc efektywnym kodem jest 401.
    """

    def __init__(self, grupa):
        self.grupa = grupa

    def has_permission(self, request, view):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is None:
            return True

        if self.grupa is GrupaApiV1.KAFELKI:
            if not uczelnia.api_v1_kafelki:
                raise self._grupa_wylaczona()
            return True

        if not uczelnia.api_v1_wlaczone:
            raise NotFound({"detail": KOMUNIKAT_GLOWNY, "powod": "api_wylaczone"})

        if self.grupa is not None and not uczelnia.api_v1_grupa_wlaczona(
            self.grupa
        ):
            raise self._grupa_wylaczona()

        if uczelnia.api_v1_tylko_zalogowani and not request.user.is_authenticated:
            raise NotAuthenticated(
                {"detail": KOMUNIKAT_ZALOGOWANI, "powod": "wymagane_zalogowanie"}
            )

        return True

    def _grupa_wylaczona(self) -> NotFound:
        return NotFound(
            {
                "detail": KOMUNIKAT_GRUPA,
                "powod": "grupa_wylaczona",
                "grupa": self.grupa.value,
            }
        )


class BramkaApiV1Mixin:
    """Dokleja :class:`BramkaApiV1` na początek uprawnień widoku.

    Przez ``get_permissions()``, a nie przez ``permission_classes`` — po
    pierwsze nie kasujemy deklaracji widoku (``MoznaUzywacZapytania``
    w ``/zapytanie/``, ``IsGrupaRaportyWyswietlanie`` w raporcie slotów),
    po drugie bramka potrzebuje argumentu konstruktora, a DRF
    instancjonowałby klasę z ``permission_classes`` bezargumentowo.

    Grupa siedzi w atrybucie z prefiksem, bo mixin owija także klasy
    z innych aplikacji (``WhoAmIView`` z ``oauth_mcp``).
    """

    bramka_api_v1_grupa = None

    def get_permissions(self):
        return [BramkaApiV1(self.bramka_api_v1_grupa), *super().get_permissions()]


def z_bramka_api_v1(view_cls, grupa):
    """Zwróć podklasę ``view_cls`` objętą bramką, przypisaną do ``grupa``.

    ``grupa`` jest argumentem **wymaganym** (dla widoków bez grupy podaje się
    jawnie ``None``). Wartość domyślna odtworzyłaby furtkę o piętro niżej niż
    ``CustomRouter.register``: root i ``whoami/`` są owijane bezpośrednio,
    z pominięciem routera.

    Podklasa, a nie mutacja ``view_cls`` w miejscu: viewsety bywają
    importowane i testowane bezpośrednio, a ``WhoAmIView`` należy do innej
    aplikacji — doklejanie im uprawnień „z zewnątrz" byłoby zmianą globalną.
    """
    return type(
        view_cls.__name__,
        (BramkaApiV1Mixin, view_cls),
        {
            "__module__": view_cls.__module__,
            "__doc__": view_cls.__doc__,
            "bramka_api_v1_grupa": grupa,
        },
    )
```

- [ ] **Step 4: Przepisz `CustomRouter` w `src/api_v1/urls.py`**

Zastąp całą klasę `CustomRouter` (linie 53–79) i dodaj import `GrupaApiV1`:

```python
from bpp.models.uczelnia import GrupaApiV1
```

```python
class CustomRouter(routers.DefaultRouter):
    """Router ``/api/v1/`` z bramką przełączników ``Uczelnia``.

    Każdy rejestrowany viewset trafia do routera jako podklasa objęta
    :class:`~api_v1.permissions.BramkaApiV1`, dzięki czemu przełączniki
    obejmują CAŁE API — łącznie z viewsetami, które mają własne
    ``permission_classes`` (``/zapytanie/*``, raport slotów, kafelki).

    Dlaczego nie ``DEFAULT_PERMISSION_CLASSES``: to ustawienie *projektu*,
    nie aplikacji (DRF nie ma per-app settings) — złapałoby też widoki DRF
    spoza ``/api/v1/``, a i tak ominęłyby je viewsety nadpisujące
    ``permission_classes``. Dlaczego nie mixin dopisany ręcznie: viewsety
    nie mają jednej wspólnej klasy bazowej, więc znaczyłoby to edycję ~25
    plików i pozostawienie furtki przy każdym nowym viewsecie.

    ``grupa`` jest keyword-only i BEZ wartości domyślnej: rejestracja bez
    niej kończy się ``TypeError`` przy imporcie tego modułu, czyli przy
    starcie aplikacji. Wartość domyślna po cichu odtworzyłaby dokładnie tę
    furtkę, przed którą broni ten router.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: prefiks → grupa; czyta z tego filtr listingu w ``CustomAPIRootView``
        self.grupy_endpointow = {}

    def register(self, prefix, viewset, basename=None, *, grupa):
        if basename is None:
            basename = self.get_default_basename(viewset)
        self.grupy_endpointow[prefix] = grupa
        super().register(prefix, z_bramka_api_v1(viewset, grupa), basename)

    def get_api_root_view(self, api_urls=None):
        """Root z bramką (``grupa=None``) i mapą grup do filtrowania listingu.

        Nadpisujemy zamiast ustawiać ``APIRootView``, bo widok potrzebuje
        dodatkowego ``initkwargs`` — a te przechodzą tylko przez ``as_view``.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        return z_bramka_api_v1(CustomAPIRootView, grupa=None).as_view(
            api_root_dict=api_root_dict,
            grupy_endpointow=dict(self.grupy_endpointow),
        )
```

- [ ] **Step 5: Dopisz `grupa=` do wszystkich 37 rejestracji**

Zamień blok rejestracji (od `router.register(r"konferencja", …)` do końca raportu slotów) na:

```python
DANE = GrupaApiV1.DANE_BIBLIOGRAFICZNE
NARZEDZIA = GrupaApiV1.NARZEDZIA_REDAKTORSKIE

#
# Read-only JSON API — dane bibliograficzne
#

router.register(r"konferencja", KonferencjaViewSet, grupa=DANE)
router.register(r"seria_wydawnicza", Seria_WydawniczaViewSet, grupa=DANE)
router.register(
    r"czas_udostepnienia_openaccess",
    Czas_Udostepnienia_OpenAccess_ViewSet,
    grupa=DANE,
)
router.register(r"nagroda", NagrodaViewSet, grupa=DANE)
router.register(r"charakter_formalny", Charakter_FormalnyViewSet, grupa=DANE)
router.register(r"typ_kbn", Typ_KBNViewSet, grupa=DANE)
router.register(r"jezyk", JezykViewSet, grupa=DANE)
router.register(r"dyscyplina_naukowa", Dyscyplina_NaukowaViewSet, grupa=DANE)
router.register(r"poziom_wydawcy", Poziom_WydawcyViewSet, grupa=DANE)
router.register(r"wydawca", WydawcaViewSet, grupa=DANE)
router.register(r"wydawnictwo_zwarte", Wydawnictwo_ZwarteViewSet, grupa=DANE)
router.register(
    r"wydawnictwo_zwarte_autor", Wydawnictwo_Zwarte_AutorViewSet, grupa=DANE
)
router.register(
    r"wydawnictwo_zwarte_streszczenie",
    Wydawnictwo_Zwarte_StreszczenieViewSet,
    grupa=DANE,
)
router.register(r"patent", PatentViewSet, grupa=DANE)
router.register(r"patent_autor", Patent_AutorViewSet, grupa=DANE)
router.register(r"wydawnictwo_ciagle", Wydawnictwo_CiagleViewSet, grupa=DANE)
router.register(
    r"wydawnictwo_ciagle_autor", Wydawnictwo_Ciagle_AutorViewSet, grupa=DANE
)
router.register(
    r"wydawnictwo_ciagle_zewnetrzna_baza_danych",
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
    grupa=DANE,
)
router.register(
    r"wydawnictwo_ciagle_streszczenie",
    Wydawnictwo_Ciagle_StreszczenieViewSet,
    grupa=DANE,
)
router.register(r"praca_doktorska", Praca_DoktorskaViewSet, grupa=DANE)
router.register(r"praca_habilitacyjna", Praca_HabilitacyjnaViewSet, grupa=DANE)
router.register(r"rodzaj_zrodla", Rodzaj_ZrodlaViewSet, grupa=DANE)
router.register(r"zrodlo", ZrodloViewSet, grupa=DANE)
router.register(r"jednostka", JednostkaViewSet, grupa=DANE)
router.register(r"uczelnia", UczelniaViewSet, grupa=DANE)
router.register(r"autor", AutorViewSet, grupa=DANE)
router.register(r"funkcja_autora", Funkcja_AutoraViewSet, grupa=DANE)
router.register(r"tytul", TytulViewSet, grupa=DANE)
router.register(r"autor_jednostka", Autor_JednostkaViewSet, grupa=DANE)

#
# Wyszukiwanie — kosztowne, objęte osobnym limitem zapytań
#

router.register(
    r"szukaj",
    SzukajViewSet,
    basename="szukaj",
    grupa=GrupaApiV1.WYSZUKIWANIE,
)

#
# Kafelki do osadzania — jedyna grupa niezależna od głównego wyłącznika
# i od ograniczenia do zalogowanych (widget wisi na cudzych stronach WWW).
#

router.register(
    r"recent_author_publications",
    RecentAuthorPublicationsViewSet,
    basename="recent_author_publications",
    grupa=GrupaApiV1.KAFELKI,
)
router.register(
    r"recent_unit_publications",
    RecentUnitPublicationsViewSet,
    basename="recent_unit_publications",
    grupa=GrupaApiV1.KAFELKI,
)

#
# Narzędzia redaktorskie — wymagają konta także przy włączonej grupie
#

router.register(
    r"zapytanie/rekord",
    ZapytanieRekordViewSet,
    basename="zapytanie_rekord",
    grupa=NARZEDZIA,
)
router.register(
    r"zapytanie/autor",
    ZapytanieAutorViewSet,
    basename="zapytanie_autor",
    grupa=NARZEDZIA,
)
router.register(
    r"zapytanie/autorzy",
    ZapytanieAutorzyViewSet,
    basename="zapytanie_autorzy",
    grupa=NARZEDZIA,
)
router.register(
    r"raport_slotow_uczelnia",
    RaportSlotowUczelniaViewSet,
    basename="raport_slotow_uczelnia",
    grupa=NARZEDZIA,
)
router.register(
    r"raport_slotow_uczelnia_wiersz",
    RaportSlotowUczelniaWierszViewSet,
    basename="raport_slotow_uczelnia_wiersz",
    grupa=NARZEDZIA,
)
```

- [ ] **Step 6: Zaktualizuj `whoami` w `urlpatterns`**

```python
urlpatterns = [
    # ``whoami`` nie idzie przez router, więc bramkę dostaje osobno — inaczej
    # wyłączone API nadal potwierdzałoby tożsamość zalogowanego klienta.
    # ``grupa=None``: podlega głównemu wyłącznikowi i ograniczeniu do
    # zalogowanych, ale nie należy do żadnej grupy.
    path(
        "whoami/",
        z_bramka_api_v1(WhoAmIView, grupa=None).as_view(),
        name="whoami",
    ),
    url(r"^", include(router.urls)),
]
```

- [ ] **Step 7: Uruchom testy — mają przejść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -v
```

Jeśli `test_404_encji_nie_ma_klucza_powod` pada — sprawdź, czy fixture `autor_jan_nowak` istnieje w `src/conftest.py`; jeśli nie, użyj `baker.make(Autor, pokazuj=True)`.

- [ ] **Step 8: Uruchom CAŁY pakiet api_v1 — nic nie mogło się zepsuć**

```bash
uv run pytest src/api_v1/ -q
```

- [ ] **Step 9: Commit**

```bash
git add src/api_v1/permissions.py src/api_v1/urls.py \
    src/api_v1/tests/test_przelaczniki.py
git commit -m "feat(api_v1): bramka per-grupa, klucz powod, 401 zamiast 403

Grupa jest keyword-only bez defaultu i na poziomie register(), i na
poziomie z_bramka_api_v1() — root oraz whoami/ są owijane bezpośrednio,
więc default na tym drugim poziomie odtworzyłby furtkę.

Odmowy niosą klucz powod; jego obecność znaczy 'decyzja administratora,
nie błąd'. 404 spoza bramki (nieistniejąca encja) go nie mają.

NotAuthenticated zamiast PermissionDenied: rzucenie wyjątku wprost omija
APIView.permission_denied(), więc PermissionDenied dałby zawsze 403 i
zepsuł kontrakt whoami/ dla bpp-mcp (401 → re-auth)."
```

---

### Task 3: Root ukrywa endpointy wyłączonych grup

**Files:**
- Modify: `src/api_v1/views.py` (`CustomAPIRootView`)
- Test: `src/api_v1/tests/test_przelaczniki.py`

**Interfaces:**
- Consumes: `CustomRouter.grupy_endpointow` z Taska 2, `Uczelnia.api_v1_grupa_wlaczona` z Taska 1.
- Produces: atrybut klasy `CustomAPIRootView.grupy_endpointow` (default `{}`), przyjmowany jako `initkwargs`.

- [ ] **Step 1: Napisz failujący test**

```python
@pytest.mark.django_db
def test_root_ukrywa_endpointy_wylaczonych_grup(client, uczelnia):
    """Bez filtra listing pokazywałby linki prowadzące prosto w 404."""
    res = client.get(reverse("api_v1:api-root"))
    assert "jednostka" in res.json()["authors_and_units"]

    uczelnia.api_v1_dane_bibliograficzne = False
    uczelnia.save()

    dane = client.get(reverse("api_v1:api-root")).json()
    assert "authors_and_units" not in dane
    assert "publications" not in dane
    assert "info" in dane


@pytest.mark.django_db
def test_root_przy_wszystkich_grupach_wylaczonych_zwraca_samo_info(
    client, uczelnia
):
    uczelnia.api_v1_dane_bibliograficzne = False
    uczelnia.api_v1_wyszukiwanie = False
    uczelnia.api_v1_kafelki = False
    uczelnia.api_v1_narzedzia_redaktorskie = False
    uczelnia.save()

    res = client.get(reverse("api_v1:api-root"))
    assert res.status_code == 200
    assert list(res.json().keys()) == ["info"]


@pytest.mark.django_db
def test_root_i_whoami_ida_za_glownym_wylacznikiem(client, uczelnia):
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    for nazwa in ("api_v1:api-root", "api_v1:whoami"):
        res = client.get(reverse(nazwa))
        assert res.status_code == 404, nazwa
        assert res.json()["powod"] == "api_wylaczone"
```

- [ ] **Step 2: Uruchom — ma paść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -k root_ukrywa -v
```

Oczekiwane: FAIL — `authors_and_units` nadal obecne.

- [ ] **Step 3: Dodaj filtr w `CustomAPIRootView`**

W `src/api_v1/views.py` dodaj import i atrybut klasy:

```python
from bpp.models import Uczelnia
```

Zaraz pod `class CustomAPIRootView(APIRootView):` i jego docstringiem:

```python
    #: prefiks → :class:`GrupaApiV1`; wstrzykiwane przez
    #: ``CustomRouter.get_api_root_view`` jako ``initkwargs``. Django
    #: ``View.as_view()`` przyjmuje wyłącznie klucze odpowiadające
    #: istniejącym atrybutom klasy, stąd ta deklaracja.
    grupy_endpointow = {}
```

W metodzie `get()`, zaraz po `endpoints = response.data.copy()`:

```python
            endpoints = self._bez_wylaczonych_grup(request, endpoints)
```

I nowa metoda na klasie:

```python
    def _bez_wylaczonych_grup(self, request, endpoints):
        """Usuń z listingu endpointy z grup wyłączonych na tej uczelni.

        Bez tego root reklamowałby adresy, które bramka i tak odda jako 404.
        """
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is None:
            return endpoints

        return {
            prefiks: url
            for prefiks, url in endpoints.items()
            if self.grupy_endpointow.get(prefiks) is None
            or uczelnia.api_v1_grupa_wlaczona(self.grupy_endpointow[prefiks])
        }
```

- [ ] **Step 4: Uruchom testy — mają przejść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/api_v1/views.py src/api_v1/tests/test_przelaczniki.py
git commit -m "feat(api_v1): root ukrywa endpointy wyłączonych grup

Bez filtra listing reklamowałby adresy, które bramka i tak oddaje jako
404. Mapa prefiks→grupa idzie z routera przez initkwargs."
```

---

### Task 4: CORS na odpowiedziach błędów endpointów kafelkowych

**Files:**
- Modify: `src/api_v1/viewsets/recent_publications_common.py`
- Modify: `src/api_v1/viewsets/recent_author_publications.py`
- Modify: `src/api_v1/viewsets/recent_unit_publications.py`
- Test: `src/api_v1/tests/test_przelaczniki.py`

**Interfaces:**
- Produces: `api_v1.viewsets.recent_publications_common.CorsNaBledachMixin`.

- [ ] **Step 1: Napisz failujące testy**

```python
NAGLOWEK_CORS = "Access-Control-Allow-Origin"


@pytest.mark.django_db
def test_cors_na_404_z_bramki(client, uczelnia, autor_jan_nowak):
    """Bez tego nagłówka przeglądarka nie poda odpowiedzi skryptowi na
    cudzej domenie — ``fetch`` odrzuca się bez statusu i bez treści, więc
    widget nigdy nie zobaczy klucza ``powod``."""
    uczelnia.api_v1_kafelki = False
    uczelnia.save()

    url = reverse(
        "api_v1:recent_author_publications-detail", args=(autor_jan_nowak.pk,)
    )
    res = client.get(url)
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"


@pytest.mark.django_db
def test_cors_na_404_nieistniejacej_encji(client, uczelnia):
    url = reverse("api_v1:recent_author_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"


@pytest.mark.django_db
def test_cors_nadal_na_odpowiedzi_sukcesu(client, uczelnia, autor_jan_nowak):
    url = reverse(
        "api_v1:recent_author_publications-detail", args=(autor_jan_nowak.pk,)
    )
    res = client.get(url)
    assert res.status_code == 200
    assert res[NAGLOWEK_CORS] == "*"


@pytest.mark.django_db
def test_cors_na_404_jednostki(client, uczelnia):
    url = reverse("api_v1:recent_unit_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"
```

- [ ] **Step 2: Uruchom — mają paść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -k cors -v
```

Oczekiwane: 3 FAIL (`KeyError`/`MultiValueDictKeyError` na nagłówku), 1 PASS (sukces).

- [ ] **Step 3: Dodaj mixin w `recent_publications_common.py`**

Zaraz pod funkcją `_ustaw_cors`:

```python
class CorsNaBledachMixin:
    """Nagłówki CORS na KAŻDEJ odpowiedzi widoku — także zbudowanej z wyjątku.

    ``finalize_response`` wykonuje się w ``APIView.dispatch()`` zawsze, w tym
    dla odpowiedzi z ``handle_exception()``. Bez tego odpowiedzi odmowne
    (bramka ``/api/v1/`` rzuca w ``has_permission``, czyli PRZED wejściem do
    metody widoku) oraz 404 z :func:`pobierz_encje_lub_404` szły bez
    ``Access-Control-Allow-Origin``. Widget osadzany na cudzej domenie robi
    ``fetch`` w trybie ``cors``, więc przeglądarka nie pokazałaby mu takiej
    odpowiedzi w ogóle — promise odrzuca się ``TypeError``-em bez statusu
    i bez treści, a widget nie miałby jak odróżnić decyzji administratora
    od literówki w ``data-autor``.

    Zakres celowo wąski: tylko endpointy kafelkowe są projektowane do
    wołania cross-origin. Reszta ``/api/v1/`` zostaje bez CORS.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        _ustaw_cors(response)
        return response
```

- [ ] **Step 4: Usuń wywołanie `_ustaw_cors` z `odpowiedz_z_publikacjami`**

Polityka CORS ma zostać w jednym miejscu. Zamień końcówkę funkcji:

```python
    return Response({**naglowek, "count": len(wynik), "publications": wynik})
```

(usuwając `resp = …`, `_ustaw_cors(resp)` i `return resp`).

- [ ] **Step 5: Podepnij mixin w obu viewsetach**

W `recent_author_publications.py`:

```python
from .recent_publications_common import (
    CorsNaBledachMixin,
    odpowiedz_z_publikacjami,
    pobierz_encje_lub_404,
    queryset_rekordow,
)


class RecentAuthorPublicationsViewSet(CorsNaBledachMixin, viewsets.ViewSet):
```

Analogicznie w `recent_unit_publications.py` dla `RecentUnitPublicationsViewSet`.

- [ ] **Step 6: Uruchom testy — mają przejść**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py -k cors -v
uv run pytest src/api_v1/tests/test_autor_recent_publications.py \
    src/api_v1/tests/test_jednostka_recent_publications.py -q
```

- [ ] **Step 7: Commit**

```bash
git add src/api_v1/viewsets/
git commit -m "fix(api_v1): CORS także na odpowiedziach błędów kafelków

_ustaw_cors() wisiało tylko na odpowiedzi sukcesu, a projekt nie ma
middleware CORS. Bramka rzuca w has_permission (przed wejściem do widoku),
pobierz_encje_lub_404 rzuca Http404 — obie odpowiedzi szły bez ACAO, więc
przeglądarka nie pokazywała ich widgetowi na cudzej domenie.

To zarazem naprawia istniejący błąd: dziś literówka w data-autor daje
cross-origin mglisty błąd sieciowy zamiast czytelnego 404."
```

---

### Task 5: Admin — fieldset „REST API (/api/v1/)" nad OAI-PMH

**Files:**
- Modify: `src/bpp/admin/uczelnia.py` (fieldset z linii 318–324 → przed fieldset z linii 159)

- [ ] **Step 1: Usuń istniejący fieldset „REST API"**

Skasuj blok (linie 318–324):

```python
        (
            "REST API",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": ("api_v1_wlaczone",),
            },
        ),
```

- [ ] **Step 2: Wstaw rozbudowany fieldset przed „OAI-PMH dla Primo (/oai/)"**

Bezpośrednio przed blokiem `("OAI-PMH dla Primo (/oai/)", …)`:

```python
        (
            "REST API (/api/v1/)",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "api_v1_wlaczone",
                    "api_v1_tylko_zalogowani",
                    "api_v1_dane_bibliograficzne",
                    "api_v1_wyszukiwanie",
                    "api_v1_kafelki",
                    "api_v1_narzedzia_redaktorskie",
                ),
            },
        ),
```

Powstaje spójny blok interfejsów wyjściowych: PBN API → REST API → OAI-PMH → CERIF.

- [ ] **Step 3: Sprawdź, że admin się ładuje**

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check
```

Oczekiwane: `System check identified no issues`.

- [ ] **Step 4: Uruchom testy admina**

```bash
uv run pytest src/bpp/tests/ -k uczelnia -q
```

- [ ] **Step 5: Commit**

```bash
git add src/bpp/admin/uczelnia.py
git commit -m "feat(admin): fieldset REST API nad OAI-PMH, z sześcioma polami

Powstaje spójny blok interfejsów wyjściowych: PBN → REST → OAI → CERIF."
```

---

### Task 6: Stopka multiseek linkuje tylko do czynnych interfejsów

**Files:**
- Modify: `src/django_bpp/templates/multiseek/common-results.html:22-23`

- [ ] **Step 1: Zamień akapit**

Obecne linie 22–23:

```django
        <p>Jeżeli potrzebujesz pobrać wszystkie rekordy z systemu BPP, skorzystaj z dostępu przez API. Obsługiwane
            API to <a target="_blank" class="external-arrow-box" href="/api/v1/">JSON-REST</a> oraz <a target="_blank" class="external-arrow-box" href="/bpp/oai/?verb=ListSets">protokół OAI-PMH</a>.</p>
```

Zamień na:

```django
        {# Wymieniamy tylko interfejsy, którymi DA SIĘ pobrać rekordy. #}
        {# Sam api_v1_wlaczone nie wystarcza: przy odznaczonych danych #}
        {# bibliograficznych root odpowiada, ale rekordów za nim nie ma. #}
        {% if uczelnia.api_v1_wlaczone and uczelnia.api_v1_dane_bibliograficzne or uczelnia.oai_pmh_aktywny %}
        <p>Jeżeli potrzebujesz pobrać wszystkie rekordy z systemu BPP, skorzystaj z dostępu przez API. Obsługiwane
            API to {% if uczelnia.api_v1_wlaczone and uczelnia.api_v1_dane_bibliograficzne %}<a target="_blank" class="external-arrow-box" href="/api/v1/">JSON-REST</a>{% if uczelnia.oai_pmh_aktywny %} oraz {% endif %}{% endif %}{% if uczelnia.oai_pmh_aktywny %}<a target="_blank" class="external-arrow-box" href="/bpp/oai/?verb=ListSets">protokół OAI-PMH</a>{% endif %}.</p>
        {% endif %}
```

`and` wiąże mocniej niż `or`, więc warunek czyta się jako `(REST and DANE) or OAI`.

- [ ] **Step 2: Sprawdź, że szablon się parsuje**

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py validate_templates 2>/dev/null \
    || DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check
```

- [ ] **Step 3: Commit**

```bash
git add src/django_bpp/templates/multiseek/common-results.html
git commit -m "feat(multiseek): stopka linkuje tylko do czynnych interfejsów API

Akapit znika w całości, gdy nie ma czym pobrać rekordów — zdanie
'skorzystaj z dostępu przez API' bez działającego API byłoby kpiną
z użytkownika, który właśnie dostał komunikat o limicie 25 tys. rekordów."
```

---

### Task 7: Widget odróżnia decyzję administratora od pomyłki

**Files:**
- Modify: `src/bpp/static/embed/bpp-publikacje.js` (blok `fetch`, linie 285–297; nowe funkcje obok `renderBlad` z linii 259)
- Create: `tests/js/embed-publikacje.test.js`

**Interfaces:**
- Consumes: klucz `powod` w treści odpowiedzi 404 (Task 2), nagłówki CORS na błędach (Task 4).

- [ ] **Step 1: Napisz failujące testy JS**

Utwórz `tests/js/embed-publikacje.test.js`:

```javascript
// @vitest-environment jsdom
// Testy zachowania widgetu osadzania przy odpowiedziach błędnych.
//
// Widget to IIFE odpalane przy załadowaniu i wymagające
// `document.currentScript`, więc plik importujemy DOPIERO po przygotowaniu
// DOM-u — stąd dynamiczny import w każdym teście.
import { describe, test, expect, beforeEach, vi } from "vitest";

const SCIEZKA = "../../src/bpp/static/embed/bpp-publikacje.js";

function odpowiedz(status, tresc, { json = true } = {}) {
    return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: () =>
            json ? Promise.resolve(tresc) : Promise.reject(new SyntaxError()),
    });
}

async function uruchomWidget(odp) {
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    const script = document.createElement("script");
    script.src = "https://bpp.example.org/static/embed/bpp-publikacje.js";
    script.setAttribute("data-autor", "jan-kowalski");
    document.body.appendChild(script);
    Object.defineProperty(document, "currentScript", {
        value: script,
        configurable: true,
    });

    globalThis.fetch = vi.fn(() => odp);
    vi.resetModules();
    await import(`${SCIEZKA}?v=${Math.random()}`);
    // Widget kończy pracę w mikrotaskach łańcucha .then — czekamy na nie.
    await new Promise((r) => setTimeout(r, 0));

    return document.querySelector('[class*="bpp-publikacje"]') || document.body;
}

describe("widget osadzania — odpowiedzi błędne", () => {
    beforeEach(() => {
        vi.spyOn(console, "warn").mockImplementation(() => {});
    });

    test("404 z powod: nic na stronie, powód w komentarzu HTML", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, {
                detail: "Ta część REST API została wyłączona.",
                powod: "grupa_wylaczona",
                grupa: "kafelki",
            })
        );

        expect(kontener.textContent.trim()).toBe("");
        expect(kontener.innerHTML).toContain("<!--");
        expect(kontener.innerHTML).toContain("wyłączona");
        expect(console.warn).toHaveBeenCalled();
    });

    test("404 bez powod: ramka błędu (to zwykła pomyłka)", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, { detail: "No Autor matches the given query." })
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(kontener.innerHTML).not.toContain("<!--");
        expect(console.warn).toHaveBeenCalled();
    });

    test("404 z treścią nie-JSON: ramka błędu", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, null, { json: false })
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(console.warn).toHaveBeenCalled();
    });

    test("500: ramka błędu", async () => {
        const kontener = await uruchomWidget(odpowiedz(500, { detail: "boom" }));

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(console.warn).toHaveBeenCalled();
    });
});
```

- [ ] **Step 2: Uruchom testy JS — mają paść**

```bash
cd ~/Programowanie/bpp-api-v1-przelaczniki
yarn install --frozen-lockfile
npx vitest run tests/js/embed-publikacje.test.js
```

Oczekiwane: pierwszy test FAIL (brak komentarza, jest ramka błędu).

- [ ] **Step 3: Dodaj funkcje pomocnicze w widgecie**

W `src/bpp/static/embed/bpp-publikacje.js`, zaraz po funkcji `renderBlad`
(kończy się na linii 271):

```javascript
  function renderWylaczone(kontener, detail) {
    // Bez śladu na stronie: powód idzie do komentarza HTML, widocznego dla
    // osoby, która wkleiła widget ("pokaż źródło"), a nie dla czytelnika.
    // `createComment` nie interpretuje HTML-a, więc jedynym realnym
    // zagrożeniem jest sekwencja zamykająca — stąd zwinięcie `--`.
    kontener.innerHTML = "";
    var tekst = String(detail || "wyłączone przez administratora").replace(
      /-{2,}/g,
      "-"
    );
    kontener.appendChild(document.createComment(" BPP: " + tekst + " "));
  }

  function trescBledu(resp) {
    // Treść błędnej odpowiedzi jako obiekt albo null, gdy nie da się jej
    // sparsować (proxy, strona błędu HTML). NIGDY nie odrzuca — brak treści
    // ma degradować do ramki błędu, nie do ciszy.
    return resp.json().then(
      function (data) {
        return data;
      },
      function () {
        return null;
      }
    );
  }
```

- [ ] **Step 4: Przepisz blok `fetch`**

Zamień (linie 285–297):

```javascript
    fetch(urlApi(cfg))
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        }
        return resp.json();
      })
      .then(function (data) {
        render(kontener, data, cfg);
      })
      .catch(function () {
        renderBlad(kontener, cfg);
      });
```

na:

```javascript
    var url = urlApi(cfg);
    fetch(url)
      .then(function (resp) {
        if (resp.ok) {
          return resp.json().then(function (data) {
            render(kontener, data, cfg);
          });
        }
        // Klucz `powod` znaczy "decyzja konfiguracyjna administratora, nie
        // błąd". 404 bez niego (literówka w data-autor, autor ukryty,
        // encja skasowana) to zwykła pomyłka — ktoś musi się o niej
        // dowiedzieć, więc zostaje ramka błędu.
        return trescBledu(resp).then(function (dane) {
          var powod = dane && dane.powod;
          console.warn(
            "BPP: " +
              url +
              " → HTTP " +
              resp.status +
              (powod ? " (" + powod + ")" : "")
          );
          if (resp.status === 404 && powod) {
            renderWylaczone(kontener, dane.detail);
          } else {
            renderBlad(kontener, cfg);
          }
        });
      })
      .catch(function (err) {
        console.warn("BPP: " + url + " → " + err);
        renderBlad(kontener, cfg);
      });
```

- [ ] **Step 5: Uruchom testy JS — mają przejść**

```bash
npx vitest run tests/js/embed-publikacje.test.js
```

Oczekiwane: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/bpp/static/embed/bpp-publikacje.js tests/js/embed-publikacje.test.js
git commit -m "feat(embed): widget odróżnia decyzję administratora od pomyłki

404 z kluczem powod → nic na stronie, powód w komentarzu HTML (widoczny
w 'pokaż źródło' dla osoby, która wkleiła widget). 404 bez powod, 404 z
treścią nie-JSON i pozostałe błędy → ramka błędu jak dotychczas.

Cisza jest zarezerwowana dla przypadku, w którym serwer wprost powiedział,
że to decyzja administratora — nie wolno nią ukrywać cudzej literówki."
```

---

### Task 8: Przeniesienie testów `/api/v1/` z aplikacji CERIF

**Files:**
- Modify: `src/cerif_export/tests/test_przelaczniki.py` (usunięcie części `/api/v1/`)
- Modify: `src/api_v1/tests/test_przelaczniki.py` (przyjęcie przeniesionych testów)

- [ ] **Step 1: Przenieś testy `api_v1_wlaczone`**

Z `src/cerif_export/tests/test_przelaczniki.py` przenieś do
`src/api_v1/tests/test_przelaczniki.py`: stałą `ENDPOINTY_API_V1`
i cztery testy (`test_api_v1_wlaczone_domyslnie`,
`test_api_v1_domyslnie_odpowiada`, `test_api_v1_wylaczone_daje_404`,
`test_api_v1_wylaczone_nie_daje_403_ani_401`,
`test_api_v1_wylaczone_dziala_takze_na_detail`).

**Zmiana w `test_api_v1_wylaczone_nie_daje_403_ani_401`:** nazwa i asercja
były pisane, gdy bramka miała jeden przełącznik. Zostawiamy sens
(wyłączone API wygląda na nieistniejące), ale test przemianuj na
`test_api_v1_wylaczone_daje_404_takze_superuserowi` i asertuj wyłącznie
`status_code == 404`.

**Usuń** `test_api_v1_wlaczone_domyslnie` — pokrywa go już
`test_defaulty_zachowuja_obecne_zachowanie` z Taska 1.

- [ ] **Step 2: Popraw docstring modułu w `cerif_export`**

Zostaje sam CERIF:

```python
"""Przełącznik widoczności eksportu CERIF z obiektu ``Uczelnia``.

``Uczelnia.eksport_cerif_wlaczony`` — endpoint OAI-PMH z CERIF-XML,
domyślnie WŁĄCZONY (istniejące wdrożenia nie zmieniają zachowania).

Wyłączony przełącznik daje **404**, nie 403/401 — endpoint ma wyglądać na
nieistniejący, a nie na „istnieje, ale nie dla ciebie".

Przełączniki ``/api/v1/`` mają własny plik:
``src/api_v1/tests/test_przelaczniki.py``.
"""
```

- [ ] **Step 3: Uruchom oba pakiety testów**

```bash
uv run pytest src/api_v1/tests/test_przelaczniki.py \
    src/cerif_export/tests/test_przelaczniki.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/api_v1/tests/test_przelaczniki.py \
    src/cerif_export/tests/test_przelaczniki.py
git commit -m "test(api_v1): testy przełączników /api/v1/ do własnej aplikacji

Mieszkały w cerif_export z przyczyn historycznych — powstały razem ze
specyfikacją eksportu CERIF. Część CERIF-owa zostaje na miejscu."
```

---

### Task 9: Dokumentacja administratora i newsfragment

**Files:**
- Create: `docs/administrator/rest-api.md`
- Modify: `mkdocs.yml` (nawigacja, ok. linii 114)
- Create: `src/bpp/newsfragments/api-v1-przelaczniki.feature.rst`

- [ ] **Step 1: Napisz stronę dokumentacji**

Utwórz `docs/administrator/rest-api.md`:

````markdown
# REST API (`/api/v1/`)

BPP wystawia publiczne REST API pod adresem `/api/v1/`. Domyślnie działa
w całości — ta strona opisuje, jak wyłączyć jego części, gdy z jakiegoś
powodu nie chcesz ich udostępniać.

Ustawienia znajdziesz w panelu administracyjnym: **Uczelnia** → sekcja
**REST API (/api/v1/)**.

Przełączniki dotyczą wyłącznie `/api/v1/`. Nie wpływają na OAI-PMH
(`/oai/`), eksport CERIF (`/cerif-oai/`) ani na działanie samej strony WWW.

## Sześć przełączników

### Włącz REST API (/api/v1/)

Główny wyłącznik. Odznaczenie sprawia, że całe `/api/v1/` odpowiada kodem
404 z informacją, że API zostało wyłączone przez administratora.

**Nie dotyczy kafelków do osadzania** — te mają własny przełącznik
i działają niezależnie. Dzięki temu wyłączenie API nie psuje list
publikacji wklejonych na stronach WWW jednostek.

### REST API tylko dla zalogowanych

Domyślnie **odznaczone**. Po zaznaczeniu niezalogowany klient dostaje kod
401 zamiast danych; zalogowany pracuje normalnie.

Nie dotyczy kafelków do osadzania — te z założenia wiszą na publicznych
stronach i nie mają jak się zalogować.

Użyj tego, gdy chcesz udostępniać dane integracjom (które potrafią się
uwierzytelnić), ale nie chcesz, żeby ktokolwiek mógł anonimowo pobrać
całą bazę.

### Udostępniaj dane bibliograficzne

Słowniki (charaktery formalne, języki, dyscypliny), struktura uczelni,
autorzy, rekordy publikacji, źródła i wydawcy. To główna zawartość API.

### Udostępniaj wyszukiwanie

Endpoint `/api/v1/szukaj/` — pełnotekstowe wyszukiwanie po wszystkich
publikacjach. Jest kosztowny obliczeniowo i objęty osobnym limitem
zapytań; odznacz, jeśli mimo limitu obciąża serwer.

### Udostępniaj kafelki do osadzania

Endpointy `/api/v1/recent_author_publications/`
i `/api/v1/recent_unit_publications/`, z których korzysta widget
`bpp-publikacje.js`.

!!! warning "Odznaczenie zgasi widgety na cudzych stronach"

    Z tych endpointów korzystają listy publikacji wklejone na stronach WWW
    wydziałów, katedr i pracowników — poza Twoją kontrolą. Po odznaczeniu
    listy przestaną się wyświetlać. Widget nie pokaże komunikatu o błędzie
    (strona będzie wyglądać normalnie, po prostu bez listy), a powód
    trafi do komentarza HTML widocznego w „pokaż źródło".

### Udostępniaj narzędzia redaktorskie

Zapytania DjangoQL (`/api/v1/zapytanie/`) i raport slotów uczelni.

Te endpointy wymagają konta redaktora także wtedy, gdy przełącznik jest
zaznaczony — decyduje on wyłącznie o tym, czy w ogóle istnieją.

## Co widzi klient po wyłączeniu

| Sytuacja | Kod | Komunikat |
|---|---|---|
| Główny wyłącznik odznaczony | 404 | REST API tego serwisu zostało wyłączone przez administratora. |
| Odznaczona grupa | 404 | Ta część REST API została wyłączona przez administratora tego serwisu. |
| „Tylko dla zalogowanych", klient anonimowy | 401 | REST API tego serwisu jest dostępne wyłącznie dla zalogowanych użytkowników. |

Strona `/api/v1/` przy częściowym wyłączeniu pokazuje wyłącznie czynne
grupy — nie reklamuje adresów, które i tak nie odpowiedzą.

## Odzyskanie dostępu

Wszystkie przełączniki są odwracalne i działają natychmiast — zaznacz
z powrotem w panelu administracyjnym, zapisz, gotowe. Nie wymagają
restartu ani przebudowy niczego.
````

- [ ] **Step 2: Dodaj wpis do nawigacji**

W `mkdocs.yml`, bezpośrednio **przed** linią
`      - Eksport CERIF / OpenAIRE: administrator/eksport-cerif.md`:

```yaml
      - REST API: administrator/rest-api.md
```

- [ ] **Step 3: Napisz newsfragment**

Utwórz `src/bpp/newsfragments/api-v1-przelaczniki.feature.rst`:

```rst
Konfiguracja REST API ``/api/v1/`` w obiekcie Uczelnia: obok istniejącego
głównego wyłącznika doszły opcje „tylko dla zalogowanych" oraz osobne
przełączniki czterech grup endpointów (dane bibliograficzne, wyszukiwanie,
kafelki do osadzania, narzędzia redaktorskie). Domyślnie wszystko działa
tak jak dotychczas. Wyłączone endpointy zwracają czytelny komunikat
zamiast gołego 404, a widget osadzania odróżnia świadomą decyzję
administratora od nieistniejącego autora.
```

- [ ] **Step 4: Zbuduj dokumentację w trybie strict**

```bash
uv run mkdocs build --strict
```

Oczekiwane: build bez ostrzeżeń.

- [ ] **Step 5: Commit**

```bash
git add docs/administrator/rest-api.md mkdocs.yml \
    src/bpp/newsfragments/api-v1-przelaczniki.feature.rst
git commit -m "docs(administrator): konfiguracja REST API"
```

---

### Task 10: Pełny przebieg kontroli jakości

**Files:** brak zmian merytorycznych — wyłącznie weryfikacja i ewentualne poprawki.

- [ ] **Step 1: Pre-commit**

```bash
cd ~/Programowanie/bpp-api-v1-przelaczniki
uv run pre-commit
```

**NIGDY z argumentami.** Zgłoszone problemy naprawiaj **ręcznie, po jednym**,
narzędziem Edit. Nie uruchamiaj `ruff check --fix` ani innych batch-fixów.

- [ ] **Step 2: Testy Pythona bez Playwrighta**

```bash
make tests-without-playwright
```

Do 10 minut. Jeśli coś padnie — napraw i uruchom ponownie.

- [ ] **Step 3: Testy JS**

```bash
make js-tests
```

`make tests` przerywa się na pierwszym błędnym kroku, więc ten krok trzeba
wykonać osobno, jeśli poprzedni padł i był naprawiany.

- [ ] **Step 4: Sprawdź świeżość baseline**

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run
```

Oczekiwane: brak wykrytych zmian (migracja z Taska 1 pokrywa wszystko).

- [ ] **Step 5: Commit ewentualnych poprawek**

```bash
git add -A
git commit -m "chore: poprawki po pre-commit i pełnym przebiegu testów"
```

---

## Self-Review

**Pokrycie specyfikacji.** Każda sekcja specu ma zadanie:
model i enum → Task 1; przypisanie endpointów do grup, semantyka, `powod`,
implementacja bramki i routera → Task 2; root → Task 3; CORS na błędach →
Task 4; admin → Task 5; stopka multiseek → Task 6; widget → Task 7;
testy → rozproszone po Taskach 1–4 i 7, plus przeniesienie w Tasku 8;
migracja i baseline → Task 1 (kroki 6 i 8); dokumentacja → Task 9.

**Rozbieżność wobec specu, świadoma.** Spec pisał o przepuszczeniu treści
komentarza przez `sanitize`. W implementacji używamy `document.createComment`,
które w ogóle nie interpretuje HTML-a — `sanitize` (zbudowane do czyszczenia
HTML-a w kontekście elementu) byłoby tu nie na miejscu. Zostaje zwinięcie
`--`, czyli jedyny realny wektor w kontekście komentarza. Spec wymaga
korekty tego zdania.

**Spójność nazw.** `GrupaApiV1` (nie `GrupyApiV1`);
`api_v1_grupa_wlaczona` w modelu, bramce i widoku root;
`bramka_api_v1_grupa` jako atrybut klasy;
`grupy_endpointow` w routerze i w `CustomAPIRootView`;
`CorsNaBledachMixin`; `powod`/`grupa`/`detail` jako klucze odpowiedzi;
`renderWylaczone`, `trescBledu` w widgecie.

**Bez placeholderów.** Każdy krok zawiera kod albo dokładne polecenie
z oczekiwanym wynikiem.
