# ewaluacja_liczba_n per-uczelnia (R2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Liczba N (i tabele udziałów) liczona i zapisywana osobno per uczelnia, na podstawie `autor.aktualna_jednostka.uczelnia`, zachowując identyczne liczby w instalacji jednouczelnianej.

**Architecture:** Tabele udziałów `IloscUdzialowDlaAutoraZaRok`/`...ZaCalosc` zyskują FK `uczelnia`. Cały pipeline w `utils.py` zawęża budowę/agregację do jednej uczelni (autorzy filtrowani po `aktualna_jednostka.uczelnia` + `skupia_pracownikow`, nieprzypisani pomijani). Widoki odczytowe filtrują po `get_for_request`.

**Tech Stack:** Django, PostgreSQL, pytest + model_bakery, testcontainers.

**Spec:** `docs/superpowers/specs/2026-06-03-ewaluacja-liczba-n-per-uczelnia-design.md`

---

## Uwagi wykonawcze (przeczytaj przed startem)

- Komenda testowa: `uv run pytest <ścieżka> -q -p no:cacheprovider` (testcontainers; Docker musi działać).
- **NIGDY nie edytuj istniejących migracji.** Nowe pliki (max obecny: `0008` → nowy `0009`).
- Lint: `uv run ruff check <pliki>` (NIE `--fix` — popraw ręcznie). Max 88 znaków.
- Po każdym Tasku: testy zielone → commit.
- Reguła atrybucji: uczelnia autora = `autor.aktualna_jednostka.uczelnia`; gdy NULL lub `skupia_pracownikow=False` → autor POMIJANY (zero wierszy udziałów).
- Invariant single-install: istniejące `src/ewaluacja_liczba_n/` testy zielone.
- Fixtury wielouczelniane (`zwarte_dwie_uczelnie`, `druga_uczelnia`, `jednostka_drugiej_uczelni`) są w `src/bpp/tests/test_models/test_sloty/conftest.py`; z `ewaluacja_liczba_n/tests/` NIE są widoczne — w razie potrzeby zbuduj scenariusz lokalnie (2× `Uczelnia`+`Jednostka`+autorzy z `Autor_Dyscyplina`+`wymiar_etatu`) albo dodaj do `ewaluacja_liczba_n/tests/conftest.py`.

---

## Task 1: FK `uczelnia` na modelach udziałów + migracja + backfill

**Files:**
- Modify: `src/ewaluacja_liczba_n/models.py` (`IloscUdzialowDlaAutoraZaRok`, `IloscUdzialowDlaAutoraZaCalosc`)
- Create: `src/ewaluacja_liczba_n/migrations/0009_iloscudzialow_uczelnia.py` (przez makemigrations + ręczny RunPython)
- Test: `src/ewaluacja_liczba_n/tests/test_per_uczelnia.py` (create)

- [ ] **Step 1: Napisz failing test (model przyjmuje uczelnia + unique_together)**

Utwórz `src/ewaluacja_liczba_n/tests/test_per_uczelnia.py`:

```python
import pytest
from decimal import Decimal

from model_bakery import baker

from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaRok,
    IloscUdzialowDlaAutoraZaCalosc,
)


@pytest.mark.django_db
def test_zarok_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    obj = IloscUdzialowDlaAutoraZaRok.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rok=2022,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        uczelnia=u,
    )
    assert obj.uczelnia_id == u.pk


@pytest.mark.django_db
def test_zacalosc_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    obj = IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        uczelnia=u,
    )
    assert obj.uczelnia_id == u.pk
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/ewaluacja_liczba_n/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (`TypeError: unexpected keyword 'uczelnia'` / unknown field).

- [ ] **Step 3: Dodaj pole `uczelnia` + rozszerz unique_together**

W `src/ewaluacja_liczba_n/models.py`:

`IloscUdzialowDlaAutoraZaRok` — dodaj pole (po `autor_dyscyplina`) i zmień Meta:
```python
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        verbose_name = "Ilość udziałów dla autora za rok"
        verbose_name_plural = "Ilości udziałów dla autorów za rok"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rok", "uczelnia"),
        ]
```

`IloscUdzialowDlaAutoraZaCalosc` — dodaj pole (po `komentarz`) i zmień Meta:
```python
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        verbose_name = "Ilość udziałów dla autora za cały okres"
        verbose_name_plural = "Ilości udziałów dla autorów za cały okres"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rodzaj_autora", "uczelnia"),
        ]
