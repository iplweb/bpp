# Per-uczelnia sloty READ-SIDE (R1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Odczyty slotowe (raporty/eksporty/API) filtrują dane po uczelni
oglądającego, zachowując identyczne liczby w instalacji jednouczelnianej.

**Architecture:** Widok `bpp_cache_punktacja_autora_view` eksponuje `uczelnia_id`
(z jednostki). Jeden helper `uczelnia_dla_odczytu(request)` rozstrzyga uczelnię
(hybryda: site + override superusera). Cross-autorowe agregatory (`create_report`,
`autorzy_zerowi`, `zbieraj_sloty`, `RaportSlotowAutor`, `oswiadczenia`) zawężają
queryset po uczelni; `RaportSlotowUczelnia` zyskuje FK `uczelnia`. Konsumenci już
zawężeni po `autor_id`+`dyscyplina_id` (część `ewaluacja_metryki`) — bez zmian,
udokumentowane.

**Tech Stack:** Django, PostgreSQL, pytest + model_bakery, testcontainers, django_tables2.

**Spec:** `docs/superpowers/specs/2026-06-03-per-uczelnia-sloty-read-side-design.md`

---

## Uwagi wykonawcze (przeczytaj przed startem)

- Komenda testowa: `uv run pytest <ścieżka> -q -p no:cacheprovider` (testcontainers;
  Docker musi działać).
- **NIGDY nie edytuj istniejących migracji.** Nowe pliki (0425 to wyjątek już zamknięty).
- Lint: `uv run ruff check <pliki>` (NIE `--fix` — popraw ręcznie). Max 88 znaków.
- Po każdym Tasku: testy zielone → commit.
- Invariant single-install: istniejące `src/raport_slotow/` muszą pozostać zielone.
- `get_for_request` jest w `src/bpp/models/uczelnia.py:40` (`UczelniaManager`).
- Numery migracji startowe: `bpp` → 0426/0427; `raport_slotow` → 0020.

---

## Task 1: Kolumna `uczelnia` w widoku `Cache_Punktacja_Autora_Query_View`

**Files:**
- Create: `src/bpp/migrations/0426_cache_punktacja_autora_view_uczelnia.py`
- Modify: `src/bpp/models/cache/punktacja.py` (klasa `Cache_Punktacja_Autora_Query_View`)
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing test**

Dopisz w `test_per_uczelnia.py`:

```python
@pytest.mark.django_db
def test_view_eksponuje_uczelnia(zwarte_dwie_uczelnie, jednostka, druga_uczelnia):
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.cache import Cache_Punktacja_Autora_Query_View

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    ctype = ContentType.objects.get_for_model(zwarte_dwie_uczelnie).pk

    rows = Cache_Punktacja_Autora_Query_View.objects.filter(
        rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
    )
    for row in rows:
        assert row.uczelnia_id == row.jednostka.uczelnia_id
    assert set(rows.values_list("uczelnia_id", flat=True)) == {
        jednostka.uczelnia_id,
        druga_uczelnia.pk,
    }
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_view_eksponuje_uczelnia -q -p no:cacheprovider`
Expected: FAIL (`FieldError: Cannot resolve keyword 'uczelnia_id'` / brak pola).

- [ ] **Step 3: Dodaj pole na modelu**

W `src/bpp/models/cache/punktacja.py`, klasa `Cache_Punktacja_Autora_Query_View`,
po polu `jednostka` dodaj:

```python
    uczelnia = ForeignKey("bpp.Uczelnia", DO_NOTHING)
```

- [ ] **Step 4: Utwórz migrację widoku (DROP+CREATE z kolumną)**

Utwórz `src/bpp/migrations/0426_cache_punktacja_autora_view_uczelnia.py`:

```python
from django.db import migrations

DROP = "DROP VIEW IF EXISTS bpp_cache_punktacja_autora_view;"

CREATE_NEW = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id,
       a.rekord_id,
       a.pkdaut,
       a.slot,
       a.autor_id,
       a.dyscyplina_id,
       a.jednostka_id,
       j.uczelnia_id,
       d.autorzy_z_dyscypliny,
       d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
"""

CREATE_OLD = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id,
       a.rekord_id,
       a.pkdaut,
       a.slot,
       a.autor_id,
       a.dyscyplina_id,
       a.jednostka_id,
       d.autorzy_z_dyscypliny,
       d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0425_per_uczelnia_cache_view"),
    ]

    operations = [
        migrations.RunSQL(sql=DROP + CREATE_NEW, reverse_sql=DROP + CREATE_OLD),
    ]
```

(Model `managed=False`, więc pole nie generuje `AddField` — `makemigrations
--check` musi dać „No changes".)

- [ ] **Step 5: Uruchom — ma PRZEJŚĆ + brak dryfu**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_view_eksponuje_uczelnia -q -p no:cacheprovider`
Expected: PASS.
Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run` (ignoruj pre-existing dryf w siteblog/raport_slotow do_roku).
Expected: brak nowych zmian dla `bpp`.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/bpp/models/cache/punktacja.py src/bpp/migrations/0426_cache_punktacja_autora_view_uczelnia.py
git add src/bpp/models/cache/punktacja.py src/bpp/migrations/0426_cache_punktacja_autora_view_uczelnia.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): widok cache_punktacja_autora eksponuje uczelnia_id"
```

---

## Task 2: Indeks `(rekord_id, uczelnia, dyscyplina)` (hardening #2)

**Files:**
- Create: `src/bpp/migrations/0427_cpd_index_rekord_uczelnia_dyscyplina.py`
- Modify: `src/bpp/models/cache/punktacja.py` (Meta.indexes `Cache_Punktacja_Dyscypliny`)

- [ ] **Step 1: Dodaj indeks na modelu**

W `Cache_Punktacja_Dyscypliny.Meta.indexes` dopisz drugi indeks:

```python
        indexes = [
            models.Index(fields=["uczelnia", "dyscyplina"]),
            models.Index(fields=["rekord_id", "uczelnia", "dyscyplina"]),
        ]
```

- [ ] **Step 2: Wygeneruj migrację**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp -n cpd_index_rekord_uczelnia_dyscyplina`
Expected: `0427_*` z `AddIndex`. (Jeśli numer inny — dostosuj zależność w kolejnych zadaniach.)

- [ ] **Step 3: Brak dryfu + commit**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak zmian dla `bpp`.

```bash
uv run ruff check src/bpp/models/cache/punktacja.py
git add src/bpp/models/cache/punktacja.py src/bpp/migrations/0427_*.py
git commit -m "feat(multi-hosted): indeks (rekord_id, uczelnia, dyscyplina) na CPD"
```

---

## Task 3: Helper `uczelnia_dla_odczytu(request)` (hybryda)

**Files:**
- Create: `src/raport_slotow/uczelnia_helper.py`
- Test: `src/raport_slotow/tests/test_uczelnia_helper.py`

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/raport_slotow/tests/test_uczelnia_helper.py`:

```python
import pytest
from model_bakery import baker

from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu


class _Req:
    def __init__(self, user, get=None):
        self.user = user
        self.GET = get or {}


@pytest.mark.django_db
def test_zwykly_user_dostaje_uczelnie_z_requestu(uczelnia, druga_uczelnia, rf):
    from bpp.models import Uczelnia

    user = baker.make("bpp.BppUser", is_superuser=False)
    req = _Req(user, get={"uczelnia": str(druga_uczelnia.pk)})
    # get_for_request rozstrzyga po site; bez wielu site'ów zwróci default.
    result = uczelnia_dla_odczytu(req)
    assert isinstance(result, Uczelnia)
    # non-superuser nie może nadpisać:
    assert result != druga_uczelnia or Uczelnia.objects.count() == 1


@pytest.mark.django_db
def test_superuser_moze_nadpisac(uczelnia, druga_uczelnia):
    user = baker.make("bpp.BppUser", is_superuser=True)
    req = _Req(user, get={"uczelnia": str(druga_uczelnia.pk)})
    assert uczelnia_dla_odczytu(req) == druga_uczelnia


