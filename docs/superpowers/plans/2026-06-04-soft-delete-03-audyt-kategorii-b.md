# Soft-delete — Faza 03: audyt kategorii B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przełączyć miejsca matchingu importu/dedupu/PBN na `global_objects`, żeby re-import lub deduplikacja NIE tworzyły duplikatów rekordów skasowanych miękko, oraz wymusić jawny `.hard_delete()` tam, gdzie kod celowo czyści fizycznie przed re-importem.

**Architecture:** Po fazie 02 modele 5 publikacji są `SoftDeleteModel`; domyślny menedżer `objects` ukrywa skasowane (kategoria A — czysta automatycznie). Kategoria B to miejsca, które MUSZĄ widzieć skasowane: matching przez `pbn_uid` / DOI / ISBN / tytuł podczas re-importu i dedup. Jeśli te miejsca użyją ukrywającego menedżera, skasowany rekord stanie się „niewidzialny" → import utworzy DUPLIKAT (a denormalizowany warunkowy `slug` z fazy 02 i tak będzie kolidował dopiero przy restore). Dlatego matching przełączamy na `global_objects`. Osobno: `pbn_import` czyści publikacje PBN fizycznie przed re-importem — po fazie 02 `.delete()` na querysecie stałby się soft → trzeba jawnie `.hard_delete()`.

**Tech Stack:** Django, PostgreSQL, `django-soft-delete>=1.0.23` (`objects` / `global_objects` / `deleted_objects`, `.hard_delete()`), pytest + model_bakery (`baker.make`).

---

## Zależności i kontrakty (z fazy 02 + indeksu 00)

- **Zależy od fazy 02.** Po fazie 02:
  - `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Praca_Doktorska`,
    `Praca_Habilitacyjna`, `Patent`, oraz `Wydawnictwo_Ciagle_Autor`,
    `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` są `SoftDeleteModel`.
  - Menedżery (VERBATIM z indeksu 00): `objects` (ukrywa skasowane),
    `global_objects` (wszystkie), `deleted_objects` (tylko skasowane).
  - Metody instancji: `.delete()` (soft), `.hard_delete()` (fizyczny),
    `.restore()`.
  - Menedżery publikacji (`Wydawnictwo_Ciagle_Manager`,
    `Wydawnictwo_Zwarte_Manager`) mają przepleciony filtr soft-delete —
    `.objects` zwraca tylko nieusunięte, ale nadal udostępnia metody
    domenowe (`wydawnictwa_nadrzedne_dla_innych()` itd.). **`global_objects`
    pochodzi z `GlobalManager` pakietu i NIE ma metod domenowych** — przy
    przełączaniu sprawdzić, czy dane miejsce nie woła metody domenowej (jeśli
    woła — patrz nota w odpowiednim Tasku).
- **Niezmienna reguła BPP:** NIE modyfikować istniejących plików migracji
  w `src/*/migrations/`. Ten plan nie tworzy migracji (zmiany tylko w kodzie
  zapytań + testy).
- **Linia ≤88 znaków** (ruff). Komendy Pythona przez `uv run`.
- **Testy:** pytest, standalone functions, `@pytest.mark.django_db`,
  `baker.make`. Bez `unittest.TestCase`.

---

## Mapa plików tej fazy

**Modyfikowane (produkcyjne):**
- `src/pbn_api/models/publication.py` — `rekord_w_bpp`, `get_bpp_publication`,
  `matchuj_do_rekordu_bpp` matchują przez `Rekord` (cache-view filtrowany po
  `deleted_at`) → przełączyć na matching widzący skasowane (`global_objects`
  modeli źródłowych).
- `src/import_common/core/publikacja.py` — `matchuj_publikacje` i 6 helperów
  `_try_match_pub_by_*` używają `klass.objects` → `klass` ma dostać menedżer
  widzący skasowane.
- `src/deduplikator_publikacji/tasks.py:140,147` — skanowanie do dedupu na
  `.objects` (pomija skasowane — poprawne, ale udokumentować decyzję; bez
  zmiany kodu).
- `src/pbn_integrator/importer/chapters.py:64` — `Wydawnictwo_Zwarte.objects
  .get(pbn_uid_id=...)` (matching książki-matki rozdziału) → `global_objects`.
- `src/pbn_import/utils/publication_import.py:115-116` — jawny `.hard_delete()`
  zamiast `.delete()` (kod celowo czyści fizycznie przed re-importem).
- `src/deduplikator_autorow/utils/merge.py:172,178,265,271,335,341` —
  transfer through-rows duplikatu → `global_objects` (łapie kaskadowo
  soft-deletowane autorstwa; inaczej zostaną sieroty blokujące guard fazy 04).

**Tworzone (testy):**
- `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

**Bez zmian (decyzja audytu udokumentowana w planie):**
- 90 miejsc `*_Autor.objects` w ewaluacji / API / przemapuj — patrz Task 7.
- `src/komparator_pbn/views.py`, `src/snapshot_odpiec/tasks.py`,
  `src/ewaluacja_dwudyscyplinowcy/core.py` — patrz Task 7.

---

## Task 1: Test bazowy — re-import po soft-delete znajduje rekord przez `pbn_uid` (FAIL przed zmianą)

Po fazie 02 `Rekord` (cache-view `bpp_rekord_mat`/`bpp_rekord`) jest filtrowany
po `deleted_at` (faza 01). `pbn_api.Publication.rekord_w_bpp` matchuje przez
`Rekord.objects.get(pbn_uid_id=...)` — więc dla soft-deletowanej publikacji
zwróci `None` (rekord zniknął z widoku), a importer utworzy DUPLIKAT. Ten test
to pokazuje.

**Files:**
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Utwórz katalog testów i napisz failing test**

Utwórz `src/bpp/tests/test_soft_delete/__init__.py` (pusty) oraz
`src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_get_bpp_publication_widzi_soft_deletowany_rekord():
    """Re-import: matching po pbn_uid MUSI znaleźć soft-deletowaną
    publikację, inaczej importer utworzy duplikat."""
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Testowy artykuł",
        rok=2020,
        pbn_uid=publication,
    )
    rec.delete()  # soft-delete

    assert Wydawnictwo_Ciagle.objects.filter(pk=rec.pk).count() == 0
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=rec.pk).count() == 1

    znaleziony = publication.get_bpp_publication()
    assert znaleziony is not None, (
        "matching po pbn_uid musi widzieć soft-deletowany rekord"
    )
    assert znaleziony.pk == rec.pk
