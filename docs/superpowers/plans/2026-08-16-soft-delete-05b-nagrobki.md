# Soft-delete faza 05b: nagrobki — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. TDD: każdy krok najpierw PRAWDZIWY failing test → komenda + FAIL → PRAWDZIWA implementacja → komenda + PASS → commit.

**Goal:** Konsument przyrostowy (harvester OAI-PMH, klient REST) dowiaduje się, że rekord przestał być wystawiany — zamiast odkrywać to po cichej nieobecności.

**Architecture:** Providerzy CERIF dostają drugą metodę kontraktu, `przynaleznosc(uczelnia, model)` — rekordy tenanta bez reguł ekspozycji. Nagrobek to różnica `przynaleznosc − queryset`, liczona w klasie bazowej. Stronicowanie przechodzi na nadzbiór (`przynaleznosc`), więc żywe rekordy i nagrobki płyną **jednym** strumieniem, jednym kursorem keyset. `/api/v1/usuniete/` to osobny, ubogi endpoint zwracający wyłącznie typ, klucz i znacznik czasu.

**Tech Stack:** Django, PostgreSQL, lxml (OAI-PMH XML), Django REST Framework + django-filter, pytest + model_bakery.

**Spec źródłowy:** [`../specs/2026-08-15-soft-delete-nagrobki-design.md`](../specs/2026-08-15-soft-delete-nagrobki-design.md) — czytaj go przed startem, zwłaszcza sekcje „Decyzje" i „Ograniczenia".

**Zależność:** faza 02 (kosz publikacji i autorstw), faza 04 (`Autor`). NIE zależy od fazy 05a ani od `SoftDeleteLog` z fazy 06.

---

## Global Constraints

- Wszystkie komendy Pythona przez `uv run` (np. `uv run pytest ...`). NIGDY gołe `python`.
- Max długość linii **88 znaków** (ruff). Komentarze, docstringi i komunikaty **po polsku**.
- Testy: pytest, standalone functions, **NIGDY `unittest.TestCase`**; `@pytest.mark.django_db`; `model_bakery.baker.make`.
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`.
- Po każdym kroku z kodem produkcyjnym: `uv run ruff check <pliki>` + `uv run ruff format <pliki>`, potem commit.
- Commituj **po jawnych ścieżkach** (`git add <plik> …`), nigdy `git add -A`.
- **NIE uruchamiaj `make clean-testcontainers`** — host bywa współdzielony z równoległymi sesjami; ubiłbyś cudzą pracę. Gdy kontener nie wstaje w 120 s, użyj `TC_MAX_TRIES=600`.
- **Nowa grupa `GrupaApiV1` jest ZABRONIONA w tej fazie.** Każda grupa wymaga pola `api_v1_<value>` na `Uczelnia` (pilnuje `test_kazda_grupa_ma_pole_na_uczelni`), czyli migracji i nowego przełącznika. `/api/v1/usuniete/` rejestrujemy pod istniejącą `GrupaApiV1.DANE_BIBLIOGRAFICZNE`.
- **Ta faza nie dodaje żadnej migracji.** Jeśli `makemigrations --check` zrobi się czerwony, coś poszło nie tak — zatrzymaj się.

---

## Stan zastany (zweryfikowany w kodzie 2026-08-16 — używać tych nazw VERBATIM)

`src/cerif_export/providers/base.py`:
- `ADNOTACJA_TS = "_cerif_ts"`; `z_datestampem(queryset, pole="ostatnio_zmieniony")`
  robi `Trunc(Coalesce(pole, EPOKA), "second", tzinfo=datetime.UTC)`. **Nie ruszaj tej
  funkcji** — jej dwie „blizny" (obcięcie do sekundy, `tzinfo=UTC`) powstały po realnych
  duplikatach na granicy strony.
- `na_datestamp(wartosc) -> str`.
- `class ProviderEncji`: atrybuty `set_spec`, `typ_cerif`, `modele`; metody
  `queryset(uczelnia, model)`, `zbiory_widocznosci(uczelnia, obiekty)`,
  `strona(uczelnia, od=None, do=None, kursor=None, rozmiar=None)`,
  `_istnieje_dalej(...)`, `_kursor(slug, obiekt)`,
  `_strona_modelu(uczelnia, model, od, do, kursor, limit)`,
  `pojedynczy(uczelnia, model, pk)`, `najstarszy_datestamp(uczelnia)`.
- `class ProviderPusty(ProviderEncji)` — `strona()` zwraca `([], None)`,
  `pojedynczy()` zwraca `None`, `najstarszy_datestamp()` zwraca `None`.

Helpery widoczności (wszystkie **bez prefetchy**, nadają się do podzapytań):

| plik | helper | reguły ekspozycji ponad atrybucję |
|---|---|---|
| `publikacje.py:85` | `widoczne_wydawnictwa(model, uczelnia)` | `status_korekty` (kanał `cerif`), `nie_eksportuj_przez_api` |
| `publikacje.py:105` | `widoczne_prace(model, uczelnia)` | jw. |
| `publikacje.py:124` | `widoczne_dla_modelu(model, uczelnia)` | dispatcher |
| `publikacje.py:151` | `widoczne_konferencje(uczelnia)` | **pochodna** od `widoczne_wydawnictwa` |
| `osoby.py:31` | `widoczni_autorzy(uczelnia)` | `Uczelnia.eksport_cerif_osoby`, `pokazuj` |
| `patenty.py:28` | `widoczne_patenty(uczelnia)` | `status_korekty`, `nie_eksportuj_przez_api`, `rodzaj_prawa.eksportuj_jako_patent` |
| `jednostki.py:43` | `widoczne_jednostki(uczelnia)` | `widoczna`, `nie_eksportuj_przez_api` |
| `jednostki.py:58` | `widoczni_grantodawcy(uczelnia)` | **pochodna** od projektów |
| `projekty.py:39` | `widoczne_projekty(uczelnia)` | brak — czysta atrybucja |
| `finansowanie.py:24` | `widoczne_finansowania(uczelnia)` | brak — czysta atrybucja |

`src/cerif_export/oai/czasowniki.py`:
- `_naglowek(rodzic, set_spec, obiekt, namespace)` (`:619`) — buduje `<header>` z
  `identifier`, `datestamp`, `setSpec`.
- `_dopisz_rekordy(korzen, zadanie, rejestr, pary, namespace)` (`:507`) — pętla po
  setach, `_bezpiecznie(...)`, `<record><header/><metadata/></record>`.
- `_lista(zadanie, argumenty, nazwa, z_metadanymi)` (`:339`) — `ListIdentifiers`
  woła `_naglowek` wprost (`:357`).
- `_get_record(zadanie, argumenty)` (`:294`) i `_znajdz_rekord(zadanie, identyfikator)`
  (`:552`) — dziś `provider.pojedynczy()` → `None` → `NieznanyIdentyfikator`.
- `_identify(zadanie, argumenty)` (`:188`) — `_pod(identify, "deletedRecord", const.DELETED_RECORD)` (`:198`).

`src/cerif_export/const.py:115`: `DELETED_RECORD = "no"`.

`src/api_v1/urls.py`: `DANE = GrupaApiV1.DANE_BIBLIOGRAFICZNE` (`:120`);
`router.register(prefix, viewset, grupa=...)` — `grupa` jest **keyword-only bez defaultu**.

`src/cerif_export/tests/conftest.py` dostarcza fixtury `uczelnia`, `jednostka`,
`typ_autor`. **Nowe testy piszemy w `src/cerif_export/tests/test_nagrobki.py`.**

---

## File Structure

| plik | odpowiedzialność |
|---|---|
| `src/cerif_export/providers/base.py` (modify) | kontrakt `przynaleznosc()`, `nagrobki()`, stronicowanie nadzbioru |
| `src/cerif_export/providers/{publikacje,osoby,patenty,jednostki,projekty,finansowanie,konferencje,puste}.py` (modify) | `przynaleznosc()` per provider |
| `src/cerif_export/oai/czasowniki.py` (modify) | emisja `status="deleted"`, GetRecord na nagrobku |
| `src/cerif_export/const.py` (modify) | `DELETED_RECORD` |
| `src/cerif_export/tests/test_nagrobki.py` (create) | cała faza — testy nagrobków |
| `src/api_v1/viewsets/usuniete.py` (create) | viewset `/api/v1/usuniete/` |
| `src/api_v1/serializers/usuniete.py` (create) | serializer nagrobka REST |
| `src/api_v1/urls.py` (modify) | rejestracja endpointu |
| `src/api_v1/tests/test_usuniete.py` (create) | testy endpointu |

---

## Task 1: Kontrakt `przynaleznosc()` w klasie bazowej

**Files:**
- Modify: `src/cerif_export/providers/base.py`
- Modify: `src/cerif_export/providers/puste.py`
- Test: `src/cerif_export/tests/test_nagrobki.py` (NOWY)

**Interfaces:**
- Produces: `ProviderEncji.przynaleznosc(uczelnia, model) -> QuerySet` (abstrakcyjna,
  `NotImplementedError`); `ProviderEncji.nagrobki(uczelnia, model) -> QuerySet`.

- [ ] **Krok 1.1: Failing test — każdy zarejestrowany provider ma `przynaleznosc`.**

Utwórz `src/cerif_export/tests/test_nagrobki.py`:

```python
"""Faza 05b soft-delete: nagrobki dla konsumentów przyrostowych.

Nagrobek = rekord, który NALEŻY do tenanta, ale nie jest już wystawiany.
Dopełniamy ekspozycję, nigdy przynależność — dopełnienie przynależności
wystawiłoby w multi-hosted rekordy cudzych uczelni.
"""

