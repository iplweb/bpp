# Redukcja zużycia pamięci w imporcie PBN — plan wdrożenia

> **Dla agentów:** WYMAGANA POD-UMIEJĘTNOŚĆ: użyj
> `superpowers:subagent-driven-development` (zalecane) lub
> `superpowers:executing-plans`, żeby zrealizować ten plan zadanie-po-zadaniu.
> Kroki używają składni checkboxów (`- [ ]`).

**Cel:** Zbić szczyt pamięci importu PBN z „cała tabela JSON-a w RAM" do
„garść wierszy" w pięciu funkcjach `pbn_integrator`, bez zmiany zachowania.

**Architektura:** Każda zmiana zastępuje materializację całego QuerySet-a
(`list(...)` / `tqdm(qs)` / `pbar(qs)`) jednym z dwóch kanonicznych wzorców ze
specyfikacji: **A** = lista kluczy (`values_list("pk")`) + leniwy `.get()`;
**B** = `.values_list(pola).iterator(chunk_size=N)` dla pętli tylko-do-odczytu.
Plus `Subquery` zamiast `pk__in=list(...)`.

**Stack:** Python 3.13, Django ORM, pytest + `model_bakery`, testcontainers
(PostgreSQL). Wszystko przez `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-04-pbn-import-pamiec-design.md`

---

## Metodyka testów (przeczytaj zanim zaczniesz)

To są **refaktory zachowujące zachowanie**, nie nowa funkcjonalność. Dlatego
część testów to **testy charakteryzujące** — są zielone *przed i po* zmianie i
pełnią rolę siatki bezpieczeństwa, a sama redukcja pamięci jest gwarantowana
strukturalnie przez diff (że używa `.iterator()` / listy ID / `Subquery`). Gdzie
to zaznaczono, krok „uruchom test" oczekuje **PASS na obecnym kodzie** (baseline
charakteryzujący) — to celowe, nie błąd. Tam gdzie da się uzyskać prawdziwy RED,
jest to wskazane wprost.

Uruchamianie pojedynczego pliku testów (z włączonym reuse kontenerów dla
szybkości):

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest <ścieżka>::<test> -q
```

Komendy `git` wykonuj w worktree branch-a docelowego. **Każde zadanie =
osobny commit.** Po każdej zmianie: `uv run ruff format <pliki>` i
`uv run ruff check <pliki>`.

---

## Task 0: `importuj_zrodla` (źródła) — ✅ ZROBIONE

Zrealizowane na branchu `feature/pbn-zrodla-mem` (Wzorzec A + `Subquery`).
Referencja implementacyjna i testowa dla pozostałych zadań:

- `src/pbn_integrator/importer/sources.py` — `_process_journal_thread_safe`
  przyjmuje `journal_id`, ładuje `Journal.objects.get(pk=...)` w workerze;
  `importuj_zrodla` zbiera `values_list("pk", flat=True)`.
- `src/pbn_integrator/tests/test_importuj_zrodla_memory.py` — wzór testów
  (helper `_make_active_journal`, monkeypatch workera, asercja „dyspozytor
  dostaje ID-stringi").

Nic do zrobienia — pozycja dla kompletności inwentarza.

---

## Task 1: `importuj_publikacje_instytucji` — wąski strumień zamiast hydratacji

Najcięższy model (`Publication.versions`). Pętla czyta wyłącznie `.mongoId`,
więc po naprawie nie ładuje JSON-a w ogóle.

**Files:**
- Modify: `src/pbn_integrator/importer/__init__.py:122-145` (+ importy)
- Test: `src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py`

- [ ] **Step 1: Napisz test charakteryzujący (wąska dyspozycja ID)**

```python
"""Pamięciowy refactor importu publikacji instytucji.

Pętla dyspozytora czyta tylko ``mongoId`` -> po naprawie iteruje
``values_list("mongoId").iterator()`` i nie hydratuje ciężkiego
``Publication.versions``. Test charakteryzujący: każda ACTIVE publikacja
trafia do ``importuj_publikacje_po_pbn_uid_id`` dokładnie raz jako string.
"""