```

- [ ] **Step 2: Uruchom test — ma FAILować**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_get_bpp_publication_widzi_soft_deletowany_rekord -v`
Expected: FAIL — `znaleziony is None` (`Rekord.objects.get(pbn_uid_id=...)`
nie widzi soft-deletowanego rekordu, bo widok `bpp_rekord` jest filtrowany).

- [ ] **Step 3: Commit testu**

```bash
git add src/bpp/tests/test_soft_delete/__init__.py \
    src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "test(soft-delete): re-import po pbn_uid widzi soft-deletowany rekord (failing)"
```

---

## Task 2: `get_bpp_publication` matchuje po `pbn_uid` przez `global_objects` modeli źródłowych

`Rekord` to widok (`managed=False`), NIE `SoftDeleteModel` — nie ma
`global_objects`. Matching po `pbn_uid` musi odpytać modele źródłowe ich
menedżerem `global_objects`. `pbn_uid` jest unikalny w obrębie typu, więc
przeszukujemy 5 modeli i zwracamy pierwsze trafienie.

**Files:**
- Modify: `src/pbn_api/models/publication.py:121-128` (`get_bpp_publication`)

- [ ] **Step 1: Podejrzyj obecny kod (kontekst)**

`get_bpp_publication` (linie 121-128) i `rekord_w_bpp` (130-143) matchują
przez `Rekord.objects.get(pbn_uid_id=self.pk)`.

- [ ] **Step 2: Dodaj helper i przepisz `get_bpp_publication`**

Zamień metodę `get_bpp_publication` (linie 121-128) na:

```python
    def _modele_publikacji_global(self):
        """Modele publikacji z menedżerem widzącym soft-deletowane.
        Rekord (widok) NIE ma global_objects, więc matching po pbn_uid
        idzie po modelach źródłowych."""
        from bpp.models import (
            Patent,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
        )

        return [
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Patent,
        ]

    def get_bpp_publication(self):
        """Zwraca rekord BPP powiązany przez PBN UID (bez fuzzy matching).

        Używa global_objects, więc widzi też soft-deletowane rekordy —
        inaczej re-import utworzyłby duplikat skasowanej publikacji.
        """
        for klass in self._modele_publikacji_global():
            obj = klass.global_objects.filter(pbn_uid_id=self.pk).first()
            if obj is not None:
                return obj
        return None
```

- [ ] **Step 3: Uruchom test Task 1 — ma PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_get_bpp_publication_widzi_soft_deletowany_rekord -v`
Expected: PASS

- [ ] **Step 4: ruff**

Run: `ruff format src/pbn_api/models/publication.py && ruff check src/pbn_api/models/publication.py`
Expected: brak błędów

- [ ] **Step 5: Commit**

```bash
git add src/pbn_api/models/publication.py
git commit -m "fix(soft-delete): get_bpp_publication matchuje po pbn_uid przez global_objects"
```

---

## Task 3: `rekord_w_bpp` widzi soft-deletowany rekord (re-import przez pbn_integrator)

`pbn_integrator/importer/books.py:44` i `articles.py:62` matchują istniejący
rekord przez `pbn_publication.rekord_w_bpp` i pomijają tworzenie, gdy
`ret is not None`. `rekord_w_bpp` (linie 130-143) wciąż używa
`Rekord.objects.get(pbn_uid_id=...)` → dla soft-deletowanego zwróci None →
duplikat. Trzeba je oprzeć na `get_bpp_publication` (już naprawione w Task 2),
zachowując dotychczasowy fallback do fuzzy-matchingu (`matchuj_do_rekordu_bpp`)
i obsługę „wielu rekordów o tym samym pbn_uid".

**Files:**
- Modify: `src/pbn_api/models/publication.py:130-143` (`rekord_w_bpp`)
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Dopisz failing test re-importu (pbn_integrator)**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_rekord_w_bpp_widzi_soft_deletowany_rekord():
    """rekord_w_bpp (używany przez pbn_integrator do pominięcia tworzenia)
    musi zwrócić soft-deletowany rekord, inaczej powstanie duplikat."""
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Artykuł do re-importu",
        rok=2021,
        pbn_uid=publication,
    )
    rec.delete()

    # cached_property — świeża instancja, żeby nie czytać cache
    publication_fresh = Publication.objects.get(pk=publication.pk)
    assert publication_fresh.rekord_w_bpp is not None
    assert publication_fresh.rekord_w_bpp.pk == rec.pk
```