import pytest

from cerif_export.providers import rejestr_providerow


def test_kazdy_provider_deklaruje_przynaleznosc():
    """Kontrakt musi być kompletny, inaczej nagrobki milkną w losowym secie.

    Provider bez ``przynaleznosc`` wywaliłby się dopiero przy harveście
    akurat tego setu — czyli u konsumenta, nie w testach.
    """
    for set_spec, provider in rejestr_providerow().items():
        assert hasattr(provider, "przynaleznosc"), (
            f"Provider setu {set_spec} nie deklaruje przynaleznosc()"
        )
```

- [ ] **Krok 1.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q`
Expected: FAIL — `AttributeError`/`assert` (brak metody).

- [ ] **Krok 1.3: Implementacja — kontrakt + różnica w klasie bazowej**

W `src/cerif_export/providers/base.py`, w klasie `ProviderEncji`, tuż **pod**
metodą `queryset`:

```python
    def przynaleznosc(self, uczelnia, model):
        """Rekordy TEGO tenanta — także niewidoczne i te w koszu.

        Wyłącznie atrybucja tenanta. ŻADNYCH reguł ekspozycji
        (``nie_eksportuj_przez_api``, ``status_korekty``, ``widoczna``,
        ``pokazuj``, przełączniki ``Uczelnia.eksport_cerif_*``) — te należą
        do ``queryset()`` i to ich dopełnienie daje nagrobki.

        Rozszczepienie jest konieczne, bo predykat widoczności sklei dziś
        dwie różne rzeczy. Dopełnienie CAŁEJ widoczności wystawiłoby
        w multi-hosted nagrobki dla rekordów innych uczelni —
        ``widoczne_jednostki()`` filtruje ``uczelnia=uczelnia`` wprost.

        Prefetche: te same co w ``queryset()``. Prefetch na husku jest
        nieszkodliwy, a alternatywa (ponowne pobranie żywych z prefetchami)
        dokładałaby zapytanie na każdą stronę harvestu.
        """
        raise NotImplementedError

    def nagrobki(self, uczelnia, model):
        """Rekordy tenanta, które przestały być wystawiane.

        Różnica liczona po kluczach głównych: ``queryset()`` niesie
        prefetche, a te w podzapytaniu i tak nie działają — ``values("pk")``
        sprowadza je do samego klucza.
        """
        widoczne = self.queryset(uczelnia, model).values("pk")
        return self.przynaleznosc(uczelnia, model).exclude(pk__in=widoczne)
```

W `src/cerif_export/providers/puste.py`, w klasie `ProviderPusty`, pod `queryset`:

```python
    def przynaleznosc(self, uczelnia, model):
        raise NotImplementedError("Set pusty nie ma modeli")
```

- [ ] **Krok 1.4: Komenda + PASS**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q`
Expected: PASS.

- [ ] **Krok 1.5: Lint + commit**

```bash
uv run ruff check src/cerif_export/providers/base.py src/cerif_export/providers/puste.py src/cerif_export/tests/test_nagrobki.py
uv run ruff format src/cerif_export/providers/base.py src/cerif_export/providers/puste.py src/cerif_export/tests/test_nagrobki.py
git add src/cerif_export/providers/base.py src/cerif_export/providers/puste.py src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): kontrakt przynaleznosc() + roznica nagrobkow w bazie providera"
```

---

## Task 2: `przynaleznosc()` providerów o atrybucji własnej

**Files:**
- Modify: `src/cerif_export/providers/publikacje.py`, `osoby.py`, `patenty.py`,
  `jednostki.py`, `projekty.py`, `finansowanie.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`

**Interfaces:**
- Consumes: `ProviderEncji.przynaleznosc` (Task 1).
- Produces: moduł-level helpery `naleza_wydawnictwa(model, uczelnia)`,
  `naleza_prace(model, uczelnia)`, `naleza_dla_modelu(model, uczelnia)`,
  `nalezacy_autorzy(uczelnia)`, `nalezace_patenty(uczelnia)`,
  `nalezace_jednostki(uczelnia)`, `nalezace_projekty(uczelnia)`,
  `nalezace_finansowania(uczelnia)` — wszystkie **bez prefetchy**.

- [ ] **Krok 2.1: Failing test — izolacja tenantów (TEST KRYTYCZNY).**

Dopisz do `test_nagrobki.py`:

```python
@pytest.fixture
def druga_uczelnia(db):
    """Druga uczelnia z własną jednostką — multi-hosted."""
    from django.contrib.sites.models import Site

    from bpp.models import Jednostka, Uczelnia

    site = Site.objects.create(domain="druga.example.org", name="druga")
    uczelnia = Uczelnia.objects.create(nazwa="Druga", skrot="DRU", site=site)
    Jednostka.objects.create(nazwa="Jednostka Drugiej", skrot="JDR", uczelnia=uczelnia)
    return uczelnia


@pytest.mark.django_db
def test_nagrobki_nie_wyciekaja_miedzy_uczelniami(uczelnia, druga_uczelnia):
    """Dopełnienie NIE może objąć rekordów cudzego tenanta.

    To jedyne ryzyko, które dopełnienie widoczności wnosi wprost:
    ``widoczne_jednostki()`` filtruje ``uczelnia=uczelnia``, więc naiwne
    „wszystko minus widoczne" zamieniłoby każdą jednostkę drugiej uczelni
    w nagrobek pierwszej — wyciek identyfikatorów i lawina szumu.
    """
    from bpp.models import Jednostka

    from cerif_export.providers import rejestr_providerow
    from cerif_export import const

    provider = rejestr_providerow()[const.SET_ORGUNITS]
    nagrobki = provider.nagrobki(uczelnia, Jednostka)

    obce = Jednostka.objects.filter(uczelnia=druga_uczelnia)
    assert obce.exists(), "fixture musi utworzyć jednostkę drugiej uczelni"
    assert not nagrobki.filter(pk__in=obce.values("pk")).exists(), (
        "nagrobki uczelni A zawierają jednostkę uczelni B — wyciek tenanta"
    )
```

- [ ] **Krok 2.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py::test_nagrobki_nie_wyciekaja_miedzy_uczelniami -x -q`
Expected: FAIL — `NotImplementedError` z `przynaleznosc`.

- [ ] **Krok 2.3: Implementacja — `jednostki.py`**