```

- [ ] **Step 4: Wygeneruj migrację + dodaj backfill**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations ewaluacja_liczba_n -n iloscudzialow_uczelnia`
Otrzymasz `0009_*` z `AddField` (×2) + `AlterUniqueTogether` (×2). Dopisz do niej RunPython backfill (single→domyślna; multi z wierszami→fail) i dodaj do `operations` NA KOŃCU:

```python
def backfill_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    ZaRok = apps.get_model("ewaluacja_liczba_n", "IloscUdzialowDlaAutoraZaRok")
    ZaCalosc = apps.get_model("ewaluacja_liczba_n", "IloscUdzialowDlaAutoraZaCalosc")

    null_qs = [
        ZaRok.objects.filter(uczelnia__isnull=True),
        ZaCalosc.objects.filter(uczelnia__isnull=True),
    ]
    if not any(qs.exists() for qs in null_qs):
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        for qs in null_qs:
            qs.update(uczelnia=uczelnie[0])
        return

    raise RuntimeError(
        "Migracja liczba_n per-uczelnia (0009): istnieją wiersze udziałów bez "
        f"uczelni, a w systemie jest {len(uczelnie)} uczelni — nie można "
        "zdeterministycznie przypisać. Przelicz liczbę N per uczelnia (przelicz_n) "
        "albo usuń stare IloscUdzialow* i zaaplikuj migrację na czystych danych."
    )


def backfill_uczelnia_reverse(apps, schema_editor):
    pass
```

i `migrations.RunPython(backfill_uczelnia, backfill_uczelnia_reverse)` jako ostatnia operacja.
**Uwaga kolejności:** `AlterUniqueTogether` musi wykonać się PRZED backfillem nie jest wymagane (backfill tylko update'uje FK); ale upewnij się, że AddField jest przed RunPython (jest, makemigrations stawia je pierwsze).

- [ ] **Step 5: Uruchom test + brak dryfu**

Run: `uv run pytest src/ewaluacja_liczba_n/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.
Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak nowych zmian dla `ewaluacja_liczba_n` (pre-existing dryf innych apek ignoruj).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/ewaluacja_liczba_n/models.py src/ewaluacja_liczba_n/migrations/0009_*.py src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git add src/ewaluacja_liczba_n/models.py src/ewaluacja_liczba_n/migrations/0009_*.py src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git commit -m "feat(multi-hosted): FK uczelnia na IloscUdzialow* + backfill (liczba_n R2)"
```

---

## Task 2: Pipeline `utils.py` — zawężenie budowy udziałów per uczelnia

**Files:**
- Modify: `src/ewaluacja_liczba_n/utils.py`
- Test: `src/ewaluacja_liczba_n/tests/test_per_uczelnia.py`

To rdzeń R2. Funkcje są sprzężone (`oblicz_liczby_n_dla_ewaluacji_2022_2025` orkiestruje resztę), więc zmieniamy je RAZEM; testem jednostki jest cały pipeline.

- [ ] **Step 1: Napisz failing testy (izolacja 2 uczelni + wykluczenie nieprzypisanych)**

Dopisz w `test_per_uczelnia.py` (zbuduj scenariusz lokalnie — 2 uczelnie, autor w każdej przez `aktualna_jednostka`, oraz autor z obcą/NULL jednostką; ustaw `Autor_Dyscyplina` z `wymiar_etatu` i `rodzaj_autora.jest_w_n=True`):

```python
@pytest.mark.django_db
def test_pipeline_izolacja_dwie_uczelnie(db):
    from decimal import Decimal

    from bpp.models import Autor, Autor_Dyscyplina, Jednostka, Uczelnia, Wydzial
    from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
    from ewaluacja_common.models import Rodzaj_Autora
    from ewaluacja_liczba_n.models import (
        IloscUdzialowDlaAutoraZaRok,
        LiczbaNDlaUczelni,
    )
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

    u1 = baker.make(Uczelnia, skrot="U1", nazwa="U1")
    u2 = baker.make(Uczelnia, skrot="U2", nazwa="U2")
    j1 = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=True)
    j2 = baker.make(Jednostka, uczelnia=u2, skupia_pracownikow=True)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    rodzaj_n = baker.make(Rodzaj_Autora, jest_w_n=True, licz_sloty=True)

    a1 = baker.make(Autor, aktualna_jednostka=j1)
    a2 = baker.make(Autor, aktualna_jednostka=j2)
    for autor in (a1, a2):
        for rok in (2022, 2023, 2024, 2025):
            baker.make(
                Autor_Dyscyplina, autor=autor, rok=rok,
                dyscyplina_naukowa=dyscyplina, rodzaj_autora=rodzaj_n,
                wymiar_etatu=Decimal("1.0"), procent_dyscypliny=Decimal("100.0"),
            )

    oblicz_liczby_n_dla_ewaluacji_2022_2025(u1)
    oblicz_liczby_n_dla_ewaluacji_2022_2025(u2)  # drugi run NIE może skasować u1

    assert IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u1, autor=a1).exists()
    assert IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u2, autor=a2).exists()
    # u1 nie zawiera autora z u2 i odwrotnie:
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u1, autor=a2).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u2, autor=a1).exists()
    # LiczbaN policzona per uczelnia:
    assert LiczbaNDlaUczelni.objects.filter(uczelnia=u1).exists()
    assert LiczbaNDlaUczelni.objects.filter(uczelnia=u2).exists()


@pytest.mark.django_db
def test_pipeline_pomija_nieprzypisanych(db):
    from decimal import Decimal

    from bpp.models import Autor, Autor_Dyscyplina, Jednostka, Uczelnia
    from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
    from ewaluacja_common.models import Rodzaj_Autora
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

    u1 = baker.make(Uczelnia, skrot="U1", nazwa="U1")
    obca = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=False)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    rodzaj_n = baker.make(Rodzaj_Autora, jest_w_n=True, licz_sloty=True)

    a_null = baker.make(Autor, aktualna_jednostka=None)
    a_obca = baker.make(Autor, aktualna_jednostka=obca)
    for autor in (a_null, a_obca):
        baker.make(
            Autor_Dyscyplina, autor=autor, rok=2022,
            dyscyplina_naukowa=dyscyplina, rodzaj_autora=rodzaj_n,
            wymiar_etatu=Decimal("1.0"), procent_dyscypliny=Decimal("100.0"),
        )

    oblicz_liczby_n_dla_ewaluacji_2022_2025(u1)

    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(autor=a_null).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(autor=a_obca).exists()
```

(Sprawdź faktyczne nazwy pól `Rodzaj_Autora`/`Autor_Dyscyplina` w `src/ewaluacja_common/models.py` i `src/bpp/models/dyscyplina_naukowa.py` — dostosuj fixture, jeśli `procent_dyscypliny`/`wymiar_etatu`/`jest_w_n`/`licz_sloty` mają inne nazwy/wymogi. Cel testów niezmienny.)

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/ewaluacja_liczba_n/tests/test_per_uczelnia.py -k pipeline -q -p no:cacheprovider`
Expected: FAIL (drugi run kasuje wiersze u1; nieprzypisani są liczeni; `uczelnia` None).

- [ ] **Step 3: Zawęź `oblicz_liczby_n_dla_ewaluacji_2022_2025`**

W `src/ewaluacja_liczba_n/utils.py`, w `oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia, rok_min=2022, rok_max=2025)`:
- Zmień delete na per-uczelnia:
```python
    IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=uczelnia, **warunek_lat).delete()