- [ ] **Step 2: Uruchom — ma FAILować**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_rekord_w_bpp_widzi_soft_deletowany_rekord -v`
Expected: FAIL — `rekord_w_bpp is None` (matching przez widok `bpp_rekord`).

- [ ] **Step 3: Przepisz `rekord_w_bpp`**

Zamień metodę `rekord_w_bpp` (linie 130-143) na:

```python
    @cached_property
    def rekord_w_bpp(self):
        from bpp.models.cache import Rekord

        # Najpierw szybki lookup po pbn_uid w modelach źródłowych
        # (global_objects — widzi też soft-deletowane, by re-import nie
        # tworzył duplikatu). Obsługa "wielu rekordów o tym samym pbn_uid"
        # jak dotychczas: zwróć łańcuch tytułów (sygnał błędu danych).
        trafienia = [
            obj
            for klass in self._modele_publikacji_global()
            for obj in klass.global_objects.filter(pbn_uid_id=self.pk)
        ]
        if len(trafienia) == 1:
            # Zwróć obiekt Rekord (zachowanie zgodne z poprzednim API),
            # czytając z global widoku po pk modelu źródłowego.
            obj = trafienia[0]
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_model(type(obj))
            rec = Rekord.objects.filter(
                content_type=ct, object_id=obj.pk
            ).first()
            # Soft-deletowany rekord znika z widoku Rekord — wtedy zwróć
            # obiekt źródłowy (importer i tak używa go tylko do .pk).
            return rec if rec is not None else obj
        if len(trafienia) > 1:
            return ";; ".join(o.tytul_oryginalny for o in trafienia)

        return self.matchuj_do_rekordu_bpp()
```

> **Nota:** importer (`books.py`/`articles.py`) używa `rekord_w_bpp` wyłącznie
> jako „czy istnieje" + dostęp do pól; zwrócenie obiektu źródłowego zamiast
> `Rekord` dla soft-deletowanego rekordu jest bezpieczne (oba mają `pk`,
> `tytul_oryginalny`). Dla niesoft-deletowanych zachowujemy zwrot `Rekord`.

- [ ] **Step 4: Uruchom oba testy pbn_uid — mają PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py -k "widzi_soft_deletowany" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Regresja — pbn_api publication**

Run: `uv run pytest src/pbn_api/ -k "rekord_w_bpp or get_bpp_publication or publication" -q`
Expected: PASS (brak regresji na istniejących testach matchingu).

- [ ] **Step 6: ruff + commit**

```bash
ruff format src/pbn_api/models/publication.py
ruff check src/pbn_api/models/publication.py
git add src/pbn_api/models/publication.py src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "fix(soft-delete): rekord_w_bpp widzi soft-deletowane rekordy (re-import bez duplikatów)"
```

---

## Task 4: `import_common.matchuj_publikacje` matchuje przez `global_objects`

`matchuj_publikacje(klass, ...)` (`src/import_common/core/publikacja.py:264`)
i 6 helperów (`_try_match_pub_by_doi/zrodlo/isbn/uri/title`,
`_build_isbn_query`) używają `klass.objects`. Przy `klass = Wydawnictwo_*`
soft-deletowane rekordy są ukryte → fuzzy-matching nie znajdzie skasowanego
duplikatu → re-import go odtworzy. Trzeba odpytywać widzącym menedżerem.

> **Uwaga na metodę domenową:** `_build_isbn_query` woła
> `Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych()` — to metoda
> menedżera domenowego, której `global_objects` (`GlobalManager` pakietu) NIE
> ma. Dla matchingu po ISBN „tylko nadrzędne" akceptujemy, że nadrzędne
> liczone są spośród nieusuniętych (książka-matka skasowana → i tak PROTECT
> w fazie 04). Tę jedną ścieżkę zostawiamy na `objects`; zmieniamy tylko
> pozostałe lookupy w helperach na widzący menedżer.

**Files:**
- Modify: `src/import_common/core/publikacja.py` — helper + `klass.objects`
  w `_try_match_pub_by_doi:87`, `_try_match_pub_by_zrodlo:108`,
  `_try_match_pub_by_uri:181`, `_try_match_pub_by_title:235,249`.
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Failing test — matchuj_publikacje po tytule widzi skasowany**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_matchuj_publikacje_widzi_soft_deletowany():
    """Fuzzy matching importu po tytule+rok musi znaleźć soft-deletowaną
    publikację, inaczej re-import utworzy duplikat."""
    from import_common.core.publikacja import matchuj_publikacje

    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Unikalny tytul do matchowania importu",
        rok=2019,
    )
    rec.delete()

    wynik = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Unikalny tytul do matchowania importu",
        year=2019,
    )
    assert wynik is not None
    assert wynik.pk == rec.pk
```

- [ ] **Step 2: Uruchom — ma FAILować**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_matchuj_publikacje_widzi_soft_deletowany -v`
Expected: FAIL — `wynik is None` (`klass.objects` ukrywa skasowany rekord).

- [ ] **Step 3: Dodaj helper `_manager_dla_matchingu` i podmień lookupy**

Na początku `src/import_common/core/publikacja.py` (po importach) dodaj:

```python
def _manager_dla_matchingu(klass):
    """Menedżer widzący także soft-deletowane rekordy (kat. B: re-import
    NIE może omijać skasowanych, inaczej tworzy duplikaty). Modele bez
    soft-delete (np. Rekord-view) nie mają global_objects → fallback do
    objects."""
    return getattr(klass, "global_objects", klass.objects)