W `src/cerif_export/providers/jednostki.py`, obok `widoczne_jednostki`:

```python
def nalezace_jednostki(uczelnia):
    """Jednostki TEJ uczelni — bez reguł ekspozycji.

    Atrybucja to bezpośredni FK ``uczelnia``; ``widoczna``
    i ``nie_eksportuj_przez_api`` są regułami ekspozycji i zostają
    w ``widoczne_jednostki()``, żeby ich dopełnienie dało nagrobki.
    """
    wymagaj_uczelni(uczelnia)
    return Jednostka.objects.filter(uczelnia=uczelnia)
```

a w klasie providera jednostek, pod `queryset`:

```python
    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is Jednostka:
            return nalezace_jednostki(uczelnia)
        if model is Uczelnia:
            return Uczelnia.objects.filter(pk=uczelnia.pk)
        if model is Instytucja_Finansujaca:
            return nalezacy_grantodawcy(uczelnia)
        raise BlednyIdentyfikator(
            f"Model {model!r} nie należy do setu {self.set_spec}"
        )
```

(`nalezacy_grantodawcy` dostarcza Task 3 — do tego czasu ten warunek nie jest
wołany przez testy Taska 2. Jeśli wykonujesz taski po kolei, dopisz go w Tasku 3;
jeśli ktoś czyta ten task osobno — patrz Task 3 po treść tej funkcji.)

- [ ] **Krok 2.4: Implementacja — `publikacje.py`**

Obok `widoczne_wydawnictwa` / `widoczne_prace` / `widoczne_dla_modelu`:

```python
def naleza_wydawnictwa(model, uczelnia):
    """Wydawnictwa TEJ uczelni — bez reguł ekspozycji.

    ⚠️ Scope idzie przez ``global_objects`` modelu autorstwa, czyli
    **z koszem**. Autorstwa mają ``BppAutorstwoSoftDeleteMixin`` od fazy 02,
    więc rekord, któremu skasowano ostatniego autora z tej uczelni,
    pozostaje „kiedyś nasz" i dostanie nagrobek zamiast zniknąć po cichu.
    Użycie ``objects`` cofnęłoby jedną z czterech dróg zniknięcia
    z powrotem do ciszy.
    """
    wymagaj_uczelni(uczelnia)
    return model.objects.filter(
        pk__in=model.autor_rekordu_klass.global_objects.filter(
            jednostka__uczelnia=uczelnia
        ).values("rekord_id")
    )


def naleza_prace(model, uczelnia):
    """Prace dyplomowe TEJ uczelni — bez reguł ekspozycji.

    Atrybucja przez bezpośredni FK ``jednostka`` (jak ``widoczne_prace``).
    """
    wymagaj_uczelni(uczelnia)
    return model.objects.filter(jednostka__uczelnia=uczelnia)


def naleza_zrodla(uczelnia):
    """Źródła wskazywane przez wydawnictwa ciągłe NALEŻĄCE do tej uczelni.

    Provider pochodny — odpowiednik ``widoczne_zrodla`` wyprowadzony
    z przynależności. Tylko ``Wydawnictwo_Ciagle`` ma FK ``zrodlo``.
    Różnica obu zbiorów to źródła, do których prowadziły wyłącznie
    wydawnictwa, które przestały być widoczne — i one dostają nagrobek.
    """
    wymagaj_uczelni(uczelnia)
    return Zrodlo.objects.filter(
        pk__in=naleza_wydawnictwa(Wydawnictwo_Ciagle, uczelnia)
        .filter(zrodlo__isnull=False)
        .values("zrodlo_id")
    )


def naleza_dla_modelu(model, uczelnia):
    """Dispatcher równoległy do ``widoczne_dla_modelu`` (publikacje.py:124).

    MUSI mieć te same trzy gałęzie co tamten — w tym ``Zrodlo``. Pominięcie
    którejś dałoby ``NotImplementedError`` dopiero przy harveście akurat
    tego modelu, czyli u konsumenta.
    """
    if model in MODELE_WYDAWNICTW:
        return naleza_wydawnictwa(model, uczelnia)
    if model in MODELE_PRAC:
        return naleza_prace(model, uczelnia)
    if model is Zrodlo:
        return naleza_zrodla(uczelnia)
    raise BlednyIdentyfikator(
        f"Model {model!r} nie należy do setu {const.SET_PUBLICATIONS}"
    )
```

W klasie `ProviderPublikacji`, pod `queryset`:

```python
    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model not in self.modele:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return naleza_dla_modelu(model, uczelnia)
```

⚠️ **`przynaleznosc` MUSI nieść te same `select_related`/`prefetch_related` co
`queryset`** — stronicowanie (Task 4) paginuje właśnie ją, a serializacja żywych
rekordów czyta z niej relacje. Wydziel listy prefetchy do wspólnych stałych albo
powiel wywołania `.select_related(...)/.prefetch_related(...)` z `queryset()`.
Bez tego harvest dostanie N+1 na każdej stronie — testy tego NIE złapią.

- [ ] **Krok 2.5: Implementacja — `osoby.py`, `patenty.py`, `projekty.py`, `finansowanie.py`**

```python
# osoby.py — obok widoczni_autorzy
def nalezacy_autorzy(uczelnia):
    """Autorzy afiliowani przy TEJ uczelni — bez reguł ekspozycji.

    ⚠️ Świadomie IGNORUJEMY ``Uczelnia.eksport_cerif_osoby``. Przełącznik
    jest regułą ekspozycji, więc jego wyłączenie MA produkować nagrobki —
    harvester ma te osoby usunąć. Skutek uboczny (opisany w specu):
    przestawienie przełącznika wystawia nagrobki dla wszystkich autorów
    uczelni naraz. To poprawne, ale jednorazowo bardzo hałaśliwe.
    """
    wymagaj_uczelni(uczelnia)
    return Autor.objects.filter(
        pk__in=Autor_Jednostka.objects.filter(jednostka__uczelnia=uczelnia).values(
            "autor_id"
        )
    )
```

(Ścieżka zweryfikowana w `widoczni_autorzy` — ta sama konstrukcja
`Autor_Jednostka.objects…values("autor_id")`, bez `pokazuj=True` i bez gałęzi
`eksport_cerif_osoby`, bo oba są regułami ekspozycji.)

```python
# patenty.py — obok widoczne_patenty
def nalezace_patenty(uczelnia):
    """Patenty TEJ uczelni — bez reguł ekspozycji.

    Scope przez model autorstwa z KOSZEM (``global_objects``), jak
    wydawnictwa. ``status_korekty``, ``nie_eksportuj_przez_api``
    i ``rodzaj_prawa.eksportuj_jako_patent`` to ekspozycja — zostają
    w ``widoczne_patenty()``.
    """
    wymagaj_uczelni(uczelnia)
    return Patent.objects.filter(
        pk__in=Patent_Autor.global_objects.filter(
            jednostka__uczelnia=uczelnia
        ).values("rekord_id")
    )


# projekty.py — obok widoczne_projekty
def nalezace_projekty(uczelnia):
    """Projekty TEJ uczelni. Czysta atrybucja — identyczna z widocznością,
    więc dopełnienie jest puste i ten set nagrobków nie wygeneruje.
    Kontrakt implementujemy dla spójności i gotowości na przyszłe reguły."""
    wymagaj_uczelni(uczelnia)
    return Projekt.objects.filter(jednostka__uczelnia=uczelnia)


# finansowanie.py — obok widoczne_finansowania
def nalezace_finansowania(uczelnia):
    """Finansowania projektów TEJ uczelni. Jak projekty: czysta atrybucja,
    dopełnienie puste."""
    wymagaj_uczelni(uczelnia)
    return Finansowanie.objects.filter(projekt__jednostka__uczelnia=uczelnia)
```

W każdej z czterech klas providerów dopisz `przynaleznosc` w kształcie:

```python
    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not <Model>:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return <nalezace_helper>(uczelnia).<te same select_related/prefetch co queryset>
```