@pytest.mark.django_db
def test_superuser_zly_param_ignorowany(uczelnia, druga_uczelnia):
    user = baker.make("bpp.BppUser", is_superuser=True)
    req = _Req(user, get={"uczelnia": "999999"})
    # nieistniejąca uczelnia → fallback do get_for_request
    from bpp.models import Uczelnia

    assert isinstance(uczelnia_dla_odczytu(req), Uczelnia)
```

(Fixture `druga_uczelnia` jest w `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`
— przenieś go do `src/conftest.py` jeśli niedostępny w `raport_slotow/tests`, albo
zdefiniuj lokalnie analogicznie: `Uczelnia.objects.create(skrot="DR", nazwa="Druga", site=<nowy Site>)`.)

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/raport_slotow/tests/test_uczelnia_helper.py -q -p no:cacheprovider`
Expected: FAIL (ModuleNotFoundError: uczelnia_helper).

- [ ] **Step 3: Implementacja helpera**

Utwórz `src/raport_slotow/uczelnia_helper.py`:

```python
"""Rozstrzyganie 'uczelni oglądającego' dla odczytów slotowych (read-side).

Hybryda: domyślnie uczelnia z requestu (site/domena); superuser może nadpisać
jawnym parametrem ``?uczelnia=<pk>``.
"""

from bpp.models import Uczelnia


def uczelnia_dla_odczytu(request):
    bazowa = Uczelnia.objects.get_for_request(request)

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_superuser:
        pk = request.GET.get("uczelnia")
        if pk:
            try:
                return Uczelnia.objects.get(pk=pk)
            except (Uczelnia.DoesNotExist, ValueError, TypeError):
                return bazowa
    return bazowa
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/raport_slotow/tests/test_uczelnia_helper.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/raport_slotow/uczelnia_helper.py src/raport_slotow/tests/test_uczelnia_helper.py
git add src/raport_slotow/uczelnia_helper.py src/raport_slotow/tests/test_uczelnia_helper.py
git commit -m "feat(multi-hosted): helper uczelnia_dla_odczytu (hybryda site/superuser)"
```

---

## Task 4: `zbieraj_sloty` — parametr `uczelnia_id`

**Files:**
- Modify: `src/bpp/core.py` (`zbieraj_sloty`)
- Test: `src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py` (create)

- [ ] **Step 1: Napisz failing test**

Utwórz `src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py`:

```python
import pytest

from bpp.core import zbieraj_sloty


@pytest.mark.django_db
def test_zbieraj_sloty_zaweza_po_uczelni(zwarte_dwie_uczelnie, jednostka, druga_uczelnia):
    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    autor = zwarte_dwie_uczelnie.autorzy_set.first().autor

    _pkt_all, lista_all, _slot_all = zbieraj_sloty(
        autor.pk, 1, zwarte_dwie_uczelnie.rok, zwarte_dwie_uczelnie.rok,
        akcja="wszystko",
    )
    _pkt_u, lista_u, _slot_u = zbieraj_sloty(
        autor.pk, 1, zwarte_dwie_uczelnie.rok, zwarte_dwie_uczelnie.rok,
        akcja="wszystko", uczelnia_id=jednostka.uczelnia_id,
    )
    # zawężenie po uczelni nie może dać więcej wpisów niż bez zawężenia
    assert len(lista_u) <= len(lista_all)
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (`TypeError: unexpected keyword 'uczelnia_id'`).

- [ ] **Step 3: Dodaj parametr + filtr**

W `src/bpp/core.py`, `zbieraj_sloty` — dodaj `uczelnia_id=None` na końcu sygnatury
i filtr po `jednostka__uczelnia_id`:

```python
def zbieraj_sloty(
    autor_id,
    zadany_slot,
    rok_min,
    rok_max,
    minimalny_pk=None,
    dyscyplina_id=None,
    jednostka_id=None,
    akcja=None,
    uczelnia_id=None,
):
    from bpp.models.cache import Cache_Punktacja_Autora_Query

    rekordy = Cache_Punktacja_Autora_Query.objects.filter(
        rekord__rok__gte=rok_min, rekord__rok__lte=rok_max, autor_id=autor_id
    )
    if uczelnia_id is not None:
        rekordy = rekordy.filter(jednostka__uczelnia_id=uczelnia_id)
    if dyscyplina_id is not None:
        rekordy = rekordy.filter(dyscyplina_id=dyscyplina_id)