```

Następnie podmień w helperach `klass.objects` na `_manager_dla_matchingu(klass)`:

- `_try_match_pub_by_doi` (linia 87):
  `zapytanie = klass.objects.filter(doi__istartswith=doi, rok=year)`
  → `zapytanie = _manager_dla_matchingu(klass).filter(doi__istartswith=doi, rok=year)`
- `_try_match_pub_by_zrodlo` (linia 108):
  `return klass.objects.get(` → `return _manager_dla_matchingu(klass).get(`
- `_try_match_pub_by_uri` (linia 181):
  `klass.objects.filter(Q(www=public_uri) | Q(public_www=public_uri))`
  → `_manager_dla_matchingu(klass).filter(Q(www=public_uri) | Q(public_www=public_uri))`
- `_try_match_pub_by_title` (linia 235):
  `klass.objects.filter(tytul_oryginalny__istartswith=title, rok=year)`
  → `_manager_dla_matchingu(klass).filter(tytul_oryginalny__istartswith=title, rok=year)`
- `_try_match_pub_by_title` (linia 249):
  `klass.objects.filter(rok=year)`
  → `_manager_dla_matchingu(klass).filter(rok=year)`

> `_build_isbn_query` zostaje na `klass.objects` (patrz Uwaga w nagłówku
> Tasku — woła metodę domenową `wydawnictwa_nadrzedne_dla_innych()`).

- [ ] **Step 4: Uruchom test — ma PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_matchuj_publikacje_widzi_soft_deletowany -v`
Expected: PASS

- [ ] **Step 5: Regresja matchingu importu**

Run: `uv run pytest src/import_common/ -q`
Expected: PASS

- [ ] **Step 6: ruff + commit**

```bash
ruff format src/import_common/core/publikacja.py
ruff check src/import_common/core/publikacja.py
git add src/import_common/core/publikacja.py src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "fix(soft-delete): matchuj_publikacje widzi soft-deletowane rekordy (import bez duplikatów)"
```

---

## Task 5: `pbn_integrator/importer/chapters.py` — matching książki-matki przez `global_objects`

`chapters.py:64` woła `Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pbn_book_id)`
żeby znaleźć książkę-matkę rozdziału. Jeśli książka jest soft-deletowana,
`objects.get` rzuci `DoesNotExist` → import rozdziału stworzy nową książkę
(duplikat) lub się wywali. Matching musi widzieć skasowaną książkę-matkę.

> **Spójność z fazą 04:** faza 04 ustawia `wydawnictwo_nadrzedne` na PROTECT
> (książka z rozdziałami nie da się skasować). Tu chodzi o sytuację, gdy
> książka-matka została skasowana zanim importowano rozdział — matching ma ją
> odnaleźć przez `global_objects`, nie tworzyć duplikatu.

**Files:**
- Modify: `src/pbn_integrator/importer/chapters.py:64`
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Failing test**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_chapters_matchuje_soft_deletowana_ksiazke_matke():
    """Import rozdziału po pbn_uid książki-matki musi znaleźć soft-deletowaną
    książkę przez global_objects, nie tworzyć duplikatu."""
    from bpp.models import Wydawnictwo_Zwarte
    from pbn_api.models import Publication

    pub_ksiazki = baker.make(Publication)
    ksiazka = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Ksiazka matka",
        rok=2018,
        pbn_uid=pub_ksiazki,
    )
    ksiazka.delete()

    znaleziona = Wydawnictwo_Zwarte.global_objects.get(
        pbn_uid_id=pub_ksiazki.pk
    )
    assert znaleziona.pk == ksiazka.pk
    # objects (ukrywający) NIE znajdzie — to różnica, którą naprawiamy
    with pytest.raises(Wydawnictwo_Zwarte.DoesNotExist):
        Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pub_ksiazki.pk)
```

- [ ] **Step 2: Uruchom — ma PASS już teraz (test kontraktu menedżera)**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_chapters_matchuje_soft_deletowana_ksiazke_matke -v`
Expected: PASS — to test kontraktu (`global_objects` widzi, `objects` nie).
Potwierdza powód zmiany kodu w Step 3.

- [ ] **Step 3: Zmień lookup w chapters.py**

`src/pbn_integrator/importer/chapters.py:64`:
```python
        wydawnictwo_nadrzedne = Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pbn_book_id)
```
→
```python
        wydawnictwo_nadrzedne = Wydawnictwo_Zwarte.global_objects.get(
            pbn_uid_id=pbn_book_id
        )
```

- [ ] **Step 4: Regresja pbn_integrator chapters**

Run: `uv run pytest src/pbn_integrator/ -k "chapter or rozdzial" -q`
Expected: PASS (jeśli brak testów dla chapters — `no tests ran`, OK).

- [ ] **Step 5: ruff + commit**

```bash
ruff format src/pbn_integrator/importer/chapters.py
ruff check src/pbn_integrator/importer/chapters.py
git add src/pbn_integrator/importer/chapters.py src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "fix(soft-delete): chapters matchuje soft-deletowana ksiazke-matke przez global_objects"
```

---

## Task 6: `pbn_import` — jawny `.hard_delete()` przy czyszczeniu przed re-importem

`src/pbn_import/utils/publication_import.py:115-116` celowo USUWA FIZYCZNIE
publikacje PBN przed pełnym re-importem z PBN. Po fazie 02
`.objects.exclude(...).delete()` na querysecie stałby się soft-delete → stare
rekordy zostałyby w koszu, a re-import (Task 2/3 — matching widzący skasowane)
zwróciłby je jako „istniejące", więc re-import by ich nie odtworzył ALE też
nie zaktualizował, a slug-i (warunkowy unique tylko dla nieusuniętych z fazy
02) by nie kolidowały — efekt: dryf danych i rosnący kosz. Intencja kodu to
czystka fizyczna → jawny `.hard_delete()`.