- [ ] **Krok 2.6: Komenda + PASS**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q`
Expected: PASS (oba testy).

- [ ] **Krok 2.7: Regresja providerów**

Run: `uv run pytest src/cerif_export/tests/test_providery.py src/cerif_export/tests/test_widocznosc.py -q`
Expected: zielono — `przynaleznosc` niczego nie zmienia w widoczności.

- [ ] **Krok 2.8: Lint + commit**

```bash
uv run ruff check src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
uv run ruff format src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
git add src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): przynaleznosc() providerow o atrybucji wlasnej + izolacja tenantow"
```

---

## Task 3: `przynaleznosc()` providerów pochodnych

Konferencje i grantodawcy nie mają własnej atrybucji — ich widoczność jest
wyprowadzona z publikacji i projektów. Przynależność wyprowadzamy **z przynależności**
rekordów nadrzędnych, nie z ich widoczności. Dzięki temu konferencja, do której
prowadziły wyłącznie publikacje, które przestały być widoczne, dostaje nagrobek —
bo realnie znika z feedu.

**Files:**
- Modify: `src/cerif_export/providers/publikacje.py` (helper konferencji),
  `src/cerif_export/providers/konferencje.py`, `src/cerif_export/providers/jednostki.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`

**Interfaces:**
- Consumes: `naleza_wydawnictwa` (Task 2), `nalezace_projekty` (Task 2).
- Produces: `nalezace_konferencje(uczelnia)`, `nalezacy_grantodawcy(uczelnia)`.

- [ ] **Krok 3.1: Failing test — konferencja osierocona dostaje nagrobek**

```python
@pytest.mark.django_db
def test_konferencja_bez_widocznych_publikacji_to_nagrobek(
    uczelnia, jednostka, typ_autor
):
    """Provider pochodny: konferencja znika, gdy znikną jej publikacje.

    Widoczność konferencji jest wyprowadzona z publikacji. Gdy jedyna
    publikacja wskazująca konferencję przestaje być widoczna, konferencja
    też wypada z feedu — i musi dostać nagrobek, a nie zniknąć po cichu.
    """
    from model_bakery import baker

    from bpp.models import Konferencja, Wydawnictwo_Ciagle
    from cerif_export import const
    from cerif_export.providers import rejestr_providerow

    konferencja = baker.make(Konferencja)
    praca = baker.make(Wydawnictwo_Ciagle, konferencja=konferencja)
    praca.dodaj_autora(
        baker.make("bpp.Autor"), jednostka, typ_odpowiedzialnosci_skrot="aut."
    )

    provider = rejestr_providerow()[const.SET_EVENTS]
    assert not provider.nagrobki(uczelnia, Konferencja).filter(
        pk=konferencja.pk
    ).exists(), "konferencja z widoczną publikacją nie jest nagrobkiem"

    praca.nie_eksportuj_przez_api = True
    praca.save()

    assert provider.nagrobki(uczelnia, Konferencja).filter(
        pk=konferencja.pk
    ).exists(), (
        "konferencja straciła jedyną widoczną publikację, a nie dostała "
        "nagrobka — znika z feedu po cichu"
    )