from unittest.mock import Mock

import pytest
from model_bakery import baker

from bpp.models import Rodzaj_Zrodla
from pbn_api.models import Publication


def _make_active_publication(title="Pub testowa"):
    return baker.make(
        Publication,
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"title": title, "type": "ARTICLE"},
            }
        ],
    )


@pytest.mark.django_db
def test_importuj_publikacje_instytucji_dispatches_mongoids(monkeypatch):
    from pbn_integrator import importer as importer_mod

    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    pub = _make_active_publication()

    captured = []

    def fake_dispatch(mongo_id, **kwargs):
        captured.append(mongo_id)
        return None

    monkeypatch.setattr(
        importer_mod, "importuj_publikacje_po_pbn_uid_id", fake_dispatch
    )

    importer_mod.importuj_publikacje_instytucji(
        client=Mock(), default_jednostka=Mock(), pbn_uid_id=None
    )

    assert captured == [pub.mongoId]
    assert all(isinstance(m, str) for m in captured)
```

- [ ] **Step 2: Uruchom test — baseline (oczekiwany PASS na obecnym kodzie)**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py -q
```
Oczekiwane: PASS (charakteryzacja istniejącego zachowania).

- [ ] **Step 3: Refactor — `Subquery` + `values_list` + `.iterator()`**

W `src/pbn_integrator/importer/__init__.py` dodaj import (jeśli brak):

```python
from django.db.models import Subquery
from bpp.util import pbar
```

Zamień ciało `importuj_publikacje_instytucji` (linie ~125-142):

```python
    # Wyklucz już zaimportowane (re-entrancy) — wykluczenie zostaje w SQL
    # przez Subquery (zamiast ściągać całą listę ID do Pythona):
    niechciane = Rekord.objects.values_list("pbn_uid_id", flat=True)
    chciane = Publication.objects.exclude(pk__in=Subquery(niechciane))

    if pbn_uid_id:
        chciane = chciane.filter(pk=pbn_uid_id)

    # Cache słowników RAZ przed pętlą
    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

    # Strumieniuj wyłącznie mongoId (zero hydratacji versions JSON):
    total = chciane.count()
    for mongo_id in pbar(
        chciane.values_list("mongoId", flat=True).iterator(chunk_size=200),
        count=total,
    ):
        ret = importuj_publikacje_po_pbn_uid_id(
            mongo_id,
            client=client,
            default_jednostka=default_jednostka,
            rodzaj_periodyk=rodzaj_periodyk,
            dyscypliny_cache=dyscypliny_cache,
        )

        if pbn_uid_id:
            return ret
```

- [ ] **Step 4: Uruchom test — nadal zielony**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/pbn_integrator/importer/__init__.py \
  src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py
uv run ruff check src/pbn_integrator/importer/__init__.py \
  src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py
git add src/pbn_integrator/importer/__init__.py \
  src/pbn_integrator/tests/test_importuj_publikacje_instytucji_memory.py
git commit -m "perf(pbn_import): strumieniuj importuj_publikacje_instytucji (values_list+iterator+Subquery)"
```

---

## Task 5: `pobierz_prace_po_doi` / `pobierz_prace_po_isbn` — `values_list` zamiast hydratacji `Rekord`

Pętle czytają tylko `.doi` / `.isbn`, a hydratują pełny `Rekord`. Najpierw
**wyodrębniamy** zbieranie do testowalnych helperów, potem zmieniamy na
`values_list(...).iterator()`.

**Files:**
- Modify: `src/pbn_integrator/utils/publications.py:249-329`
- Test: `src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py`

- [ ] **Step 1: Napisz test helperów zbierających**

```python
"""Zbieranie DOI/ISBN do pobrania nie hydratuje pełnych Rekordów."""