**Files:**
- Modify: `src/pbn_import/utils/publication_import.py:115-116`
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Failing test — hard-delete fizycznie usuwa (nie soft)**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_pbn_import_czyszczenie_jest_hard_delete():
    """_delete_existing_publications musi FIZYCZNIE usunąć publikacje PBN
    (hard_delete), nie zostawiać ich w koszu (soft)."""
    from bpp.models import Wydawnictwo_Zwarte
    from pbn_api.models import Publication

    pub = baker.make(Publication)
    baker.make(Wydawnictwo_Zwarte, rok=2020, pbn_uid=pub)

    # Symulacja linii czyszczenia z publication_import.py:115
    Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None).hard_delete()

    # Nic nie zostaje — ani w objects, ani w global_objects (kosz pusty)
    assert Wydawnictwo_Zwarte.global_objects.filter(
        pbn_uid_id=pub.pk
    ).count() == 0
```

- [ ] **Step 2: Uruchom — ma PASS (test kontraktu hard_delete)**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_pbn_import_czyszczenie_jest_hard_delete -v`
Expected: PASS — potwierdza, że `.hard_delete()` na querysecie czyści fizycznie
(uzasadnia zmianę w Step 3).

- [ ] **Step 3: Zmień kod czyszczenia na `.hard_delete()`**

`src/pbn_import/utils/publication_import.py:115-116`:
```python
        deleted_zwarte = Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None).delete()[0]
        deleted_ciagle = Wydawnictwo_Ciagle.objects.exclude(pbn_uid_id=None).delete()[0]
```
→
```python
        # Re-import PBN wymaga fizycznego czyszczenia (NIE soft-delete) —
        # inaczej stare rekordy zostają w koszu i kolidują przy re-imporcie.
        deleted_zwarte = Wydawnictwo_Zwarte.objects.exclude(
            pbn_uid_id=None
        ).hard_delete()
        deleted_ciagle = Wydawnictwo_Ciagle.objects.exclude(
            pbn_uid_id=None
        ).hard_delete()
```

> **Uwaga na wartość zwracaną:** stare `.delete()` zwracało krotkę
> `(liczba, {model: liczba})`, stąd `[0]`. `SoftDeleteQuerySet.hard_delete()`
> w `django-soft-delete` zwraca wynik bazowego `QuerySet.delete()`
> (krotkę) — ale to zależy od wersji pakietu. Następny krok to weryfikuje
> i, jeśli trzeba, koryguje rozpakowanie.

- [ ] **Step 4: Zweryfikuj typ zwracany `hard_delete()` i skoryguj rozpakowanie**

Run: `uv run python -c "import inspect, django_softdelete.managers as m; print(inspect.getsource(m.SoftDeleteQuerySet.hard_delete))"`
Expected: zobacz, co zwraca. Jeśli zwraca krotkę `(int, dict)` — zachowaj
`[0]` (usuń je z powyższego diffu: `... .hard_delete()[0]`). Jeśli zwraca
`int` lub `None` — dostosuj: gdy `int`, zostaw bez `[0]`; gdy `None`, policz
przed usunięciem:
```python
        zwarte_qs = Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None)
        deleted_zwarte = zwarte_qs.count()
        zwarte_qs.hard_delete()
        ciagle_qs = Wydawnictwo_Ciagle.objects.exclude(pbn_uid_id=None)
        deleted_ciagle = ciagle_qs.count()
        ciagle_qs.hard_delete()
```
Zastosuj wariant zgodny z faktycznym zwrotem (log używa `deleted_zwarte`/
`deleted_ciagle` jako liczb w komunikacie linii 118-121).

- [ ] **Step 5: Regresja pbn_import**

Run: `uv run pytest src/pbn_import/ -q`
Expected: PASS

- [ ] **Step 6: ruff + commit**

```bash
ruff format src/pbn_import/utils/publication_import.py
ruff check src/pbn_import/utils/publication_import.py
git add src/pbn_import/utils/publication_import.py src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "fix(soft-delete): pbn_import czysci publikacje przez hard_delete przed re-importem"
```

---

## Task 7: Audyt 90 miejsc `*_Autor.objects` — decyzje (zostaw `objects` / zmień na `global_objects`)