```

(Reszta funkcji bez zmian.)

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/bpp/core.py src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py
git add src/bpp/core.py src/bpp/tests/test_core_zbieraj_sloty_uczelnia.py
git commit -m "feat(multi-hosted): zbieraj_sloty przyjmuje uczelnia_id (zawężenie)"
```

---

## Task 5: `autorzy_z_punktami` / `autorzy_zerowi` — filtr uczelni

**Files:**
- Modify: `src/raport_slotow/core.py`
- Test: `src/raport_slotow/tests/test_core.py`

- [ ] **Step 1: Napisz failing test**

Dopisz w `src/raport_slotow/tests/test_core.py`:

```python
@pytest.mark.django_db
def test_autorzy_z_punktami_filtr_uczelni(zwarte_dwie_uczelnie, jednostka, druga_uczelnia):
    from raport_slotow.core import autorzy_z_punktami

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    wszyscy = set(autorzy_z_punktami())
    tylko_u1 = set(autorzy_z_punktami(uczelnia=jednostka.uczelnia))
    assert tylko_u1 <= wszyscy
    assert len(tylko_u1) <= len(wszyscy)
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/raport_slotow/tests/test_core.py -k autorzy_z_punktami_filtr -q -p no:cacheprovider`
Expected: FAIL (`TypeError: unexpected keyword 'uczelnia'`).

- [ ] **Step 3: Dodaj parametr `uczelnia`**

W `src/raport_slotow/core.py`, `autorzy_z_punktami` (i przekaż dalej z
`autorzy_zerowi`):

```python
def autorzy_z_punktami(
    od_roku=None, do_roku=None, min_pk=None, uczelnia=None
) -> List[Tuple[int, int, int]]:
    kwargs = _get_kwargs(od_roku, do_roku, prefix="rekord__")

    exclude_kwargs = dict()
    if min_pk is not None:
        exclude_kwargs = dict(rekord__punkty_kbn__lt=min_pk)

    qs = Cache_Punktacja_Autora_Query_View.objects.all().filter(**kwargs)
    if uczelnia is not None:
        qs = qs.filter(uczelnia=uczelnia)
    return qs.exclude(**exclude_kwargs).values(
        "autor_id", "rekord__rok", "dyscyplina_id"
    )
```

I `autorzy_zerowi`:

```python
def autorzy_zerowi(od_roku=None, do_roku=None, min_pk=None, uczelnia=None):
    defined = autorzy_z_dyscyplinami(od_roku=od_roku, do_roku=do_roku)
    existent = autorzy_z_punktami(
        od_roku=od_roku, do_roku=do_roku, min_pk=min_pk, uczelnia=uczelnia
    )
    return defined.difference(existent)
```

> Uwaga: `autorzy_z_dyscyplinami` czyta `Autor_Dyscyplina` (deklaracje, nie cache)
> — w R1 NIE zawężamy go po uczelni (autor deklaruje dyscyplinę niezależnie od
> afiliacji); zawężenie zerowych realizuje `existent`. Udokumentuj to komentarzem.

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/raport_slotow/tests/test_core.py -k autorzy_z_punktami_filtr -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/raport_slotow/core.py src/raport_slotow/tests/test_core.py
git add src/raport_slotow/core.py src/raport_slotow/tests/test_core.py
git commit -m "feat(multi-hosted): autorzy_z_punktami/zerowi filtrują po uczelni"
```

---

## Task 6: `RaportSlotowUczelnia` — FK `uczelnia` + zawężenie generacji

**Files:**
- Modify: `src/raport_slotow/models/uczelnia.py`
- Create: `src/raport_slotow/migrations/0020_raportslotowuczelnia_uczelnia.py` (przez makemigrations)
- Modify: `src/raport_slotow/views/uczelnia.py` (ustawienie uczelni przy zamówieniu)
- Test: `src/raport_slotow/tests/test_raport_slotow_uczelnia/` (nowy plik)

- [ ] **Step 1: Napisz failing test (generacja zawężona)**

Utwórz `src/raport_slotow/tests/test_per_uczelnia_uczelnia.py`:

```python
import pytest