import pytest
from model_bakery import baker

from bpp.const import PBN_MIN_ROK
from bpp.models import Rekord


@pytest.mark.django_db
def test_zbierz_doi_pomija_puste_i_stare_oraz_normalizuje():
    from pbn_integrator.utils.publications import _zbierz_doi_do_pobrania

    baker.make(Rekord, doi="10.1/AbC", rok=PBN_MIN_ROK, pbn_uid_id=None)
    baker.make(Rekord, doi="", rok=PBN_MIN_ROK, pbn_uid_id=None)        # puste -> pomiń
    baker.make(Rekord, doi="10.2/x", rok=PBN_MIN_ROK - 1, pbn_uid_id=None)  # za stare -> pomiń

    dois = _zbierz_doi_do_pobrania()

    from pbn_integrator.utils.django_imports import normalize_doi
    assert dois == {normalize_doi("10.1/AbC")}
```

> Uwaga dla wykonawcy: `Rekord` to model z wieloma polami — `baker.make` może
> wymagać dodatkowych pól NOT NULL. Jeśli `baker.make(Rekord, ...)` rzuca, użyj
> istniejących fixtures pełnego rekordu (`src/conftest.py`,
> np. `wydawnictwo_ciagle`) i ustaw `doi`/`rok` na jego `Rekord`.

- [ ] **Step 2: Uruchom test — oczekiwany FAIL (`ImportError`)**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py -q
```
Oczekiwane: FAIL — `cannot import name '_zbierz_doi_do_pobrania'`.

- [ ] **Step 3: Wyodrębnij helper + przełącz na `values_list().iterator()`**

W `src/pbn_integrator/utils/publications.py` dodaj helper i użyj go w
`pobierz_prace_po_doi`:

```python
def _zbierz_doi_do_pobrania():
    """Zbierz znormalizowane DOI prac bez pbn_uid (tylko odczyt, bez hydratacji)."""
    from pbn_integrator.utils.django_imports import normalize_doi

    dois = set()
    for doi in (
        Rekord.objects.exclude(doi=None)
        .exclude(doi="")
        .filter(pbn_uid_id=None, rok__gte=PBN_MIN_ROK)
        .values_list("doi", flat=True)
        .iterator(chunk_size=500)
    ):
        dois.add(normalize_doi(doi))
    return dois
```

I w `pobierz_prace_po_doi` zastąp pętlę `for praca in pbar(Rekord.objects...)`:

```python
def pobierz_prace_po_doi(client: PBNClient):
    """Fetch publications by DOI."""
    dois = _zbierz_doi_do_pobrania()

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    p = initialize_pool()
    results = []
    for doi in dois:
        results.append(
            p.apply_async(_pobierz_prace_po_elemencie, args=(client, "doi", doi))
        )
    wait_for_results(p, results)
```

- [ ] **Step 4: Uruchom test — PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 5: Analogicznie ISBN + test**

Dodaj `_zbierz_isbn_do_pobrania()` (filtr jak w oryginale, w tym
`wydawnictwo_nadrzedne_id=None`, `normalize_isbn`) i przełącz
`pobierz_prace_po_isbn`. Dopisz `test_zbierz_isbn_...` analogiczny do DOI.

```python
def _zbierz_isbn_do_pobrania():
    from pbn_integrator.utils.django_imports import normalize_isbn

    isbns = set()
    for isbn in (
        Rekord.objects.exclude(isbn=None)
        .exclude(isbn="")
        .filter(pbn_uid_id=None, rok__gte=PBN_MIN_ROK, wydawnictwo_nadrzedne_id=None)
        .values_list("isbn", flat=True)
        .iterator(chunk_size=500)
    ):
        isbns.add(normalize_isbn(isbn))
    return isbns
```

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff format src/pbn_integrator/utils/publications.py \
  src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py