Po fazie 02 `*_Autor.objects` ukrywa kaskadowo soft-deletowane autorstwa
(kaskada §2.2). To jest **poprawny default dla ewaluacji** (praca w koszu nie
liczy się do punktacji). Audyt: dla każdej grupy miejsc zapada decyzja
z uzasadnieniem. Większość = ZOSTAW `objects`. Wyjątek kat. B (musi widzieć
skasowane) → `global_objects` (tu: tylko transfer w merge autorów, Step „merge").

> **Reguła nadrzędna (spec §2.5):** default „pomijaj skasowane" jest tu
> znacznie bezpieczniejszy niż przeciwny. Zmieniamy tylko miejsca, które
> *muszą* widzieć skasowane, by nie zostawić sierot lub nie zgubić transferu.
>
> **Gate `BppSoftDeleteQuerySet.update()` (z fazy 01):** miejsca robiące
> `*_Autor.objects.filter(...).update(...)` są bezpieczne, DOPÓKI nie ustawiają
> `deleted_at`/`restored_at`. Audyt potwierdza, że wszystkie poniższe `.update()`
> dotyczą `przypieta` / `dyscyplina_naukowa` / `afiliuje` — gate nie zadziała.

**Files (tylko decyzje — zmiana kodu tylko w „merge"):**
- Decyzje (bez zmian): pliki ewaluacji, API, przemapuj, snapshot, komparator,
  dwudyscyplinowcy.
- Modify: `src/deduplikator_autorow/utils/merge.py:172,178,265,271,335,341`
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Udokumentuj decyzje audytu (komentarz w teście jako rejestr)**

Decyzje per-miejsce (uzasadnienie w nagłówku — w kodzie bez zmian):

  **ZOSTAW `objects` (default „pomijaj skasowane" poprawny):**
  - `src/ewaluacja_optymalizacja/tasks/reset_pins.py:34,54,75`
    (`.update(przypieta=...)`) — reset przypięć dotyczy tylko prac liczonych
    do ewaluacji; prace w koszu nie biorą udziału w optymalizacji. `.update`
    nie tyka `deleted_at` → gate nie zadziała. **Zostaw.**
  - `src/ewaluacja_optymalizacja/management/commands/reset_disciplines.py:59,63,67,90,100,108`
    (count + `.update(dyscyplina_naukowa=...)`) — jw., reset dyscyplin tylko
    dla prac w ewaluacji. **Zostaw.**
  - `src/ewaluacja_optymalizacja/tasks/unpin_all_sensible.py:134,140,146`
    (`.update`) — odpinanie prac ewaluowanych. **Zostaw.**
  - `src/ewaluacja_optymalizacja/solve_helpers/unpinning.py:54,62` — jw.
    **Zostaw.**
  - `src/ewaluacja_optymalizacja/tasks/helpers.py:121,139`,
    `tasks/optimization.py:536,539,573,576` (liczenie udziałów / przypiętych) —
    optymalizacja MA pomijać prace w koszu. **Zostaw.**
  - `src/ewaluacja_optymalizacja/views/author_works.py:75,93,111`,
    `views/evaluation_browser/builders.py:136,141,170,174`,
    `views/evaluation_browser/filters.py:44,55`, `views/verification.py:52,57`
    (przeglądarka/weryfikacja ewaluacji) — prezentują stan ewaluacji; praca
    w koszu nie powinna się pokazywać. **Zostaw.**
  - `src/ewaluacja_dwudyscyplinowcy/core.py:125` — analiza dwudyscyplinowości
    dla ewaluacji; kosz pomijamy. **Zostaw.**
  - `src/snapshot_odpiec/tasks.py:6,9,12,20,23,26` — snapshot stanu odpięć
    dyscyplin dla bieżącej ewaluacji; praca w koszu = brak odpięcia do
    zapisania. **Zostaw.**
  - `src/komparator_pbn/views.py:85,89,267,301` — porównanie „co BPP
    deklaruje" vs „co jest w PBN". Soft-delete publikacji wycofuje oświadczenia
    z PBN (faza 05), więc BPP NIE deklaruje już tej pracy → `objects`
    (ukrywający) daje spójny obraz z PBN. **Zostaw.**
  - `src/api_v1/viewsets/{wydawnictwo_ciagle.py:21,wydawnictwo_zwarte.py:19,patent.py:10}`
    (`queryset = *_Autor.objects.all()`) — publiczne/REST API NIE może
    serwować autorstw skasowanych prac (spójność z resztą API, gdzie sama
    publikacja znika). **Zostaw.**
  - `src/przemapuj_prace_autora/{views.py,forms.py}` (wiele linii) — narzędzie
    przemapowania prac autora operuje na pracach aktywnych; skasowane (w koszu)
    nie powinny być przemapowywane (operator najpierw je przywraca). **Zostaw.**
  - `src/bpp/views/autocomplete/authors.py`, `src/ranking_autorow/forms.py` —
    publiczne UI; kosz pomijamy. **Zostaw.**
  - `src/bpp/management/commands/{ukryj_nieuzywane_dyscypliny.py,ustaw_daty_oswiadczenia_pbn.py}` —
    operują na aktywnych autorstwach. **Zostaw.**
  - `src/bpp/migrations/0403_*`, `src/zglos_publikacje/migrations/0019_*` —
    **migracje: NIE RUSZAĆ** (reguła BPP). Działają na stanie historycznym.
  - `src/conftest.py`, `src/bpp/tests/**`, `src/*/tests*.py`,
    `src/integration_tests/test_conftest.py`,
    `src/bpp/demo_data/generators/*` — fixtures/testy/demo: tworzą obiekty
    (`.create`) — `objects` poprawne. **Zostaw.**

  **ZMIEŃ na `global_objects` (kat. B — MUSI widzieć skasowane):**
  - `src/deduplikator_autorow/utils/merge.py:172,178,265,271,335,341` —
    transfer through-rows z autora-duplikatu na głównego. Jeśli duplikat ma
    autorstwo wskazujące na soft-deletowaną publikację (kaskada §2.2), to
    autorstwo jest też soft-deletowane → `objects` go NIE przeniesie →
    zostanie sierota wskazująca duplikat → guard fazy 04 (liczący przez
    `global_objects`) zablokuje usunięcie husku duplikatu. Transfer MUSI
    widzieć wszystkie autorstwa. **Zmień na `global_objects`.**

- [ ] **Step 2: Failing test — merge przenosi też autorstwo soft-deletowanej pracy**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_merge_przenosi_autorstwo_soft_deletowanej_pracy():
    """Merge autorów musi przenieść także autorstwo wskazujące na
    soft-deletowaną publikację (kaskadowo skasowane *_Autor), inaczej
    zostaje sierota blokująca guard usunięcia duplikatu (faza 04)."""
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
    from deduplikator_autorow.utils.merge import przenies_wydawnictwa_ciagle

    autor_glowny = baker.make("bpp.Autor")
    autor_duplikat = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")

    praca = baker.make(Wydawnictwo_Ciagle, rok=2020)
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=praca,
        autor=autor_duplikat,
        jednostka=jednostka,
        kolejnosc=0,
        typ_odpowiedzialnosci_id=1,
    )
    praca.delete()  # kaskadowo soft-deletuje też Wydawnictwo_Ciagle_Autor

    # autorstwo jest teraz ukryte w objects, widoczne w global_objects
    assert Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=autor_duplikat
    ).count() == 0
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(
        autor=autor_duplikat
    ).count() == 1

    przenies_wydawnictwa_ciagle(autor_duplikat, autor_glowny)

    # po transferze autorstwo wskazuje na autora głównego, duplikat czysty
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(
        autor=autor_duplikat
    ).count() == 0
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(
        autor=autor_glowny
    ).count() == 1
```

> **Uwaga:** dopasuj nazwę funkcji (`przenies_wydawnictwa_ciagle`) i jej
> sygnaturę do faktycznego API `src/deduplikator_autorow/utils/merge.py`
> (przeczytaj linie 160-200 przed uruchomieniem). Jeśli nazwa/sygnatura inna —
> popraw wywołanie w teście. `typ_odpowiedzialnosci_id=1` zakłada istnienie
> rekordu w bazie testowej; jeśli go nie ma, użyj
> `baker.make("bpp.Typ_Odpowiedzialnosci")` i przekaż obiekt.

- [ ] **Step 3: Uruchom — ma FAILować**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_merge_przenosi_autorstwo_soft_deletowanej_pracy -v`
Expected: FAIL — autorstwo nie zostało przeniesione (`objects` go nie widział),
duplikat nadal ma 1 wiersz w `global_objects`.

- [ ] **Step 4: Zmień lookupy transferu na `global_objects`**

W `src/deduplikator_autorow/utils/merge.py` zamień (po przeczytaniu kontekstu
każdej linii — zachowaj resztę wyrażenia):

- linia 172: `wc_autorzy = Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor_duplikat)`
  → `wc_autorzy = Wydawnictwo_Ciagle_Autor.global_objects.filter(autor=autor_duplikat)`
- linia 178: `existing = Wydawnictwo_Ciagle_Autor.objects.filter(`
  → `existing = Wydawnictwo_Ciagle_Autor.global_objects.filter(`
- linia 265: `wz_autorzy = Wydawnictwo_Zwarte_Autor.objects.filter(autor=autor_duplikat)`
  → `wz_autorzy = Wydawnictwo_Zwarte_Autor.global_objects.filter(autor=autor_duplikat)`
- linia 271: `existing = Wydawnictwo_Zwarte_Autor.objects.filter(`
  → `existing = Wydawnictwo_Zwarte_Autor.global_objects.filter(`
- linia 335: `patent_autorzy = Patent_Autor.objects.filter(autor=autor_duplikat)`
  → `patent_autorzy = Patent_Autor.global_objects.filter(autor=autor_duplikat)`
- linia 341: `existing = Patent_Autor.objects.filter(`
  → `existing = Patent_Autor.global_objects.filter(`

> **Nota:** „existing" to sprawdzenie kolizji (czy autor główny ma już to
> autorstwo). Liczenie kolizji przez `global_objects` jest poprawne — kolizja
> z soft-deletowanym autorstwem głównego też ma być wykryta, by nie powstał
> duplikat through-row po restore.