```
- Zawęź iterację autorów (zamiast `Autor_Dyscyplina.objects.filter(**warunek_lat)`):
```python
    autor_dyscypliny = Autor_Dyscyplina.objects.filter(
        autor__aktualna_jednostka__uczelnia=uczelnia,
        autor__aktualna_jednostka__skupia_pracownikow=True,
        **warunek_lat,
    )
    for ad in autor_dyscypliny:
```
- W obu `IloscUdzialowDlaAutoraZaRok.objects.create(...)` dodaj `uczelnia=uczelnia,`.
- Przekaż `uczelnia` do kroków: `oblicz_sumy_udzialow_za_calosc(uczelnia, rok_min, rok_max)`,
  `oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, rok_min, rok_max)` (już bierze uczelnia),
  `oblicz_dyscypliny_nieraportowane(uczelnia, rok_max)`,
  `dolicz_bonus_za_nieraportowana(uczelnia, nieraportowane_ids, rok_min, rok_max)`.

- [ ] **Step 4: Zawęź `oblicz_sumy_udzialow_za_calosc`**

Sygnatura → `oblicz_sumy_udzialow_za_calosc(uczelnia, rok_min=2022, rok_max=2025)`.
- Delete per-uczelnia: `IloscUdzialowDlaAutoraZaCalosc.objects.filter(uczelnia=uczelnia).delete()`
  (zamiast `objects.all().delete()`).
- Źródło agregacji: `IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=uczelnia, rok__gte=rok_min, rok__lte=rok_max)`.
- W `IloscUdzialowDlaAutoraZaCalosc.objects.create(...)` dodaj `uczelnia=uczelnia,`.

- [ ] **Step 5: Zawęź `oblicz_srednia_liczbe_n_dla_dyscyplin`, `oblicz_dyscypliny_nieraportowane`, `dolicz_bonus_za_nieraportowana`, `oblicz_liczbe_n_na_koniec_2025`**

- `oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, …)`: zmień `udzialy =
  IloscUdzialowDlaAutoraZaRok.objects.filter(**rok_kw)` → `.filter(uczelnia=uczelnia, **rok_kw)`.
  (Reszta — delete/zapis `LiczbaNDlaUczelni` per uczelnia — bez zmian.)
- `oblicz_dyscypliny_nieraportowane(uczelnia, rok=2025)`: dodaj param `uczelnia`;
  `IloscUdzialowDlaAutoraZaRok.objects.filter(rok=rok)` → `.filter(uczelnia=uczelnia, rok=rok)`.
- `dolicz_bonus_za_nieraportowana(uczelnia, nieraportowane_ids, rok_min=2022, rok_max=2025)`:
  dodaj param `uczelnia`; iteracja `IloscUdzialowDlaAutoraZaCalosc.objects.select_related(...)`
  → `.filter(uczelnia=uczelnia).select_related(...)`.
- `oblicz_liczbe_n_na_koniec_2025(uczelnia)`: `IloscUdzialowDlaAutoraZaRok.objects.filter(rok=2025)`
  → `.filter(uczelnia=uczelnia, rok=2025)`.

- [ ] **Step 6: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/ewaluacja_liczba_n/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS (izolacja + wykluczenie).

- [ ] **Step 7: Regresja istniejących testów liczba_n (invariant single-install)**

Run: `uv run pytest src/ewaluacja_liczba_n/ -q -p no:cacheprovider -k "not playwright"`
Expected: PASS. Jeśli któryś istniejący test woła `oblicz_dyscypliny_nieraportowane()` /
`oblicz_sumy_udzialow_za_calosc()` bez uczelni — zaktualizuj wywołanie (oczekiwana zmiana sygnatury). Jeśli test buduje udziały bez `aktualna_jednostka` na autorze, dostosuj fixture (autor musi mieć jednostkę w danej uczelni, by być liczony).

- [ ] **Step 8: Lint + commit**

```bash
uv run ruff check src/ewaluacja_liczba_n/utils.py src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git add src/ewaluacja_liczba_n/utils.py src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git commit -m "feat(multi-hosted): pipeline liczba_n zawężony per uczelnia (utils.py)"
```

---

## Task 3: Odczyty (views) — filtr po uczelni + nieraportowane z uczelnią

**Files:**
- Modify: `src/ewaluacja_liczba_n/views/list.py`, `src/ewaluacja_liczba_n/views/export.py`, `src/ewaluacja_liczba_n/views/verify.py`
- Test: `src/ewaluacja_liczba_n/tests/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing test (lista U1 nie pokazuje wierszy U2)**