uv run ruff check src/pbn_integrator/utils/publications.py \
  src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py
git add src/pbn_integrator/utils/publications.py \
  src/pbn_integrator/tests/test_pobierz_prace_doi_isbn_memory.py
git commit -m "perf(pbn_import): zbieranie DOI/ISBN przez values_list+iterator (bez hydratacji Rekord)"
```

---

## Task 4: `importuj_wydawcow` — `.iterator()` zamiast `list(...)`

`Publisher` niesie `versions` JSON; funkcja jest w `transaction.atomic`, więc
kursor serwerowy `.iterator()` jest bezpieczny.

**Files:**
- Modify: `src/pbn_integrator/importer/publishers.py:162-176`
- Test: `src/pbn_integrator/tests/test_importuj_wydawcow_memory.py`

- [ ] **Step 1: Test charakteryzujący (każdy wydawca przetworzony raz)**

```python
"""importuj_wydawcow strumieniuje wydawców, ale przetwarza każdego raz."""

import pytest
from model_bakery import baker

from pbn_api.models import Publisher


@pytest.mark.django_db
def test_importuj_wydawcow_przetwarza_kazdego_raz(monkeypatch):
    from pbn_integrator.importer import publishers as pub_mod

    p1 = baker.make(Publisher, status="ACTIVE", publisherName="A")
    p2 = baker.make(Publisher, status="ACTIVE", publisherName="B")

    seen = []

    def fake_one(publisher):
        seen.append(publisher.pk)
        return False  # brak needs_mapping -> nie odpala call_command

    monkeypatch.setattr(pub_mod, "importuj_jednego_wydawce", fake_one)

    pub_mod.importuj_wydawcow()

    assert set(seen) == {p1.pk, p2.pk}
    assert len(seen) == 2
```

> Uwaga: jeśli `Publisher.objects.official()` filtruje (np. tylko z `mniswId`/
> ACTIVE), dostosuj `baker.make` tak, by oba obiekty przechodziły filtr
> `official()` (sprawdź definicję managera w `pbn_api/models/publisher.py`).

- [ ] **Step 2: Uruchom — baseline PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_importuj_wydawcow_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 3: Refactor na `.iterator()`**

W `importuj_wydawcow` zastąp `publishers = list(Publisher.objects.official())`:

```python
def importuj_wydawcow(verbosity=1, callback=None):
    needs_mapping = False
    qs = Publisher.objects.official()
    total = qs.count()
    imported = 0
    logger.info(f"Importowanie wydawców: {total} wydawców do przetworzenia")

    with transaction.atomic():
        for i, publisher in enumerate(qs.iterator(chunk_size=200), 1):
            if importuj_jednego_wydawce(publisher):
                needs_mapping = True
                imported += 1
            if callback:
                callback.update(i, total, f"Zaimportowano: {imported}")

    if needs_mapping:
        logger.info("Importowanie wydawców: uruchamiam mapowanie do publikacji...")
        call_command("zamapuj_wydawcow")
        logger.info("Importowanie wydawców: mapowanie zakończone")
```

- [ ] **Step 4: Uruchom — PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_importuj_wydawcow_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/pbn_integrator/importer/publishers.py \
  src/pbn_integrator/tests/test_importuj_wydawcow_memory.py
uv run ruff check src/pbn_integrator/importer/publishers.py \
  src/pbn_integrator/tests/test_importuj_wydawcow_memory.py
git add src/pbn_integrator/importer/publishers.py \
  src/pbn_integrator/tests/test_importuj_wydawcow_memory.py
git commit -m "perf(pbn_import): importuj_wydawcow przez iterator (bez list() całej tabeli)"
```

---

## Task 3: `integruj_oswiadczenia_z_instytucji` — lista ID

`OswiadczenieInstytucji` niesie `disciplines` JSON. Pętla potrzebuje obiektu
(woła `integruj_..._pojedyncza_praca(elem, ...)`), więc **Wzorzec A** (lista ID
+ leniwy `.get()`) — bezpieczny także gdyby pętla coś dopisywała.