@pytest.mark.django_db
def test_create_report_zawezony_po_uczelni(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia, rok
):
    from raport_slotow.models.uczelnia import RaportSlotowUczelnia

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    raport = RaportSlotowUczelnia.objects.create(
        od_roku=rok, do_roku=rok, uczelnia=jednostka.uczelnia,
        akcja=RaportSlotowUczelnia.Akcje.WSZYSTKO,
    )
    raport.create_report()

    jednostki_w_raporcie = set(
        raport.raportslotowuczelniawiersz_set.values_list(
            "jednostka__uczelnia_id", flat=True
        )
    )
    assert jednostki_w_raporcie <= {jednostka.uczelnia_id}
    assert druga_uczelnia.pk not in jednostki_w_raporcie
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/raport_slotow/tests/test_per_uczelnia_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (`TypeError: 'uczelnia' is an invalid keyword`).

- [ ] **Step 3: Dodaj FK `uczelnia` na modelu**

W `src/raport_slotow/models/uczelnia.py`, klasa `RaportSlotowUczelnia`, dodaj pole:

```python
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, null=True, blank=True
    )
```

- [ ] **Step 4: Zawęź `create_report`**

W `create_report`, filtr `kombinacje` i wywołanie `zbieraj_sloty`:

```python
        kombinacje = (
            Cache_Punktacja_Autora_Query.objects.filter(
                rekord__rok__gte=self.od_roku, rekord__rok__lte=self.do_roku
            )
            .values_list(*lst)
            .distinct()
        )
        if self.uczelnia_id is not None:
            kombinacje = kombinacje.filter(jednostka__uczelnia_id=self.uczelnia_id)
```

oraz w wywołaniu `zbieraj_sloty(...)` dodaj `uczelnia_id=self.uczelnia_id`.
W gałęzi `pokazuj_zerowych` przekaż `uczelnia=self.uczelnia` do `autorzy_zerowi(...)`.

- [ ] **Step 5: Ustaw uczelnię przy zamówieniu raportu**

W `src/raport_slotow/views/uczelnia.py` znajdź widok tworzący `RaportSlotowUczelnia`
(CreateView/`form_valid`). Ustaw `form.instance.uczelnia = uczelnia_dla_odczytu(self.request)`
przed zapisem (import: `from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu`).

- [ ] **Step 6: Migracja + backfill**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations raport_slotow -n raportslotowuczelnia_uczelnia`
Następnie do wygenerowanej migracji dopisz `RunPython` backfill (single→domyślna,
multi→stare raporty zostają null — to artefakty historyczne):

```python
    def backfill(apps, schema_editor):
        Uczelnia = apps.get_model("bpp", "Uczelnia")
        RSU = apps.get_model("raport_slotow", "RaportSlotowUczelnia")
        u = list(Uczelnia.objects.all()[:2])
        if len(u) == 1:
            RSU.objects.filter(uczelnia__isnull=True).update(uczelnia=u[0])

    def backfill_reverse(apps, schema_editor):
        pass
```

i dodaj `migrations.RunPython(backfill, backfill_reverse)` do `operations`.

- [ ] **Step 7: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/raport_slotow/tests/test_per_uczelnia_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 8: Lint + commit**

```bash
uv run ruff check src/raport_slotow/models/uczelnia.py src/raport_slotow/views/uczelnia.py src/raport_slotow/migrations/0020_*.py
git add src/raport_slotow/models/uczelnia.py src/raport_slotow/views/uczelnia.py src/raport_slotow/migrations/0020_*.py src/raport_slotow/tests/test_per_uczelnia_uczelnia.py
git commit -m "feat(multi-hosted): RaportSlotowUczelnia FK uczelnia + zawężona generacja"
```

---

## Task 7: `RaportSlotowAutor` — filtr po uczelni oglądającego

**Files:**
- Modify: `src/raport_slotow/views/autor.py:97`
- Test: `src/raport_slotow/tests/test_views/test_raport_slotow_autor.py`

- [ ] **Step 1: Napisz failing test**

Dopisz test sprawdzający, że dla autora z afiliacjami w dwóch uczelniach widok
raportu (z `uczelnia_dla_odczytu` zwracającym U1) pokazuje tylko wiersze U1.
(Wzór asercji: `cpaq.values_list("uczelnia_id", flat=True)` ⊆ `{U1}`.)

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/raport_slotow/tests/test_views/test_raport_slotow_autor.py -k uczelni -q -p no:cacheprovider`
Expected: FAIL (widok pokazuje obie uczelnie).