- [ ] **Step 5: Uruchom test — ma PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_merge_przenosi_autorstwo_soft_deletowanej_pracy -v`
Expected: PASS

- [ ] **Step 6: Regresja merge autorów**

Run: `uv run pytest src/deduplikator_autorow/ -q`
Expected: PASS

- [ ] **Step 7: ruff + commit**

```bash
ruff format src/deduplikator_autorow/utils/merge.py
ruff check src/deduplikator_autorow/utils/merge.py
git add src/deduplikator_autorow/utils/merge.py src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "fix(soft-delete): merge autorow przenosi tez kaskadowo-skasowane autorstwa (global_objects)"
```

---

## Task 8: Dedup publikacji — potwierdź `objects` (ZOSTAW) + test regresji „dedup pomija kosz"

`src/deduplikator_publikacji/tasks.py:140,147` skanuje publikacje do
wyszukiwania duplikatów na `.objects`. Soft-deletowana publikacja jest „w
koszu" — NIE chcemy jej raportować jako duplikatu (operator ją świadomie
usunął). Default `objects` (ukrywający) jest poprawny. Bez zmiany kodu; test
broni decyzji przed regresją.

**Files:**
- Bez zmian: `src/deduplikator_publikacji/tasks.py:140,147`
- Test: `src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`

- [ ] **Step 1: Test regresji — skan dedupu pomija soft-deletowane**

Dopisz do `test_audyt_kategorii_b.py`:

```python
@pytest.mark.django_db
def test_dedup_skan_pomija_soft_deletowane():
    """Skaner duplikatów NIE może zgłaszać prac z kosza (operator je
    świadomie usunął) — _get_publications_to_scan używa objects."""
    from deduplikator_publikacji.tasks import _get_publications_to_scan

    aktywna = baker.make(Wydawnictwo_Ciagle, rok=2020)
    skasowana = baker.make(Wydawnictwo_Ciagle, rok=2020)
    skasowana.delete()

    publikacje = _get_publications_to_scan(2020, 2020)
    pks = {pub.pk for _ct, pub in publikacje}
    assert aktywna.pk in pks
    assert skasowana.pk not in pks
```

- [ ] **Step 2: Uruchom — ma PASS od razu (potwierdza decyzję ZOSTAW)**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py::test_dedup_skan_pomija_soft_deletowane -v`
Expected: PASS (kod już używa `objects`; test broni przed przyszłą regresją).

- [ ] **Step 3: Commit**