**Files:**
- Modify: `src/pbn_integrator/utils/statements.py:302-331`
- Test: `src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py`

- [ ] **Step 1: Test charakteryzujący**

```python
"""integruj_oswiadczenia_z_instytucji przechodzi po wszystkich wierszach."""

import pytest
from model_bakery import baker

from pbn_api.models import OswiadczenieInstytucji


@pytest.mark.django_db
def test_integruj_oswiadczenia_przetwarza_wszystkie(monkeypatch):
    from pbn_integrator.utils import statements as st

    o1 = baker.make(OswiadczenieInstytucji)
    o2 = baker.make(OswiadczenieInstytucji)

    seen = []
    monkeypatch.setattr(
        st,
        "integruj_oswiadczenia_z_instytucji_pojedyncza_praca",
        lambda elem, *a, **k: seen.append(elem.pk),
    )

    st.integruj_oswiadczenia_z_instytucji()

    assert set(seen) == {o1.pk, o2.pk}
```

> Uwaga: `baker.make(OswiadczenieInstytucji)` może wymagać FK (publicationId,
> personId, institutionId). Jeśli rzuca — użyj `baker.make(..., _fill_optional=False)`
> i ustaw wymagane FK na zbake-owane `Publication`/`Scientist`/`Institution`.

- [ ] **Step 2: Uruchom — baseline PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 3: Refactor na listę ID**

Zastąp pętlę `for elem in pbar(OswiadczenieInstytucji.objects.all(), ...)`:

```python
    noted_pub = set()
    noted_aut = set()
    ids = list(OswiadczenieInstytucji.objects.values_list("pk", flat=True))
    for pk in pbar(ids, label="integruj_oswiadczenia_z_instytucji", callback=callback):
        elem = OswiadczenieInstytucji.objects.get(pk=pk)
        integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
            elem,
            noted_pub,
            noted_aut,
            missing_publication_callback,
            inconsistency_callback,
            default_jednostka,
        )
```

- [ ] **Step 4: Uruchom — PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py
uv run ruff check src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py
git add src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_integruj_oswiadczenia_memory.py
git commit -m "perf(pbn_import): integruj_oswiadczenia_z_instytucji na listę ID (Wzorzec A)"
```

---

## Task 2: `integruj_oswiadczenia_pbn_first_import` — lista ID (zapis w pętli!)

Pętla w środku **importuje publikacje** (potencjalnie wstawia/modyfikuje wiersze),
więc kursor serwerowy jest wykluczony — **wymagany Wzorzec A** (migawka listy ID).
To najwrażliwsza zmiana — robić na końcu.

**Files:**
- Modify: `src/pbn_integrator/utils/statements.py:348-...` (sama pętla `for`)
- Test: `src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py`

- [ ] **Step 1: Test charakteryzujący (iteracja po migawce ID)**

```python
"""first_import iteruje po migawce ID — nowe wiersze w trakcie nie wpadają."""

import pytest
from model_bakery import baker

from pbn_api.models import OswiadczenieInstytucji


@pytest.mark.django_db
def test_first_import_iteruje_po_migawce(monkeypatch):
    from pbn_integrator.utils import statements as st

    o1 = baker.make(OswiadczenieInstytucji)
    o2 = baker.make(OswiadczenieInstytucji)

    seen = []

    def fake_get_bpp_publication(self):
        seen.append(self.pk)
        # symuluj zapis w trakcie pętli — NIE może zwiększyć liczby iteracji:
        baker.make(OswiadczenieInstytucji)
        return object()  # cokolwiek != None, by ominąć gałąź importu

    monkeypatch.setattr(
        OswiadczenieInstytucji, "get_bpp_publication", fake_get_bpp_publication
    )
    # zneutralizuj resztę ciała pętli (zależnie od implementacji — patrz Uwaga):
    monkeypatch.setattr(st, "_first_import_obsluz_oswiadczenie", lambda *a, **k: None, raising=False)

    st.integruj_oswiadczenia_pbn_first_import(client=None, default_jednostka=None)

    # mimo wstawiania nowych wierszy w trakcie — dokładnie 2 oryginalne:
    assert sorted(seen) == sorted([o1.pk, o2.pk])