- [ ] **Step 3: Dodaj filtr**

W `src/raport_slotow/views/autor.py`, w `get_tables` (linia ~97), dołóż filtr po
uczelni z helpera:

```python
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        cpaq = Cache_Punktacja_Autora_Query_View.objects.filter(
            autor=self.autor,
            uczelnia=uczelnia_dla_odczytu(self.request),
            rekord__rok__gte=self.kwargs["od_roku"],
            rekord__rok__lte=self.kwargs["do_roku"],
            pkdaut__gt=0,
        )
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/raport_slotow/tests/test_views/test_raport_slotow_autor.py -q -p no:cacheprovider`
Expected: PASS (wszystkie, w tym single-install regresja).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/raport_slotow/views/autor.py
git add src/raport_slotow/views/autor.py src/raport_slotow/tests/test_views/test_raport_slotow_autor.py
git commit -m "feat(multi-hosted): RaportSlotowAutor filtruje po uczelni oglądającego"
```

---

## Task 8: `oswiadczenia` — filtr po uczelni

**Files:**
- Modify: `src/oswiadczenia/views.py:342`
- Test: `src/oswiadczenia/tests/` (dopisz)

- [ ] **Step 1: Napisz failing test**

Sprawdź w `src/oswiadczenia/views.py` która to klasa (kontekst `"punktacje"`).
Test: rekord współautorski 2 uczelni → kontekst `punktacje` dla uczelni U1 zawiera
tylko wiersze `jednostka__uczelnia=U1`.

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/oswiadczenia/ -k uczelni -q -p no:cacheprovider`
Expected: FAIL.

- [ ] **Step 3: Dodaj filtr**

W `src/oswiadczenia/views.py` (linia ~342):

```python
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        return {
            "object": self.object,
            "punktacje": Cache_Punktacja_Autora.objects.filter(
                rekord_id=self.object.pk,
                jednostka__uczelnia=uczelnia_dla_odczytu(self.request),
            ),
        }
```

(Jeśli widok nie ma `self.request` lub to eksport bez requestu — użyj uczelni z
obiektu oświadczenia / `.get()` single-or-fail; sprawdź klasę przed edycją.)

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/oswiadczenia/ -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/oswiadczenia/views.py
git add src/oswiadczenia/views.py src/oswiadczenia/tests/
git commit -m "feat(multi-hosted): oswiadczenia filtruje punktacje po uczelni"
```

---

## Task 9: API + analiza pozostałych konsumentów (bez cichego pomijania)

**Files:**
- Modify: `src/api_v1/viewsets/raport_slotow_uczelnia.py` (jeśli listuje cudze raporty)
- Modify (komentarze): `src/ewaluacja_metryki/{utils.py,views/detail.py,views/list.py}`,
  `src/ewaluacja_common/utils.py`
- Test: `src/api_v1/tests/`

- [ ] **Step 1: API — ogranicz listing raportów do uczelni żądającego**

Przeczytaj `src/api_v1/viewsets/raport_slotow_uczelnia.py`. Jeśli `get_queryset`
zwraca wszystkie `RaportSlotowUczelnia`, zawęź:
`.filter(uczelnia=uczelnia_dla_odczytu(self.request))`. Napisz test: user
uczelni A nie widzi raportu uczelni B. (Jeśli viewset już filtruje po użytkowniku/
owner — udokumentuj i pomiń.)

- [ ] **Step 2: Udokumentuj konsumentów już-zawężonych (NIE filtruj na ślepo)**

`ewaluacja_metryki` (`utils.py`, `views/detail.py`, `views/list.py`) czyta
`Cache_Punktacja_Autora_Query` zawsze z `autor_id`+`dyscyplina_id`+(`pk__in`/
`rekord_id__in` z metryki) → wiersze są już związane z konkretnym autorem i
dyscypliną. Dodaj **komentarz** przy każdym z tych odczytów:
`# read-side multi-uczelnia: zawężone transitive po autor_id+dyscyplina_id;
# rewizja per-uczelnia metryk należy do federacji (R-federacja), nie R1.`
Analogicznie `ewaluacja_common/utils.py` — sprawdź źródło `dozwoleni_autorzy`:
jeśli pochodzi z federacyjnego kontekstu, oznacz komentarzem „do rewizji w federacji".