```bash
git add src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
git commit -m "test(soft-delete): dedup publikacji pomija prace w koszu (regresja)"
```

---

## Task 9: Pełny test fazy + ruff + zamknięcie

- [ ] **Step 1: Cała suita testów tej fazy**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py -v`
Expected: PASS (wszystkie testy zielone).

- [ ] **Step 2: Regresja przylegających podsystemów**

Run: `uv run pytest src/import_common/ src/pbn_integrator/ src/pbn_import/ src/deduplikator_autorow/ src/deduplikator_publikacji/ -q`
Expected: PASS (brak regresji matchingu / merge / importu).

- [ ] **Step 3: ruff całość zmienionych plików**

Run:
```bash
ruff format src/pbn_api/models/publication.py src/import_common/core/publikacja.py \
    src/pbn_integrator/importer/chapters.py src/pbn_import/utils/publication_import.py \
    src/deduplikator_autorow/utils/merge.py \
    src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
ruff check src/pbn_api/models/publication.py src/import_common/core/publikacja.py \
    src/pbn_integrator/importer/chapters.py src/pbn_import/utils/publication_import.py \
    src/deduplikator_autorow/utils/merge.py \
    src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py
```
Expected: brak błędów.

- [ ] **Step 4: Commit zamykający (jeśli ruff coś zmienił)**

```bash
git add -A
git commit -m "chore(soft-delete): faza 03 audyt kat. B — format/lint"
```

---

## Self-Review (autor planu)

**Spec coverage (§2.5 + lista miejsc):**
- Matching importu (`import_common`) → Task 4. ✓
- Crossref dedup (`crossref_bpp/core.py:178,182` — `znajdz_w_tabelach` używa
  `Wydawnictwo_*.objects`): patrz **Nota** niżej.
- `deduplikator_publikacji/tasks.py` → Task 8 (ZOSTAW + test). ✓
- PBN matching po `pbn_uid` (`pbn_integrator/utils/synchronization.py`,
  `importer/chapters.py`, `pbn_api`): Task 2, 3 (rdzeń: `rekord_w_bpp`/
  `get_bpp_publication` — używane przez `books.py`/`articles.py`), Task 5
  (chapters). `synchronization.py` matchuje przez `pbn_uid_id` na `rec`
  (obiekt już w ręku) i `_pobierz_prace_po_elemencie` (po stronie PBN) — nie
  tworzy duplikatów BPP z ukrywającego menedżera; **decyzja: bez zmian**
  (patrz Nota). `pbn_api/management/*` — komendy operacyjne na istniejących
  rekordach, nie matching tworzący duplikaty; **bez zmian**.
- `pbn_import/utils/publication_import.py:115-116` jawny `.hard_delete()` →
  Task 6. ✓
- Audyt 90 miejsc `*_Autor.objects` → Task 7 (decyzje per-miejsce; jedyna
  zmiana: merge → `global_objects`). ✓
- Testy wymagane przez zlecenie: re-import nie tworzy duplikatu (Task 1-4),
  matching po `pbn_uid` znajduje soft-deletowaną (Task 1-3), ewaluacja pomija
  kosz (Task 7 decyzje + Task 8 test), pbn_import hard-delete fizycznie
  usuwa (Task 6). ✓

**Nota — `crossref_bpp/core.py:178,182` (`znajdz_w_tabelach`):** używa
`Wydawnictwo_Zwarte.objects` / `Wydawnictwo_Ciagle.objects` do podpowiedzi
„czy w BPP jest już taki rekord (po DOI/tytule)" w UI crossref. To kat. B
(matching importu), ale ZESPÓŁ helperów matchingu używanym przez crossref
import jest `import_common.matchuj_publikacje` (Task 4 — naprawione).
`znajdz_w_tabelach` to *podgląd dla operatora* (top-10 kandydatów), nie
automatyczny dedup tworzący rekordy. **Decyzja: ZOSTAW `objects`** —
pokazywanie operatorowi rekordów z kosza jako „kandydatów do scalenia"
byłoby mylące; jeśli rekord jest w koszu, operator najpierw go przywraca.
Gdyby w fazie 08 (regresja) okazało się, że crossref-import dubluje rekordy
przez `znajdz_w_tabelach`, dodać `global_objects` tam punktowo. Zapis tej
decyzji wystarcza dla kat. B (brak ścieżki automatycznego tworzenia duplikatu
przez tę metodę).

**Placeholder scan:** brak „TBD"/„handle edge cases"; każdy krok ma kod lub
konkretną komendę. Kroki z zależnością od wersji pakietu (`hard_delete` zwrot,
Task 6 Step 4) i od faktycznej sygnatury merge (Task 7 Step 2) mają jawną
instrukcję weryfikacji przed użyciem — to świadome, nie placeholder.

**Type consistency:** `_modele_publikacji_global()` zdefiniowane w Task 2,
użyte w Task 3 — ta sama nazwa. `_manager_dla_matchingu` zdefiniowane raz
(Task 4), użyte w 5 helperach. `global_objects` / `objects` / `hard_delete`
zgodne z kontraktem PINNED w indeksie 00.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-06-04-soft-delete-03-audyt-kategorii-b.md`.

Dwie opcje wykonania:
1. **Subagent-Driven (zalecane)** — świeży subagent per Task, review między
   Taskami (`superpowers:subagent-driven-development`).
2. **Inline Execution** — wykonanie w tej sesji z checkpointami
   (`superpowers:executing-plans`).

Faza 03 zależy od ukończonej fazy 02 (modele już `SoftDeleteModel`,
`global_objects` istnieje). Bez fazy 02 testy nie ruszą.