```

> Uwaga: ciało pętli `integruj_oswiadczenia_pbn_first_import` jest długie
> (`# noqa: C901`). Przed testem przeczytaj całą funkcję
> (`src/pbn_integrator/utils/statements.py:334-...`) i zneutralizuj monkeypatch-em
> te części, które wymagają klienta PBN / sieci, tak by test ćwiczył wyłącznie
> kontrakt iteracji „po migawce ID". Jeśli ciało jest nierozłączne, najpierw
> wyodrębnij je do funkcji `_first_import_obsluz_oswiadczenie(oswiadczenie, ...)`
> (osobny commit-refactor) i dopiero potem zmień iterację.

- [ ] **Step 2: Uruchom — oczekiwany FAIL na obecnym kodzie (prawdziwy RED)**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py -q
```
Oczekiwane: FAIL — obecne `tqdm(OswiadczenieInstytucji.objects.all())` iteruje po
QuerySet, którego `_result_cache` jest budowany leniwie; wstawiony w trakcie
wiersz **może** wpaść do iteracji (zachowanie zależne od momentu `_fetch_all`),
co czyni asercję „dokładnie 2" niestabilną/fałszywą. Migawka ID to gwarantuje.

- [ ] **Step 3: Refactor — migawka listy ID**

Zastąp `for oswiadczenie in tqdm(OswiadczenieInstytucji.objects.all()):`:

```python
    ids = list(OswiadczenieInstytucji.objects.values_list("pk", flat=True))
    for pk in tqdm(ids):
        oswiadczenie = OswiadczenieInstytucji.objects.get(pk=pk)
        ...  # reszta ciała pętli bez zmian
```

(reszta ciała `first` itd. bez zmian).

- [ ] **Step 4: Uruchom — PASS**

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py -q
```
Oczekiwane: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py
uv run ruff check src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py
git add src/pbn_integrator/utils/statements.py \
  src/pbn_integrator/tests/test_oswiadczenia_first_import_memory.py
git commit -m "perf(pbn_import): first_import oświadczeń na migawkę listy ID (Wzorzec A)"
```

---

## Po wszystkich zadaniach — weryfikacja końcowa

- [ ] Pełna regresja suit importera:

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest \
  src/pbn_integrator/tests/ src/pbn_import/tests/ -q
```
Oczekiwane: wszystko zielone.

- [ ] (Opcjonalnie, manualnie) Walidacja pamięci na zaseedowanej bazie —
  porównaj szczyt RSS kroku importu źródeł/publikacji przed i po
  (`/usr/bin/time -l uv run python src/manage.py pbn_import ...` lub
  `tracemalloc` wokół konkretnego kroku). Spodziewany spadek szczytu z
  rzędu GB do dziesiątek/setek MB.

## Self-review (wykonane przy pisaniu planu)

- **Pokrycie specu:** zadania 1–5 = punkty 1–5 inwentarza; punkt 0 oznaczony
  jako zrobiony (Task 0). Brak luk.
- **Typy/sygnatury:** `_zbierz_doi_do_pobrania` / `_zbierz_isbn_do_pobrania`
  używane spójnie w Task 5; `importuj_publikacje_po_pbn_uid_id` wołane z
  `mongo_id: str` zgodnie z istniejącą sygnaturą.
- **Ryzyka oznaczone:** Task 2 (zapis w pętli → Wzorzec A, prawdziwy RED),
  Task 4 (`.iterator()` w `transaction.atomic` — OK w PostgreSQL).