```

⚠️ **Sprawdź sygnaturę `dodaj_autora`** (`grep -n "def dodaj_autora" -A 6 src/bpp/models/abstract/*.py`)
i dostosuj wywołanie — nazwa argumentu typu odpowiedzialności bywa różna w tym repo.

- [ ] **Krok 3.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py::test_konferencja_bez_widocznych_publikacji_to_nagrobek -x -q`
Expected: FAIL — `NotImplementedError` (provider konferencji nie ma `przynaleznosc`).

- [ ] **Krok 3.3: Implementacja**

W `publikacje.py`, tuż pod `widoczne_konferencje`:

```python
def nalezace_konferencje(uczelnia):
    """Konferencje wskazywane przez publikacje NALEŻĄCE do tej uczelni.

    Odpowiednik ``widoczne_konferencje``, ale wyprowadzony z przynależności,
    nie z widoczności. Różnica tych dwóch zbiorów to właśnie konferencje,
    które wypadły z feedu — i o nie chodzi w nagrobkach.
    """
    wymagaj_uczelni(uczelnia)
    warunek = Q()
    for model in MODELE_WYDAWNICTW:
        warunek |= Q(
            pk__in=naleza_wydawnictwa(model, uczelnia)
            .filter(konferencja__isnull=False)
            .values("konferencja_id")
        )
    return Konferencja.objects.filter(warunek)
```

W `konferencje.py`, w klasie providera:

```python
    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Konferencja:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return nalezace_konferencje(uczelnia).select_related("pbn_uid")
```

(import `nalezace_konferencje` z `cerif_export.providers.publikacje` — tak jak
`konferencje.py` importuje dziś `widoczne_konferencje`; sprawdź istniejący import.)

W `jednostki.py`, obok `widoczni_grantodawcy` — odwzoruj jego treść, podmieniając
wewnętrzny zbiór projektów na `nalezace_projekty`:

```python
def nalezacy_grantodawcy(uczelnia):
    """Instytucje finansujące projekty TEJ uczelni.

    ⚠️ Treść jest IDENTYCZNA z ``widoczni_grantodawcy`` — i to nie pomyłka.
    Tamten helper filtruje ``finansowanie__projekt__jednostka__uczelnia``
    wprost, czyli sama atrybucja, bez żadnej reguły ekspozycji. Dopełnienie
    jest więc puste i ten model nagrobków nie wygeneruje.

    Implementujemy mimo to, bo kontrakt providera musi być kompletny
    (``test_kazdy_provider_deklaruje_przynaleznosc``), a rozdzielenie nazw
    pokazuje następnemu czytelnikowi, gdzie dopisać regułę ekspozycji, gdyby
    kiedyś powstała — wtedy nagrobki zaczną działać bez zmian w bazie.
    """
    wymagaj_uczelni(uczelnia)
    return Instytucja_Finansujaca.objects.filter(
        finansowanie__projekt__jednostka__uczelnia=uczelnia
    ).distinct()
```

- [ ] **Krok 3.4: Komenda + PASS**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q`
Expected: PASS.

- [ ] **Krok 3.5: Lint + commit**

```bash
uv run ruff check src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
uv run ruff format src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
git add src/cerif_export/providers/ src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): przynaleznosc() providerow pochodnych (konferencje, grantodawcy)"
```

---

## Task 4: Stronicowanie nadzbioru (NAJDELIKATNIEJSZY)

**Files:**
- Modify: `src/cerif_export/providers/base.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`

**Interfaces:**
- Produces: `strona()` zwraca `([(obiekt, czy_nagrobek)], kursor)` — **zmiana
  kształtu zwrotki**; `ProviderEncji.widoczne_pk_ze_strony(uczelnia, model, obiekty) -> frozenset`.

⚠️ **Zmiana kształtu zwrotki `strona()` dotyka `oai/czasowniki.py` (`_zbierz_strone`,
`_lista`, `_dopisz_rekordy`). Task 5 dostosowuje wołających — do tego czasu suita
OAI będzie czerwona. To jedyny task, po którym wolno zacommitować przy czerwonym
`test_oai.py`; napisz to w komunikacie commita.**

- [ ] **Krok 4.1: Failing test — nagrobek pojawia się w stronie, w porządku dat**

```python
@pytest.mark.django_db
def test_strona_miesza_zywe_i_nagrobki_w_porzadku_dat(uczelnia, jednostka, typ_autor):
    """Jeden strumień, jeden kursor.

    Nagrobki NIE mogą iść osobnym przebiegiem po żywych rekordach:
    ``resumptionToken`` niesie jeden kursor ``(datestamp, pk)`` i zakłada
    jeden porządek. Dwa strumienie zepsułyby przyrostowość ``from``/``until``,
    czyli dokładnie to, co ta faza naprawia.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const
    from cerif_export.providers import rejestr_providerow

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )

    provider = rejestr_providerow()[const.SET_ORGUNITS]
    pary, _kursor = provider.strona(uczelnia, rozmiar=100)

    mapa = {obiekt.pk: nagrobek for obiekt, nagrobek in pary}
    assert mapa.get(ukryta.pk) is True, "jednostka ukryta ma być nagrobkiem"
    assert mapa.get(jednostka.pk) is False, "jednostka widoczna ma być żywa"
```

- [ ] **Krok 4.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py::test_strona_miesza_zywe_i_nagrobki_w_porzadku_dat -x -q`
Expected: FAIL — `strona()` zwraca gołe obiekty, nie pary; ukryta jednostka w ogóle nie wychodzi.

- [ ] **Krok 4.3: Implementacja**

W `base.py`:

1. W `_strona_modelu` podmień źródło — `self.queryset(...)` na `self.przynaleznosc(...)`:

```python
    def _strona_modelu(self, uczelnia, model, od, do, kursor, limit):
        from django.db.models import Q

        # Nadzbiór: żywe + nagrobki w JEDNYM porządku keyset. Kursor
        # resumption tokenu niesie (datestamp, pk) i zakłada jeden strumień.
        qs = z_datestampem(self.przynaleznosc(uczelnia, model))
        ...  # reszta ciała BEZ ZMIAN
```

2. Dodaj pomocniczą metodę ustalającą, które obiekty strony są żywe:

```python
    def widoczne_pk_ze_strony(self, uczelnia, model, obiekty) -> frozenset:
        """Klucze obiektów tej strony, które są nadal wystawiane.

        Jedno tanie zapytanie na stronę, zawężone do jej kluczy — nie
        skanuje całego zbioru widocznych.
        """
        if not obiekty:
            return frozenset()
        klucze = [obiekt.pk for obiekt in obiekty]
        return frozenset(
            self.queryset(uczelnia, model)
            .filter(pk__in=klucze)
            .values_list("pk", flat=True)
        )
```

3. W `strona()` owiń zebrane obiekty w pary `(obiekt, czy_nagrobek)`. Obiekty
   zbierane są per model, więc oznaczaj je **przed** dołożeniem do `zebrane`:
   wszędzie, gdzie dziś jest `zebrane.extend(partia)` albo
   `zebrane.extend(partia[:brakuje])`, wstaw najpierw

```python
            widoczne = self.widoczne_pk_ze_strony(uczelnia, model, partia)
            oznaczone = [(obiekt, obiekt.pk not in widoczne) for obiekt in partia]
```

   i dokładaj `oznaczone`. `self._kursor(slugi[indeks], partia[-1])` MUSI dalej
   dostawać **goły obiekt**, nie parę — kursor czyta `ADNOTACJA_TS` i `pk`.

⚠️ **Nie ruszaj sondy `brakuje + 1`, `_istnieje_dalej` ani `_kursor`.** To one
gwarantują, że token wydajemy tylko wtedy, gdy realnie jest co pokazać.

- [ ] **Krok 4.4: Komenda + PASS (test tej fazy)**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q`
Expected: PASS.

- [ ] **Krok 4.5: Commit z jawnym ostrzeżeniem o czerwonym OAI**

```bash
uv run ruff check src/cerif_export/providers/base.py
uv run ruff format src/cerif_export/providers/base.py
git add src/cerif_export/providers/base.py src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): strona() paginuje nadzbior i zwraca pary (obiekt, nagrobek)

UWAGA: test_oai.py jest po tym commicie CZERWONY — zmienil sie ksztalt
zwrotki strona(). Wolajacych dostosowuje nastepny task."
```

---

## Task 5: Emisja `status="deleted"` w ListRecords / ListIdentifiers

**Files:**
- Modify: `src/cerif_export/oai/czasowniki.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`

**Interfaces:**
- Consumes: `strona()` zwracające pary (Task 4).
- Produces: `_naglowek(rodzic, set_spec, obiekt, namespace, usuniety=False)`.

- [ ] **Krok 5.1: Failing test — nagrobek w ListRecords bez metadanych**

```python
@pytest.mark.django_db
def test_listrecords_emituje_nagrobek_bez_metadanych(uczelnia, jednostka, rf):
    """Rekord usunięty to SAM nagłówek — dokładanie <metadata> łamie schemat."""
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export.oai import czasowniki

    baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )

    korzen = czasowniki.obsluz(
        _zadanie_dla(uczelnia),
        {"verb": "ListRecords", "metadataPrefix": "oai_cerif_openaire",
         "set": "openaire_cris_orgunits"},
    )
    naglowki = korzen.findall(".//{http://www.openarchives.org/OAI/2.0/}header")
    usuniete = [h for h in naglowki if h.get("status") == "deleted"]
    assert usuniete, "brak nagrobka w ListRecords"

    for naglowek in usuniete:
        rekord = naglowek.getparent()
        assert (
            rekord.find("{http://www.openarchives.org/OAI/2.0/}metadata") is None
        ), "nagrobek nie może nieść <metadata>"
```

⚠️ **Sprawdź publiczne API modułu** (`grep -n "^def obsluz\|^def " src/cerif_export/oai/czasowniki.py | head`)
oraz jak `test_oai.py` buduje „zadanie" i wywołuje czasowniki — powiel **ten sam**
sposób zamiast wymyślać `_zadanie_dla` i `metadataPrefix`. Stałą prefiksu weź
z `const.METADATA_PREFIX`, a `setSpec` z `const.SET_ORGUNITS`.

- [ ] **Krok 5.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q -k listrecords`
Expected: FAIL — brak atrybutu `status`.

- [ ] **Krok 5.3: Implementacja — `_naglowek` + wołający**

```python
def _naglowek(rodzic, set_spec, obiekt, namespace, usuniety=False):
    """Nagłówek rekordu; ``usuniety=True`` daje nagrobek.

    OAI-PMH sygnalizuje usunięcie atrybutem ``status="deleted"`` na
    ``<header>``. Rekord usunięty NIE niesie ``<metadata>`` — dołożenie ich
    złamałoby schemat odpowiedzi.
    """
    naglowek = _pod(rodzic, "header")
    if usuniety:
        naglowek.set("status", "deleted")
    _pod(naglowek, "identifier", identyfikatory.zbuduj(namespace, obiekt))
    _pod(naglowek, "datestamp", na_datestamp(getattr(obiekt, ADNOTACJA_TS, None)))
    _pod(naglowek, "setSpec", set_spec)
    return naglowek
```

W `_lista`, gałąź `ListIdentifiers` (dziś `:357`):

```python
        for biezacy_set, (obiekt, nagrobek) in pary:
            _naglowek(korzen, biezacy_set, obiekt, namespace, usuniety=nagrobek)
```

W `_dopisz_rekordy` — nagrobek **przed** serializacją, bo nie ma czego serializować:

```python
        for obiekt, nagrobek in obiekty:
            if nagrobek:
                rekord = _pod(korzen, "record")
                _naglowek(rekord, biezacy_set, obiekt, namespace, usuniety=True)
                continue

            identyfikator = identyfikatory.zbuduj(namespace, obiekt)
            ...  # dotychczasowa ścieżka żywego rekordu BEZ ZMIAN
```

⚠️ `_wg_setu`, `_zbierz_strone` i `_kursor` przenoszą teraz pary — przejrzyj
`grep -n "pary\|obiekt" src/cerif_export/oai/czasowniki.py` i dostosuj rozpakowanie
wszędzie, gdzie iterowano po gołych obiektach. **Nie zmieniaj** logiki tokenu.

- [ ] **Krok 5.4: Komenda + PASS + regresja OAI**

```bash
uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q
uv run pytest src/cerif_export/tests/test_oai.py -q
```
Expected: oba zielone — `test_oai.py` wraca do zdrowia po Tasku 4.

- [ ] **Krok 5.5: Lint + commit**

```bash
uv run ruff check src/cerif_export/oai/czasowniki.py src/cerif_export/tests/test_nagrobki.py
uv run ruff format src/cerif_export/oai/czasowniki.py src/cerif_export/tests/test_nagrobki.py
git add src/cerif_export/oai/czasowniki.py src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): ListRecords/ListIdentifiers emituja naglowek status=deleted"
```

---

## Task 6: GetRecord zwraca nagrobek zamiast `idDoesNotExist`

**Files:**
- Modify: `src/cerif_export/providers/base.py` (`pojedynczy`), `src/cerif_export/oai/czasowniki.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`

**Interfaces:**
- Produces: `ProviderEncji.pojedynczy(uczelnia, model, pk)` szuka w nadzbiorze;
  `_znajdz_rekord` zwraca `(set_spec, provider, obiekt, czy_nagrobek)` — **czwarty element**.

- [ ] **Krok 6.1: Failing test**

```python
@pytest.mark.django_db
def test_getrecord_na_usunietym_zwraca_nagrobek(uczelnia):
    """Usunięty rekord ma nagrobek, nie błąd.

    ``idDoesNotExist`` znaczy „nigdy o takim nie słyszałem" — dla rekordu,
    który harvester dostał od nas wcześniej, to odpowiedź myląca.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const, identyfikatory
    from cerif_export.oai import czasowniki

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )
    zadanie = _zadanie_dla(uczelnia)
    identyfikator = identyfikatory.zbuduj(zadanie.namespace, ukryta)

    korzen = czasowniki.obsluz(
        zadanie,
        {"verb": "GetRecord", "identifier": identyfikator,
         "metadataPrefix": const.METADATA_PREFIX},
    )
    naglowek = korzen.find(".//{http://www.openarchives.org/OAI/2.0/}header")
    assert naglowek.get("status") == "deleted"
    assert korzen.find(".//{http://www.openarchives.org/OAI/2.0/}metadata") is None
```

- [ ] **Krok 6.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q -k getrecord`
Expected: FAIL — podnosi się `NieznanyIdentyfikator`.

- [ ] **Krok 6.3: Implementacja**

W `base.py`:

```python
    def pojedynczy(self, uczelnia, model, pk):
        """Obiekt należący do tenanta albo ``None``.

        Szuka w NADZBIORZE: rekord niewidoczny nadal istnieje dla OAI —
        jako nagrobek. O tym, czy jest żywy, decyduje wywołujący
        (``widoczne_pk_ze_strony``).
        """
        return z_datestampem(self.przynaleznosc(uczelnia, model)).filter(pk=pk).first()
```

W `ProviderPusty` `pojedynczy()` zostaje bez zmian (`return None`).

W `czasowniki.py`, `_znajdz_rekord` — dołóż czwarty element zwrotki:

```python
        obiekt = provider.pojedynczy(zadanie.uczelnia, model, pk)
        if obiekt is None:
            break
        nagrobek = obiekt.pk not in provider.widoczne_pk_ze_strony(
            zadanie.uczelnia, model, [obiekt]
        )
        return set_spec, provider, obiekt, nagrobek
```

W `_get_record`:

```python
    set_spec, provider, obiekt, nagrobek = _znajdz_rekord(zadanie, identyfikator)

    korzen = etree.Element(f"{{{NS_PMH}}}GetRecord")
    rekord = _pod(korzen, "record")
    _naglowek(rekord, set_spec, obiekt, zadanie.namespace, usuniety=nagrobek)
    if nagrobek:
        # Rekord usunięty to sam nagłówek — nie ma czego serializować.
        return korzen

    widoczne = provider.zbiory_widocznosci(zadanie.uczelnia, [obiekt])
    ...  # dotychczasowa ścieżka BEZ ZMIAN
```

⚠️ Blok `widoczne = provider.zbiory_widocznosci(...)` i `kontekst = _kontekst(...)`
przenieś **pod** wczesny zwrot — dla nagrobka są zbędne i kosztują zapytania.

- [ ] **Krok 6.4: Komenda + PASS**

```bash
uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q
uv run pytest src/cerif_export/tests/test_oai.py -q
```
Expected: zielono. `GetRecord` na identyfikatorze spoza tenanta MUSI dalej dawać
`idDoesNotExist` — sprawdza to istniejący `test_oai.py`.

- [ ] **Krok 6.5: Lint + commit**

```bash
uv run ruff check src/cerif_export/providers/base.py src/cerif_export/oai/czasowniki.py
uv run ruff format src/cerif_export/providers/base.py src/cerif_export/oai/czasowniki.py
git add src/cerif_export/providers/base.py src/cerif_export/oai/czasowniki.py src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): GetRecord na usunietym zwraca nagrobek zamiast idDoesNotExist"
```

---

## Task 7: `Identify` deklaruje `transient` + `earliestDatestamp` z nadzbioru

**Files:**
- Modify: `src/cerif_export/const.py`, `src/cerif_export/providers/base.py`
- Test: `src/cerif_export/tests/test_nagrobki.py`, `src/cerif_export/tests/test_oai.py`

- [ ] **Krok 7.1: Failing test**

```python
@pytest.mark.django_db
def test_identify_deklaruje_transient(uczelnia):
    """Deklaracja to obietnica wobec harvestera, nie kosmetyka.

    ``no`` znaczy „nie dowiesz się o usunięciach — rób pełny re-harvest".
    ``transient`` znaczy „ogłaszam usunięcia, ale nie gwarantuję, że
    nagrobek zostanie na zawsze" — i to jest prawda: husk może zniknąć przy
    twardym kasowaniu albo czyszczeniu kosza w fazie 07.
    """
    from cerif_export.oai import czasowniki

    korzen = czasowniki.obsluz(_zadanie_dla(uczelnia), {"verb": "Identify"})
    element = korzen.find(".//{http://www.openarchives.org/OAI/2.0/}deletedRecord")
    assert element.text == "transient"
```

- [ ] **Krok 7.2: Komenda + FAIL**

Run: `uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q -k identify`
Expected: FAIL — `"no" != "transient"`.

- [ ] **Krok 7.3: Implementacja**

`src/cerif_export/const.py:115`:

```python
# Faza 05b soft-delete: ogłaszamy usunięcia nagłówkiem status="deleted".
# `transient`, nie `persistent`: nie gwarantujemy trwałości nagrobka —
# husk może zniknąć przy twardym kasowaniu albo czyszczeniu kosza (faza 07),
# a sety bez soft-delete (jednostki, projekty) nie mają trwałego śladu.
DELETED_RECORD = "transient"
```

W `base.py`, `najstarszy_datestamp` — `self.queryset` → `self.przynaleznosc`
(nagrobek też jest rekordem o dacie i może być najstarszy).

- [ ] **Krok 7.4: Komenda + PASS**

```bash
uv run pytest src/cerif_export/tests/test_nagrobki.py -x -q
uv run pytest src/cerif_export/tests/test_oai.py -q
```

⚠️ `test_oai.py:228` asertuje `tekst(korzen, "Identify", "deletedRecord") == const.DELETED_RECORD`
— porównuje ze stałą, więc przejdzie automatycznie. Jeśli gdzieś jest zaszyty literał
`"no"`, popraw **test**, nie stałą.

- [ ] **Krok 7.5: Lint + commit**

```bash
uv run ruff check src/cerif_export/const.py src/cerif_export/providers/base.py
uv run ruff format src/cerif_export/const.py src/cerif_export/providers/base.py
git add src/cerif_export/const.py src/cerif_export/providers/base.py src/cerif_export/tests/test_nagrobki.py
git commit -m "feat(cerif): Identify deklaruje deletedRecord=transient"
```

---

## Task 8: Cztery drogi zniknięcia + `from`/`until` + granica strony

**Files:**
- Test: `src/cerif_export/tests/test_nagrobki.py`

To task **wyłącznie testowy** — domyka pokrycie ryzyk nazwanych w specu.

- [ ] **Krok 8.1: Test — cztery drogi zniknięcia dają nagrobek**

```python
def _ukryj_kosz(praca, uczelnia):
    praca.delete()


def _ukryj_opt_out(praca, uczelnia):
    praca.nie_eksportuj_przez_api = True
    praca.save()


def _ukryj_status(praca, uczelnia):
    from bpp.models import Status_Korekty

    ukryte = list(uczelnia.ukryte_statusy("cerif"))
    assert ukryte, (
        "fixture musi mieć status ukryty w kanale cerif — bez tego przypadek "
        "nie odtwarza trzeciej drogi zniknięcia"
    )
    praca.status_korekty = Status_Korekty.objects.get(pk=ukryte[0])
    praca.save()


def _ukryj_odpiecie_autora(praca, uczelnia):
    # Skasowanie autorstwa to soft-delete (faza 02) — wiersz zostaje w koszu
    # i to on trzyma historyczną atrybucję rekordu do uczelni.
    praca.autorzy_set.first().delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ukryj",
    [_ukryj_kosz, _ukryj_opt_out, _ukryj_status, _ukryj_odpiecie_autora],
    ids=["kosz", "opt_out", "ukryty_status", "odpiecie_autora"],
)
def test_kazda_droga_znikniecia_daje_nagrobek(uczelnia, jednostka, typ_autor, ukryj):
    """Cztery drogi, jeden skutek dla harvestera — więc jeden nagrobek.

    Przypadek ``odpiecie_autora`` jest tu najważniejszy: dowodzi, że
    ``przynaleznosc`` idzie przez ``global_objects`` modelu autorstwa.
    Gdyby szła przez ``objects``, rekord wypadłby z nadzbioru i zniknął
    po cichu — czyli wróciłaby dokładnie ta luka, którą faza zamyka.
    """
    from model_bakery import baker

    from bpp.models import Autor, Wydawnictwo_Ciagle
    from cerif_export import const
    from cerif_export.providers import rejestr_providerow

    praca = baker.make(Wydawnictwo_Ciagle)
    praca.dodaj_autora(baker.make(Autor), jednostka)

    provider = rejestr_providerow()[const.SET_PUBLICATIONS]
    assert not provider.nagrobki(uczelnia, Wydawnictwo_Ciagle).filter(
        pk=praca.pk
    ).exists(), "rekord widoczny nie może być nagrobkiem"

    ukryj(praca, uczelnia)

    assert provider.nagrobki(uczelnia, Wydawnictwo_Ciagle).filter(
        pk=praca.pk
    ).exists(), "rekord przestał być widoczny, a nie dostał nagrobka"
```

⚠️ Jeśli fixture `uczelnia` nie ma statusu ukrytego w kanale `cerif`, dopisz go
w teście (`uczelnia.ukryte_statusy_cerif` albo pole równoważne — sprawdź
`grep -n "def ukryte_statusy" -A 15 src/bpp/models/uczelnia.py`) zamiast pomijać
przypadek.

- [ ] **Krok 8.2: Test — `from`/`until` obejmuje nagrobki**

Nagrobek utworzony „teraz" wpada w okno `od = wczoraj`, a wypada z okna
`do = wczoraj`. Znacznik bierze się z `ostatnio_zmieniony`, który soft-delete
bumpuje (kontrakt PINNED fazy 01).

- [ ] **Krok 8.3: Test — `resumptionToken` na granicy żywy/nagrobek**

Utwórz co najmniej `rozmiar + 1` obiektów tak, żeby strona kończyła się
**dokładnie na nagrobku**, przejdź harvest do końca po tokenach i sprawdź:
identyfikatory bez duplikatu (`len(set(...)) == len(...)`) i bez luki
(komplet oczekiwanych). Rozmiar strony wymuś przez `rozmiar=` albo
`const.ROZMIAR_STRONY` — patrz jak robi to `test_oai.py`.

To tu żyły wcześniejsze bugi `Trunc`/`tzinfo` opisane w `z_datestampem`.

- [ ] **Krok 8.4: Komenda + PASS**

```bash
uv run pytest src/cerif_export/tests/test_nagrobki.py -q
uv run pytest src/cerif_export/ -q
```

- [ ] **Krok 8.5: Commit**

```bash
uv run ruff check src/cerif_export/tests/test_nagrobki.py
uv run ruff format src/cerif_export/tests/test_nagrobki.py
git add src/cerif_export/tests/test_nagrobki.py
git commit -m "test(cerif): cztery drogi zniknięcia, okno from/until, granica strony"
```

---

## Task 9: `/api/v1/usuniete/`

**Files:**
- Create: `src/api_v1/serializers/usuniete.py`, `src/api_v1/viewsets/usuniete.py`,
  `src/api_v1/tests/test_usuniete.py`
- Modify: `src/api_v1/urls.py`

**Interfaces:**
- Produces: endpoint `GET /api/v1/usuniete/`, pola `model`, `pk`, `usuniety_od`.

⚠️ **REST znaczy WĘŻEJ niż OAI** (decyzja D5 specu): tu wychodzą wyłącznie rekordy
**z kosza**, nie całe dopełnienie ekspozycji. REST nie składa obietnicy
`deletedRecord`. Napisz to w docstringu viewsetu.

- [ ] **Krok 9.1: Failing test — endpoint listuje husk, bez treści**

```python
@pytest.mark.django_db
def test_usuniete_zwraca_nagrobek_bez_tresci(api_client, uczelnia, wydawnictwo_ciagle):
    """Nagrobek REST niesie identyfikator, nigdy treść.

    Rekord bywa usuwany właśnie dlatego, że był błędny albo zawierał dane
    osobowe — wystawienie huska w całości cofnęłoby skutek usunięcia.
    """
    tytul = wydawnictwo_ciagle.tytul_oryginalny
    wydawnictwo_ciagle.delete()

    odpowiedz = api_client.get("/api/v1/usuniete/")
    assert odpowiedz.status_code == 200

    tresc = odpowiedz.json()
    wyniki = tresc["results"]
    assert any(
        w["model"] == "wydawnictwo_ciagle" and w["pk"] == wydawnictwo_ciagle.pk
        for w in wyniki
    )
    assert tytul not in odpowiedz.content.decode(), (
        "treść usuniętego rekordu wyciekła przez endpoint nagrobków"
    )
```

⚠️ **Sprawdź, jak istniejące testy `src/api_v1/tests/` budują klienta i uwierzytelnienie**
(bramka `z_bramka_api_v1` + przełącznik `api_v1_dane_bibliograficzne` na `Uczelnia`)
i powiel ten wzorzec zamiast wymyślać `api_client`.

- [ ] **Krok 9.2: Komenda + FAIL**

Run: `uv run pytest src/api_v1/tests/test_usuniete.py -x -q`
Expected: FAIL — 404 (brak trasy).

- [ ] **Krok 9.3: Implementacja — serializer**

`src/api_v1/serializers/usuniete.py`:

```python
from rest_framework import serializers


class UsunietySerializer(serializers.Serializer):
    """Nagrobek: co zniknęło i kiedy — NIGDY treść rekordu.

    Świadomie ``Serializer``, nie ``ModelSerializer``: łączymy wiele modeli
    w jedną listę, a każde pole ponad te trzy byłoby wyciekiem danych,
    które redakcja usunęła.
    """

    model = serializers.CharField()
    pk = serializers.IntegerField()
    usuniety_od = serializers.DateTimeField()
```

- [ ] **Krok 9.4: Implementacja — viewset**

`src/api_v1/viewsets/usuniete.py`:

```python
from rest_framework import viewsets
from rest_framework.response import Response

from api_v1.serializers.usuniete import UsunietySerializer
from bpp.models import (
    Autor,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

#: Modele soft-delete wystawiane jako nagrobki. Klucz to nazwa w odpowiedzi.
MODELE_NAGROBKOW = {
    "wydawnictwo_ciagle": Wydawnictwo_Ciagle,
    "wydawnictwo_zwarte": Wydawnictwo_Zwarte,
    "patent": Patent,
    "praca_doktorska": Praca_Doktorska,
    "praca_habilitacyjna": Praca_Habilitacyjna,
    "autor": Autor,
}


class UsunieteViewSet(viewsets.ViewSet):
    """Rekordy usunięte (w koszu) — sam identyfikator i znacznik czasu.

    ⚠️ Znaczy WĘŻEJ niż nagrobek OAI-PMH. Tam nagrobek to „przestało być
    eksportowane" (dopełnienie ekspozycji), bo ``deletedRecord`` jest
    obietnicą wobec harvestera. REST takiej obietnicy nie składa, więc tu
    wychodzi wyłącznie kosz. Rekord ukryty przez ``nie_eksportuj_przez_api``
    dostanie nagrobek w OAI, ale NIE pojawi się tutaj (decyzja D5 specu
    2026-08-15).

    Treści rekordu nie wystawiamy nigdy — patrz ``UsunietySerializer``.
    """

    serializer_class = UsunietySerializer

    def list(self, request):
        wiersze = []
        for nazwa, model in MODELE_NAGROBKOW.items():
            for pk, usuniety_od in model.deleted_objects.values_list(
                "pk", "deleted_at"
            ):
                wiersze.append(
                    {"model": nazwa, "pk": pk, "usuniety_od": usuniety_od}
                )
        wiersze.sort(key=lambda w: (w["usuniety_od"] is None, w["usuniety_od"]))
        return Response({"results": UsunietySerializer(wiersze, many=True).data})
```

⚠️ **Zanim to napiszesz, zweryfikuj dwie rzeczy** i dostosuj kod:
1. `uv run python -c "from bpp.models import Wydawnictwo_Ciagle; print(Wydawnictwo_Ciagle.deleted_objects)"`
   — nazwa menedżera kosza i to, czy każdy z sześciu modeli go ma.
2. Czy `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna` są soft-delete
   (faza 02 objęła 5 modeli publikacji). Modele bez kosza **usuń ze słownika** —
   nie dopisuj obejść.

- [ ] **Krok 9.5: Implementacja — routing**

W `src/api_v1/urls.py`: import `UsunieteViewSet` oraz obok pozostałych rejestracji

```python
router.register(r"usuniete", UsunieteViewSet, basename="usuniete", grupa=DANE)
```

`basename` jest **obowiązkowy** — `ViewSet` bez `queryset` nie ma z czego go wywieść.
`grupa=DANE` (`GrupaApiV1.DANE_BIBLIOGRAFICZNE`) — nowej grupy NIE zakładamy
(Global Constraints).

- [ ] **Krok 9.6: Komenda + PASS**

```bash
uv run pytest src/api_v1/tests/test_usuniete.py -q
uv run pytest src/api_v1/ -q
```

- [ ] **Krok 9.7: Filtr zakresowy**

Dopisz test i obsługę parametrów `usuniety_od_after` / `usuniety_od_before`
(konwencja `DateTimeFromToRangeFilter` z pozostałych viewsetów — patrz
`src/api_v1/viewsets/patent.py:32`). Filtrowanie rób na queryset każdego modelu
(`deleted_at__gte` / `deleted_at__lte`), NIE na liście w Pythonie.

- [ ] **Krok 9.8: Lint + commit**

```bash
uv run ruff check src/api_v1/serializers/usuniete.py src/api_v1/viewsets/usuniete.py src/api_v1/urls.py src/api_v1/tests/test_usuniete.py
uv run ruff format src/api_v1/serializers/usuniete.py src/api_v1/viewsets/usuniete.py src/api_v1/urls.py src/api_v1/tests/test_usuniete.py
git add src/api_v1/serializers/usuniete.py src/api_v1/viewsets/usuniete.py src/api_v1/urls.py src/api_v1/tests/test_usuniete.py
git commit -m "feat(api_v1): endpoint /usuniete/ — nagrobki bez tresci rekordu"
```

---

## Task 10: Weryfikacja końcowa fazy

**Files:** `src/bpp/newsfragments/`, `docs/superpowers/`

- [ ] **Krok 10.1: Walidacja XSD odpowiedzi z nagrobkami**

`src/cerif_export/tests/xsd/` zawiera schematy. Znajdź test walidujący odpowiedź
(`grep -rn "xsd\|schema" src/cerif_export/tests/test_oai.py | head`) i **rozszerz go**
o przypadek z nagrobkiem — odpowiedź z `status="deleted"` musi przejść walidację.
Bez tego kroku łatwo wyemitować XML, który agregator odrzuci.

- [ ] **Krok 10.2: Pełna regresja**

```bash
uv run pytest src/cerif_export/ src/api_v1/ -q
uv run pytest -m "not playwright" -q
uv run pytest -m playwright -q
npx vitest run
```
Expected: wszystko zielono. Przy wolnym starcie kontenerów: `TC_MAX_TRIES=600`.

- [ ] **Krok 10.3: Brak driftu migracji (ta faza NIE dodaje migracji)**

```bash
uv run python src/manage.py makemigrations --check --dry-run
```
Expected: zero zgłoszeń dla aplikacji z `src/` (zgłoszenia dla pakietów
zewnętrznych — `favicon`, `flexible_reports`, `siteblog` — są zastane).

- [ ] **Krok 10.4: Newsfragment**

`src/bpp/newsfragments/soft-delete-nagrobki.feature.rst`:

```rst
Repozytorium OAI-PMH ogłasza teraz usunięcia: rekord, który przestał być
eksportowany, wychodzi w harveście jako nagrobek (nagłówek ze statusem
``deleted``) zamiast po prostu zniknąć. Dzięki temu systemy pobierające dane
przyrostowo mogą usunąć go u siebie. Nowy endpoint ``/api/v1/usuniete/``
udostępnia listę usuniętych rekordów — wyłącznie identyfikator i datę,
bez treści.
```

- [ ] **Krok 10.5: Ostrzeżenie operacyjne w dokumentacji przełącznika**

Znajdź dokumentację `Uczelnia.eksport_cerif_osoby`
(`grep -rn "eksport_cerif_osoby" docs/ src/bpp/models/uczelnia.py`) i dopisz:
wyłączenie przełącznika wystawia nagrobki dla **wszystkich** autorów uczelni
naraz. Zachowanie poprawne (harvester ma je usunąć), ale jednorazowo bardzo
duży wsad — operator musi o tym wiedzieć przed przestawieniem.

- [ ] **Krok 10.6: Handoff + commit**

Zaktualizuj `docs/superpowers/HANDOFF-soft-delete-faza-06.md` §5 (faza 05b
przestaje być „do zrobienia") i zacommituj całość:

```bash
git add src/bpp/newsfragments/soft-delete-nagrobki.feature.rst docs/
git commit -m "docs(soft-delete): newsfragment fazy 05b + ostrzezenie o eksport_cerif_osoby"
```

- [ ] **Krok 10.7: PR**

```bash
git push -u origin feat/soft-delete-05b
gh pr create --base feat/soft-delete-05 --head feat/soft-delete-05b \
  --title "soft-delete faza 05b — nagrobki dla konsumentów przyrostowych"
```

W opisie PR-a wymień: cztery decyzje specu, rozszczepienie przynależność/ekspozycja,
powód paginowania nadzbioru, oraz **wyniki przebiegu lokalnego** — CI nie biegnie
na PR-ach do gałęzi `feat/soft-delete*`, więc to jedyny dowód.

---

## Podsumowanie zakresu

| dostarczone | |
|---|---|
| `ProviderEncji.przynaleznosc()` + `nagrobki()` | kontrakt rozszczepiający przynależność i ekspozycję |
| `strona()` na nadzbiorze | jeden strumień, jeden kursor keyset, nagrobki w porządku dat |
| `status="deleted"` w ListRecords / ListIdentifiers / GetRecord | bez `<metadata>` |
| `deletedRecord = "transient"` | prawdziwa deklaracja zamiast `"no"` |
| `/api/v1/usuniete/` | identyfikator + data, bez treści huska |

**Poza zakresem (świadomie):** zmiana atrybucji tenanta bez śladu w koszu (przepięcie
autorstwa do innej uczelni) nadal znika po cichu; rekordy nigdy-niewidoczne też
dostają nagrobek; REST węższy niż OAI. Wszystkie trzy opisane w specu, sekcja
„Ograniczenia".