Dopisz test: zbuduj 2 uczelnie + udziały (jak Task 2), wywołaj `get_queryset` widoku
`AutorzyLiczbaNListView` (lub `UdzialyZaCaloscListView`) z requestem rozwiązującym U1
(`request._uczelnia = u1`), asercja: queryset zawiera tylko wiersze `uczelnia=u1`.
Wzór budowy requestu jak w R1 (fake request z `_uczelnia` + `user`); zajrzyj do
istniejących testów `ewaluacja_liczba_n/tests/` po wzór instancjonowania widoku/klienta.

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/ewaluacja_liczba_n/tests/test_per_uczelnia.py -k "view or lista" -q -p no:cacheprovider`
Expected: FAIL (widok pokazuje obie uczelnie).

- [ ] **Step 3: Dodaj filtr `uczelnia` w widokach**

Wzór (źródło uczelni jak w istniejącym `views/index.py`):
```python
from bpp.models import Uczelnia
...
        uczelnia = Uczelnia.objects.get_for_request(self.request)
```
Zastosuj `.filter(uczelnia=uczelnia)` w:
- `views/list.py:184` (`AutorzyLiczbaNListView.get_queryset`, `IloscUdzialowDlaAutoraZaRok.objects.filter(...)`),
- `views/list.py:211,223` (`IloscUdzialowDlaAutoraZaRok.objects.filter(rok__gte=2022, rok__lte=2025)` w `get_context_data`),
- `views/list.py:331` (`UdzialyZaCaloscListView.get_queryset`, `IloscUdzialowDlaAutoraZaCalosc.objects.all()` → `.filter(uczelnia=uczelnia)`),
- `views/list.py:392` (`IloscUdzialowDlaAutoraZaCalosc.objects.values_list(...)` → dodaj `.filter(uczelnia=uczelnia)` przed `values_list`),
- `views/export.py:23` (`IloscUdzialowDlaAutoraZaRok.objects.filter(...)`),
- `views/export.py:207` (`IloscUdzialowDlaAutoraZaCalosc.objects.all()` → `.filter(uczelnia=uczelnia)`),
- `views/verify.py:227` (`IloscUdzialowDlaAutoraZaRok.objects.filter(rok=2025)` → dodaj `uczelnia=uczelnia`).

Oraz przekaż uczelnię do `oblicz_dyscypliny_nieraportowane(uczelnia)` we wszystkich
wywołaniach w `views/list.py` (linie ok. 113, 243, 357, 412).

W każdym widoku pobierz `uczelnia = Uczelnia.objects.get_for_request(self.request)`
RAZ w `get_queryset`/`get_context_data` i użyj zarówno do `.filter`, jak i do
`oblicz_dyscypliny_nieraportowane`.

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ + regresja**

Run: `uv run pytest src/ewaluacja_liczba_n/ -q -p no:cacheprovider -k "not playwright"`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/ewaluacja_liczba_n/views/list.py src/ewaluacja_liczba_n/views/export.py src/ewaluacja_liczba_n/views/verify.py src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git add src/ewaluacja_liczba_n/views/ src/ewaluacja_liczba_n/tests/test_per_uczelnia.py
git commit -m "feat(multi-hosted): widoki liczba_n filtrują udziały po uczelni"
```