- [ ] **Step 3: Uruchom testy API + lint + commit**

```bash
uv run pytest src/api_v1/ -q -p no:cacheprovider
uv run ruff check src/api_v1/ src/ewaluacja_metryki/ src/ewaluacja_common/utils.py
git add -A
git commit -m "feat(multi-hosted): API raport_slotow per uczelnia + adnotacje konsumentów R1"
```

---

## Task 10: Regresja całościowa read-side + hardening #3 (doc)

**Files:**
- Modify (komentarz): `src/bpp/models/sloty/core.py` (`_zapisz`, asymetria skupia_pracownikow)

- [ ] **Step 1: Pełna regresja konsumentów R1**

Run: `uv run pytest src/raport_slotow/ src/oswiadczenia/ src/ewaluacja_metryki/ src/api_v1/ src/bpp/tests/test_models/test_sloty/ -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 2: Hardening #3 — udokumentuj asymetrię `skupia_pracownikow`**

W `src/bpp/models/sloty/core.py`, `_zapisz`, przy filtrze autorów dopisz komentarz:
`# UWAGA (read-side): autorzy_z_dyscypliny w Cache_Punktacja_Dyscypliny mogą
# zawierać PK autora z jednostki skupia_pracownikow=False, dla którego NIE ma
# wiersza Cache_Punktacja_Autora (ten filtr pomija takie jednostki). Konsumenci
# widoku nie powinni zakładać 1:1 między listą CPD a wierszami CPA.`

- [ ] **Step 3: Brak dryfu migracji + commit**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`

```bash
uv run ruff check src/bpp/models/sloty/core.py
git add src/bpp/models/sloty/core.py
git commit -m "docs(multi-hosted): udokumentuj asymetrię skupia_pracownikow (read-side)"
```

---

## Self-review (autor planu)

**Spec coverage:**
- Kolumna `uczelnia` w widoku → Task 1 ✓
- Indeks #2 → Task 2 ✓
- Helper hybryda → Task 3 ✓
- `zbieraj_sloty` uczelnia → Task 4 ✓
- `autorzy_z_punktami/zerowi` → Task 5 ✓
- `RaportSlotowUczelnia` FK + generacja → Task 6 ✓
- `RaportSlotowAutor` → Task 7 ✓
- `oswiadczenia` → Task 8 ✓
- API + adnotacje (ewaluacja_metryki/common już-zawężone — bez cichego pomijania) → Task 9 ✓
- Regresja + hardening #3 → Task 10 ✓
- Invariant single-install: sprawdzany w każdym Tasku (istniejące testy zielone).

**Znane luki / uwagi wykonawcy:**
- Task 3/7/8: fixture `druga_uczelnia` może wymagać przeniesienia do `src/conftest.py`.
- Task 6 Step 5/8: dokładny widok zamawiania raportu (CreateView vs FormView) —
  potwierdź w `views/uczelnia.py` przed edycją.
- Task 8: klasa widoku „punktacje" — sprawdź czy ma `self.request` (widok vs eksport).
- Task 9 Step 1: viewset może już filtrować po ownerze — wtedy tylko test+doc.
- `Cache_Punktacja_Autora_Sum`/`_Sum_Group` (cpaq/cpasg) — w obecnym kodzie NIE są
  populowane (legacy); R1 ich nie rusza. Jeśli plan ujawni populację — dopisz Task.
- pre-existing dryf migracji (`raport_slotow/do_roku`, `siteblog`) NIE jest nasz;
  przy `makemigrations --check` ignoruj te dwa wpisy.