---

## Task 4: Regresja całościowa + brak dryfu

**Files:** brak (gate).

- [ ] **Step 1: Pełna regresja liczba_n + konsumenci**

Run: `uv run pytest src/ewaluacja_liczba_n/ src/ewaluacja_metryki/ -q -p no:cacheprovider -k "not playwright"`
Expected: PASS. (`ewaluacja_metryki` woła `oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)`
— sprawdź, że nadal przechodzi; jeśli jakiś test metryk budował dane bez `aktualna_jednostka`,
dostosuj fixture.)

- [ ] **Step 2: Brak dryfu migracji**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak nowych zmian dla `ewaluacja_liczba_n`.

- [ ] **Step 3: Commit (jeśli były poprawki fixtur w Step 1)**

```bash
git add -A
git commit -m "test(multi-hosted): regresja liczba_n per-uczelnia + dostosowanie fixtur"
```
(Jeśli nic nie zmieniono — pomiń commit.)

---

## Self-review (autor planu)

**Spec coverage:**
- FK uczelnia + unique_together + migracja/backfill → Task 1 ✓
- Pipeline `utils.py` per uczelnia (wszystkie `oblicz_*`, delete per-uczelnia, filtr autorów po aktualna_jednostka.uczelnia + skupia_pracownikow, wykluczenie nieprzypisanych) → Task 2 ✓
- Odczyty (export/list/verify) filtr `get_for_request` + nieraportowane z uczelnią → Task 3 ✓
- Invariant single-install → regresja w Task 2/3/4 ✓
- Multi-install izolacja + wykluczenie nieprzypisanych → testy Task 2 ✓

**Znane luki / uwagi wykonawcy:**
- Task 1 Step 4: kolejność operacji w migracji — AddField przed RunPython (makemigrations stawia je pierwsze); zweryfikuj wygenerowany plik.
- Task 2: nazwy pól `Rodzaj_Autora`/`Autor_Dyscyplina` (`jest_w_n`, `licz_sloty`, `wymiar_etatu`, `procent_dyscypliny`, `policz_udzialy`) — potwierdź w modelach przed pisaniem fixtur; cel testów niezmienny.
- Task 2 Step 7 / Task 4: istniejące testy mogą wołać `oblicz_*` bez uczelni (zmiana sygnatury) lub budować autorów bez `aktualna_jednostka` — dostosuj (oczekiwane).
- Task 3: dokładne sygnatury widoków (`get_queryset`/`get_context_data`) — przeczytaj plik przed edycją; pobierz uczelnię raz, użyj wielokrotnie.
- `oblicz_dyscypliny_nieraportowane` staje się wymagającym `uczelnia` — wszystkie wywołania (utils + views/list.py ×4) muszą przekazać uczelnię (inaczej TypeError złapie test/regresja).
