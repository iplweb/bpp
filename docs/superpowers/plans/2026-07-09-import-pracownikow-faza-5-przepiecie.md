# Plan implementacyjny — Faza 5: Przepięcie prac na jednostkę (§10, D6/D7)

## Goal

Domknąć wieloetapowe przeprojektowanie importu pracowników: dodać opt-in
przepięcie prac autora ze „starej” jednostki (jego `aktualna_jednostka` sprzed
importu) na jednostkę z pliku — wykonywane w fazie commit — oraz undo tych
przepięć z widoku `przemapuj_prace_autora`. Logika przemapowania zostaje
wyekstrahowana z widoku do serwisu (`przemapuj_prace_autora/service.py`), z
którego korzystają zarówno stary ręczny widok, jak i pipeline importu.

## Architecture

- **`przemapuj_prace_autora/service.py`** — czysty serwis domenowy:
  - `przemapuj(autor, jednostka_z, jednostka_do, user, zrodlowy_import=None)
    -> PrzemapoaniePracAutora` — przenosi prace ciągłe i zwarte z `jednostka_z`
    do `jednostka_do` (`filter(...).update(jednostka=...)`), buduje wzbogaconą
    historię (JSON) i tworzy rekord audytu `PrzemapoaniePracAutora`.
  - `cofnij(przemapowanie) -> (cofnieto, pominieto)` — idempotentne undo z
    guardem (przywraca tylko prace, których bieżąca `jednostka == jednostka_do`).
  - `_historia_prac_ciaglych(prace_ciagle, jednostka_z)` /
    `_historia_prac_zwartych(prace_zwarte, jednostka_z)` — przeniesione z
    `views.py`, wzbogacone o `autor_rekord_pk` + `jednostka_z_pk`.
- **`przemapuj_prace_autora/views.py`** — `_wykonaj_przemapowanie` staje się
  cienkim wywołaniem `service.przemapuj(...)` (+ `messages` + redirect); nowy
  widok `cofnij_przemapowanie(request, pk)`.
- **`import_pracownikow/pipeline/integrate.py`** — `integruj` na starcie
  robi snapshot `stare_jednostki = {row.pk: row.autor.aktualna_jednostka_id}`
  (PRZED pętlą integracji, bo trigger DB przestawi `aktualna_jednostka`), a po
  pętli woła `_wykonaj_przepiecia(parent, stare_jednostki, user, p)`, które dla
  każdego opt-in wiersza woła `service.przemapuj(..., zrodlowy_import=parent)`.
- **`import_pracownikow/views.py`** — kolumna „Przepnij prace” (N liczone
  agregatem), toggle HTMX `PrzepnijPraceView`, akcja zbiorcza
  `ZaznaczWszystkiePrzepieciaView`, helper `oznacz_przepiecie_prac(rows, parent)`.
- **`import_pracownikow/models.py`** — wspólny warunek kwalifikacji przepięcia
  (F1/F2/F3): metoda `ImportPracownikow.pary_z_pliku()` (zbiór par
  `(autor_id, jednostka_id)` z wierszy — „para z pliku”) oraz czysta funkcja
  `wiersz_kwalifikuje_do_przepiecia(autor_id, stara_id, jednostka_id,
  pary_z_pliku)`, używane IDENTYCZNIE w podglądzie (kolumna/toggle/bulk) i w
  fazie commit — gwarant tego samego zbioru kwalifikujących wierszy wszędzie.
- **Modele** — `ImportPracownikowRow.przepnij_prace` (Boolean, migracja 0015);
  `PrzemapoaniePracAutora.zrodlowy_import` (nullable FK, migracja 0003).

## Tech Stack

- Django (Python >=3.10,<3.15), PostgreSQL (przez testcontainers).
- Testy: pytest + `@pytest.mark.django_db` + `model_bakery.baker`;
  `liveops.testing.MockProgress` do testów pipeline.
- HTMX (per-wiersz swap partiala), Foundation-Icons w publicznym froncie.
- `django-liveops` (`ImportPracownikow(LiveOperation)`, `p.result(...)`).

## Global Constraints

Skopiowane z briefu — obowiązują DOSŁOWNIE w każdym tasku:

- Python `uv run` prefix do WSZYSTKich komend. Max linia 88 znaków — ruff
  IGNORUJE E501, więc pilnuj RĘCZNIE (sprawdzaj `awk 'length>88'`).
- NIE ruszaj istniejących migracji. Nowe: `import_pracownikow/migrations/0015_*`
  oraz `przemapuj_prace_autora/migrations/0003_*` (kolejne wolne numery).
- Django `{# #}` komentarze JEDNOLINIOWE (każda linia własne `{# #}`).
- Ikony: publiczny front = Foundation-Icons (`<span class="fi-...">`), nie emoji.
- Testy: pytest (NIE unittest.TestCase), standalone funkcje,
  `@pytest.mark.django_db`, `model_bakery.baker.make`. Tytuł przez
  `get_or_create`. NIE bare `except: pass`.
- Formatowanie tylko PINNED pre-commit (`pre-commit run ...`), NIE
  `uv run ruff format`.
- Stringi z polskimi „…” — domykaj TYPOGRAFICZNYM ” (U+201D), NIGDY ASCII `"`
  (zamyka literał → SyntaxError). Otwierający „ = U+201E, domykający ” = U+201D.
- Baseline: NIE odświeżaj `make baseline-update` na tej gałęzi (robimy przy
  scaleniu). Patrz nota końcowa planu.
- `LIVEOPS.RUNNER="eager"` w testach (integracja odpala się synchronicznie).
- Trigger DB `bpp_autor_ustaw_jednostka_aktualna` przelicza
  `Autor.aktualna_jednostka` po INSERT/UPDATE `Autor_Jednostka` — testy MUSZĄ to
  uwzględniać. Snapshot `aktualna_jednostka` robimy PRZED integracją; w testach
  ustawiamy stan przez `Autor.dodaj_jednostke(...)` (trigger sam ustawi
  `aktualna_jednostka`) i `refresh_from_db()`, albo przez
  `Autor.objects.filter(pk=...).update(aktualna_jednostka=...)` gdy trzeba obejść
  trigger.

## Assumptions (decyzje zabetonowane)

1. **`zrodlowy_import` zamiast `import`.** Spec pisze „nullable FK `import`”, ale
   `import` to słowo kluczowe Pythona — pole Django o tej nazwie jest
   niedostępne jako atrybut. Pole nazywamy **`zrodlowy_import`** (`FK →
   import_pracownikow.ImportPracownikow`, `null=True, blank=True,
   on_delete=SET_NULL, related_name="przemapowania", verbose_name="Import
   pracowników"`). Parametr serwisu również `zrodlowy_import=None`.
2. **Snapshot starej jednostki PRZED integracją.** „Stara” jednostka =
   `autor.aktualna_jednostka` sprzed importu. `integrate()` odpala trigger DB i
   przestawia `aktualna_jednostka` na jednostkę z pliku, więc jej NIE da się
   odczytać PO integrate — zbieramy `stare_jednostki = {row.pk:
   row.autor.aktualna_jednostka_id}` na POCZĄTKU `integruj` (odczyt świeży z bazy
   = drift-aware).
3. **Undo NIE kasuje rekordu `PrzemapoaniePracAutora`** (audyt). Guard
   `obj.jednostka_id == przemapowanie.jednostka_do_id` czyni undo idempotentnym
   (drugie cofnięcie: wszystko już przywrócone → same „pominięto”).
4. **N liczone AGREGATEM** przy budowie preview (spec dopuszcza agregat przy
   setkach wierszy) — dwa `values().annotate(Count)` na Wydawnictwo_*_Autor.
5. **Autor z wieloma starymi jednostkami** — v1 przepina TYLKO z jednostki,
   którą import faktycznie zmienia w tym wierszu (`aktualna_jednostka`); reszta
   = ręczny widok `przemapuj_prace_autora`.
6. **Literówka `PrzemapoaniePracAutora` NIETYKALNA** — istniejąca nazwa modelu i
   migracji; „poprawa” rozjechałaby się ze schematem.
7. `service.cofnij` zwraca **krotkę** `(cofnieto, pominieto)` (nie dataclass) —
   konsekwentnie w widoku i testach.
8. Serwis oczekuje INSTANCJI `Jednostka` (nie pk) — pipeline pobiera je przez
   `Jednostka.objects.get(pk=...)`.
9. `user` przekazywany do serwisu z pipeline to `parent.owner` (`LiveOperation`
   ma `owner`).
10. **Jeden warunek kwalifikacji, użyty wszędzie (F1/F2/F3).** Wiersz kwalifikuje
    się do przepięcia prac ⇔ `wiersz_kwalifikuje_do_przepiecia(autor_id, stara_id,
    jednostka_id, pary_z_pliku)` zwraca `True`: autor ustawiony, stara i nowa
    jednostka ustawione i różne, a para `(autor_id, stara_id)` NIE jest „parą z
    pliku” (stara jednostka NIE jest potwierdzona jako aktywny etat w innym
    wierszu tego samego pliku — inaczej „pułapka drugiego etatu”, §10/D7, analog
    guardu G1 odpięć z Fazy 4). `stara_id` = `aktualna_jednostka` autora sprzed
    importu: w podglądzie odczyt live (`row.autor.aktualna_jednostka_id`), w
    commit ze snapshotu (`stare_jednostki[row.pk]`), bo trigger DB zdążył ją
    przestawić. Ta sama funkcja w preview (`oznacz_przepiecie_prac`), toggle
    (`PrzepnijPraceView`), bulk (`ZaznaczWszystkiePrzepieciaView`) i commit
    (`_wykonaj_przepiecia`) → identyczny zbiór kwalifikujących wierszy.
11. **Odstępstwo od litery spec §10 („w transakcji wiersza”, F8).** Spec §10
    mówi „wykonanie w fazie commit, po `row.integrate()`, w transakcji wiersza”.
    Plan robi przepięcia w OSOBNEJ pętli PO całej pętli integracji, każde we
    własnym `transaction.atomic`. Powód: poprawny snapshot starej jednostki
    (trigger DB przestawia `aktualna_jednostka` na jednostkę z pliku podczas
    integracji, patrz Assumption 2) wymaga odczytu PRZED pętlą integracji i
    wykonania przepięć PO niej — nie da się tego wcisnąć w transakcję
    pojedynczego wiersza. Świadome odstępstwo.
12. **Restart integracji po awarii w połowie może pominąć nie-wykonane
    przepięcia (F5, minimalny zakres v1).** Snapshot starej jednostki czyta
    bieżący stan bazy na starcie `integruj`; jeśli pierwszy przebieg utworzył AJ
    (trigger przestawił `aktualna_jednostka` na nową) i padł PRZED
    `_wykonaj_przepiecia`, restart (`RestartView`) zobaczy `stara_id ==
    row.jednostka_id` i pominie przepięcie (zostawiając ślad przez `p.log`).
    Pełne utrwalenie starej jednostki w analizie = poza zakresem v1. NIE dodajemy
    nowego pola schematu (spec §12 dopuszcza tylko `przepnij_prace`).
13. **`cofnij_przemapowanie` za `login_required` (F10).** Spójnie z resztą appki
    `przemapuj_prace_autora` (istniejący `_wykonaj_przemapowanie` też destrukcyjny
    za samym `login_required`). Zaostrzenie do grupy „wprowadzanie danych” =
    osobna decyzja, poza zakresem Fazy 5 — nie zmieniamy bramki, tylko notujemy.

---

## Task 1 — Migracje + pola modelu (`przepnij_prace`, `zrodlowy_import`)

**Files:**
- Modify: `src/import_pracownikow/models.py`
- Modify: `src/przemapuj_prace_autora/models.py`
- Create: `src/import_pracownikow/migrations/0015_przepnij_prace.py`
- Create:
  `src/przemapuj_prace_autora/migrations/0003_przemapoaniepracautora_zrodlowy_import.py`
- Create: `src/import_pracownikow/tests/test_faza5_migracje.py`

**Interfaces — Produces:**
- `ImportPracownikowRow.przepnij_prace: bool` (default `False`).
- `PrzemapoaniePracAutora.zrodlowy_import: ImportPracownikow | None`
  (`related_name="przemapowania"`).

### Step 1.1 — Failing test (pola istnieją)

Utwórz `src/import_pracownikow/tests/test_faza5_migracje.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.mark.django_db
def test_przepnij_prace_pole_domyslnie_false_i_zapisywalne():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp, zmiany_potrzebne=False
    )
    assert row.przepnij_prace is False
    row.przepnij_prace = True
    row.save(update_fields=["przepnij_prace"])
    row.refresh_from_db()
    assert row.przepnij_prace is True


@pytest.mark.django_db
def test_zrodlowy_import_fk_i_related_name():
    imp = baker.make(ImportPracownikow)
    prz = PrzemapoaniePracAutora.objects.create(
        autor=baker.make(Autor),
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
        zrodlowy_import=imp,
    )
    prz.refresh_from_db()
    assert prz.zrodlowy_import_id == imp.pk
    assert list(imp.przemapowania.all()) == [prz]


@pytest.mark.django_db
def test_zrodlowy_import_nullable():
    prz = PrzemapoaniePracAutora.objects.create(
        autor=baker.make(Autor),
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
    )
    assert prz.zrodlowy_import_id is None
```

### Step 1.2 — Run (FAIL)

```bash
uv run pytest src/import_pracownikow/tests/test_faza5_migracje.py -q
```

Oczekiwane: `AttributeError`/`TypeError`/`FieldError` (pole/atrybut nie
istnieje) — `.create(zrodlowy_import=imp)` na modelu bez pola rzuca `TypeError:
... unexpected keyword arguments`, dostęp do `row.przepnij_prace` — `AttributeError`.

### Step 1.3 — Dodaj pole `przepnij_prace` do modelu

W `src/import_pracownikow/models.py`, w klasie `ImportPracownikowRow`, tuż po
polu `utworz_nowego` (linia ~270) dodaj:

```python
    przepnij_prace = models.BooleanField(default=False)
```

### Step 1.4 — Dodaj FK `zrodlowy_import` do modelu

W `src/przemapuj_prace_autora/models.py`, w klasie `PrzemapoaniePracAutora`, po
polu `prace_zwarte_historia` (przed `class Meta`) dodaj:

```python
    zrodlowy_import = models.ForeignKey(
        "import_pracownikow.ImportPracownikow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="przemapowania",
        verbose_name="Import pracowników",
    )
```

### Step 1.5 — Migracja 0015 (import_pracownikow)

Utwórz `src/import_pracownikow/migrations/0015_przepnij_prace.py`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("import_pracownikow", "0014_utworz_nowego_odpiecie"),
    ]

    operations = [
        migrations.AddField(
            model_name="importpracownikowrow",
            name="przepnij_prace",
            field=models.BooleanField(default=False),
        ),
    ]
```

### Step 1.6 — Migracja 0003 (przemapuj_prace_autora, cross-app)

Utwórz
`src/przemapuj_prace_autora/migrations/0003_przemapoaniepracautora_zrodlowy_import.py`:

```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "przemapuj_prace_autora",
            "0002_przemapoaniepracautora_prace_ciagle_historia_and_more",
        ),
        ("import_pracownikow", "0015_przepnij_prace"),
    ]

    operations = [
        migrations.AddField(
            model_name="przemapoaniepracautora",
            name="zrodlowy_import",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="przemapowania",
                to="import_pracownikow.importpracownikow",
                verbose_name="Import pracowników",
            ),
        ),
    ]
```

### Step 1.7 — Weryfikacja braku dryfu migracji + Run (PASS)

```bash
uv run python src/manage.py makemigrations --check --dry-run \
    import_pracownikow przemapuj_prace_autora
uv run pytest src/import_pracownikow/tests/test_faza5_migracje.py -q
```

Oczekiwane: `No changes detected`; 3 testy PASS.

### Step 1.8 — Commit

```bash
git add src/import_pracownikow/models.py \
    src/przemapuj_prace_autora/models.py \
    src/import_pracownikow/migrations/0015_przepnij_prace.py \
    src/przemapuj_prace_autora/migrations/0003_przemapoaniepracautora_zrodlowy_import.py \
    src/import_pracownikow/tests/test_faza5_migracje.py
git commit -m "feat(import-prac): pola przepnij_prace + zrodlowy_import (Faza 5)"
```

---

## Task 2 — Serwis `przemapuj` + ekstrakcja historii + refaktor widoku

**Files:**
- Create: `src/przemapuj_prace_autora/service.py`
- Modify: `src/przemapuj_prace_autora/views.py`
- Create: `src/przemapuj_prace_autora/test_service.py`
- Verify green: `src/przemapuj_prace_autora/test_history.py`,
  `src/przemapuj_prace_autora/test_characterization_view.py`

**Interfaces — Consumes:** `PrzemapoaniePracAutora`, `Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor` (pola `autor`, `jednostka`, `rekord`, `pk`).
**Produces:**
- `service.przemapuj(autor, jednostka_z, jednostka_do, user,
  zrodlowy_import=None) -> PrzemapoaniePracAutora`.
- Wpisy historii ze WSZYSTKimi starymi kluczami + `autor_rekord_pk`,
  `jednostka_z_pk`.

### Step 2.1 — Failing test serwisu

Utwórz `src/przemapuj_prace_autora/test_service.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from przemapuj_prace_autora import service
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.fixture
def autor():
    return baker.make(Autor, nazwisko="Kowalski", imiona="Jan")


@pytest.fixture
def jednostka_z():
    return baker.make(Jednostka, nazwa="Stara", skrot="ST")


@pytest.fixture
def jednostka_do():
    return baker.make(Jednostka, nazwa="Nowa", skrot="NW")


@pytest.mark.django_db
def test_przemapuj_przenosi_tylko_prace_ze_starej_jednostki(
    autor, jednostka_z, jednostka_do
):
    inna = baker.make(Jednostka, nazwa="Inna", skrot="IN")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Artykuł", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    # praca w innej jednostce — NIE ruszamy
    wc2 = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Inny", rok=2024)
    pa2 = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc2, autor=autor, jednostka=inna
    )

    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    pa.refresh_from_db()
    pa2.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk
    assert pa2.jednostka_id == inna.pk
    assert prz.liczba_prac_ciaglych == 1
    assert prz.liczba_prac_zwartych == 0


@pytest.mark.django_db
def test_przemapuj_buduje_wzbogacona_historie(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(
        Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=jednostka_z
    )

    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    wpis_c = prz.prace_ciagle_historia[0]
    assert wpis_c["id"] == wc.id
    assert wpis_c["tytul"] == "Art"
    assert wpis_c["autor_rekord_pk"] == pa.pk
    assert wpis_c["jednostka_z_pk"] == jednostka_z.pk
    wpis_z = prz.prace_zwarte_historia[0]
    assert wpis_z["autor_rekord_pk"] == pz.pk
    assert wpis_z["jednostka_z_pk"] == jednostka_z.pk


@pytest.mark.django_db
def test_przemapuj_ustawia_zrodlowy_import(autor, jednostka_z, jednostka_do):
    from import_pracownikow.models import ImportPracownikow

    imp = baker.make(ImportPracownikow)
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )

    prz = service.przemapuj(
        autor, jednostka_z, jednostka_do, user=None, zrodlowy_import=imp
    )
    assert prz.zrodlowy_import_id == imp.pk
    assert PrzemapoaniePracAutora.objects.get(pk=prz.pk).zrodlowy_import_id == imp.pk
```

### Step 2.2 — Run (FAIL)

```bash
uv run pytest src/przemapuj_prace_autora/test_service.py -q
```

Oczekiwane: `ModuleNotFoundError: przemapuj_prace_autora.service`.

### Step 2.3 — Utwórz serwis

Utwórz `src/przemapuj_prace_autora/service.py`:

```python
"""Serwis domenowy przemapowania prac autora między jednostkami.

Wyekstrahowany z ``views._wykonaj_przemapowanie`` (§10 D6/D7): bez ``request``,
bez ``messages`` — wołany zarówno przez ręczny widok, jak i przez fazę commit
importu pracowników (``import_pracownikow.pipeline.integrate``).
"""

from django.db import transaction

from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

from .models import PrzemapoaniePracAutora


def _historia_prac_ciaglych(prace_ciagle, jednostka_z):
    """Zbuduj historię prac ciągłych PRZED przemapowaniem.

    Zachowuje klucze czytane przez admin/szablon (``id``, ``tytul``, ``rok``,
    ``zrodlo``) i dokłada ``autor_rekord_pk`` (pk Wydawnictwo_Ciagle_Autor) oraz
    ``jednostka_z_pk`` — potrzebne do jednoznacznego undo.
    """
    historia = []
    for praca_autor in prace_ciagle:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "zrodlo": (
                    str(rekord.zrodlo)
                    if hasattr(rekord, "zrodlo") and rekord.zrodlo
                    else None
                ),
                "autor_rekord_pk": praca_autor.pk,
                "jednostka_z_pk": jednostka_z.pk,
            }
        )
    return historia


def _historia_prac_zwartych(prace_zwarte, jednostka_z):
    """Zbuduj historię prac zwartych PRZED przemapowaniem (patrz wyżej)."""
    historia = []
    for praca_autor in prace_zwarte:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "isbn": (rekord.isbn if hasattr(rekord, "isbn") else None),
                "wydawnictwo": (
                    rekord.wydawnictwo if hasattr(rekord, "wydawnictwo") else None
                ),
                "autor_rekord_pk": praca_autor.pk,
                "jednostka_z_pk": jednostka_z.pk,
            }
        )
    return historia


def przemapuj(autor, jednostka_z, jednostka_do, user, zrodlowy_import=None):
    """Przenieś prace autora afiliowane do ``jednostka_z`` na ``jednostka_do``.

    Zakres (D7): wszystkie prace ze ``jednostka_z``, niezależnie od roku. Zwraca
    utworzony rekord audytu ``PrzemapoaniePracAutora``.
    """
    with transaction.atomic():
        prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor, jednostka=jednostka_z
        ).select_related("rekord")
        prace_ciagle_historia = _historia_prac_ciaglych(prace_ciagle, jednostka_z)
        liczba_prac_ciaglych = len(prace_ciagle_historia)
        prace_ciagle.update(jednostka=jednostka_do)

        prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor, jednostka=jednostka_z
        ).select_related("rekord")
        prace_zwarte_historia = _historia_prac_zwartych(prace_zwarte, jednostka_z)
        liczba_prac_zwartych = len(prace_zwarte_historia)
        prace_zwarte.update(jednostka=jednostka_do)

        return PrzemapoaniePracAutora.objects.create(
            autor=autor,
            jednostka_z=jednostka_z,
            jednostka_do=jednostka_do,
            liczba_prac_ciaglych=liczba_prac_ciaglych,
            liczba_prac_zwartych=liczba_prac_zwartych,
            utworzono_przez=user,
            prace_ciagle_historia=prace_ciagle_historia,
            prace_zwarte_historia=prace_zwarte_historia,
            zrodlowy_import=zrodlowy_import,
        )
```

### Step 2.4 — Run (PASS)

```bash
uv run pytest src/przemapuj_prace_autora/test_service.py -q
```

Oczekiwane: 3 testy PASS.

### Step 2.5 — Refaktor `views._wykonaj_przemapowanie`

W `src/przemapuj_prace_autora/views.py`:

1. USUŃ funkcje `_historia_prac_ciaglych` (linie ~85–102) i
   `_historia_prac_zwartych` (linie ~105–121) — przeniesione do serwisu.
2. USUŃ nieużywany po refaktorze import `from django.db import transaction`.
3. Dodaj import serwisu obok istniejących: `from . import service`.
4. Zastąp całe ciało `_wykonaj_przemapowanie` (linie ~124–172) przez:

```python
def _wykonaj_przemapowanie(request, autor, form):
    """Wykonaj potwierdzone przemapowanie. Zwraca redirect lub ``None``.

    ``None`` oznacza, że wystąpił błąd (komunikat już ustawiony) i widok ma
    spaść do dolnego renderu.
    """
    jednostka_z = form.cleaned_data["jednostka_z"]
    jednostka_do = form.cleaned_data["jednostka_do"]

    try:
        przemapowanie = service.przemapuj(
            autor, jednostka_z, jednostka_do, request.user
        )
    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(
            request, f"Wystąpił błąd podczas przemapowania prac: {str(e)}"
        )
        return None

    messages.success(
        request,
        f"Pomyślnie przemapowano {przemapowanie.liczba_prac_ciaglych} prac "
        f"ciągłych i {przemapowanie.liczba_prac_zwartych} prac zwartych "
        f'z jednostki "{jednostka_z}" do jednostki "{jednostka_do}".',
    )
    return redirect(
        "przemapuj_prace_autora:przemapuj_prace", autor_id=autor.pk
    )
```

Uwaga: komunikat sukcesu użyty jest w literale z apostrofem-delimitera (`f'...'`),
więc ASCII `"` wokół nazw jednostek są bezpieczne (nie zamykają literału).

### Step 2.6 — Run istniejących testów widoku/historii (PASS)

```bash
uv run pytest src/przemapuj_prace_autora/test_history.py \
    src/przemapuj_prace_autora/test_characterization_view.py \
    src/przemapuj_prace_autora/test_service.py -q
```

Oczekiwane: wszystkie PASS (historia zachowuje stare klucze + dokłada nowe;
widok nadal robi redirect 302 + `messages.success`).

### Step 2.7 — Commit

```bash
git add src/przemapuj_prace_autora/service.py \
    src/przemapuj_prace_autora/views.py \
    src/przemapuj_prace_autora/test_service.py
git commit -m "refactor(przemapuj): ekstrakcja service.przemapuj + wzbogacona historia"
```

---

## Task 3 — `service.cofnij` (undo z guardem, idempotentne)

**Files:**
- Modify: `src/przemapuj_prace_autora/service.py`
- Modify: `src/przemapuj_prace_autora/test_service.py`

**Interfaces — Consumes:** `PrzemapoaniePracAutora` (`prace_ciagle_historia`,
`prace_zwarte_historia`, `jednostka_do_id`), `Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`.
**Produces:** `service.cofnij(przemapowanie) -> (cofnieto: int, pominieto: int)`.

### Step 3.1 — Failing testy undo

Dopisz do `src/przemapuj_prace_autora/test_service.py`:

```python
@pytest.mark.django_db
def test_cofnij_przywraca_prace(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_z.pk
    assert (cofnieto, pominieto) == (1, 0)


@pytest.mark.django_db
def test_cofnij_guard_praca_zmienila_jednostke_po(
    autor, jednostka_z, jednostka_do
):
    trzecia = baker.make(Jednostka, nazwa="Trzecia", skrot="TR")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    # praca po przemapowaniu zmieniła afiliację ręcznie — NIE cofamy na ślepo
    Wydawnictwo_Ciagle_Autor.objects.filter(pk=pa.pk).update(jednostka=trzecia)

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == trzecia.pk
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_pomija_stary_wpis_bez_autor_rekord_pk(
    autor, jednostka_z, jednostka_do
):
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=jednostka_z,
        jednostka_do=jednostka_do,
        prace_ciagle_historia=[{"id": 1, "tytul": "stary", "rok": 2020}],
        prace_zwarte_historia=[],
    )
    cofnieto, pominieto = service.cofnij(prz)
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_pomija_wpis_ze_skasowana_jednostka_z(
    autor, jednostka_z, jednostka_do
):
    # F6: jednostka źródłowa undo usunięta w międzyczasie — wpis pomijamy
    # (bez próby save → bez IntegrityError wywracającego CAŁE undo).
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_do
    )
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=jednostka_z,
        jednostka_do=jednostka_do,
        prace_ciagle_historia=[
            {
                "id": wc.id,
                "tytul": "A",
                "rok": 2023,
                "autor_rekord_pk": pa.pk,
                "jednostka_z_pk": 987654321,
            }
        ],
        prace_zwarte_historia=[],
    )

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk  # NIETKNIĘTE
    assert (cofnieto, pominieto) == (0, 1)


@pytest.mark.django_db
def test_cofnij_idempotentne(autor, jednostka_z, jednostka_do):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)

    assert service.cofnij(prz) == (1, 0)
    # drugie cofnięcie: praca już w jednostka_z != jednostka_do → pominięta
    assert service.cofnij(prz) == (0, 1)
    # rekord audytu NIE skasowany
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()


@pytest.mark.django_db
def test_cofnij_omija_clean_dyscypliny(autor, jednostka_z, jednostka_do):
    # G1: praca z `dyscyplina_naukowa`, dla której autor NIE ma
    # `Autor_Dyscyplina` na rok rekordu → `obj.save()` odpaliłby
    # `clean()`/`_waliduj_dyscypline` (ValidationError). Querysetowy `.update()`
    # w `cofnij` (symetryczny z forward `przemapuj`) omija clean/side-effecty →
    # undo przechodzi. Stan budujemy przez `.update()`, by NIE odpalić clean
    # przy tworzeniu (baker.make woła save()).
    from bpp.models import Dyscyplina_Naukowa

    dyscyplina = baker.make(Dyscyplina_Naukowa)
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jednostka_z
    )
    Wydawnictwo_Ciagle_Autor.objects.filter(pk=pa.pk).update(
        dyscyplina_naukowa=dyscyplina
    )
    prz = service.przemapuj(autor, jednostka_z, jednostka_do, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_do.pk

    cofnieto, pominieto = service.cofnij(prz)

    pa.refresh_from_db()
    assert pa.jednostka_id == jednostka_z.pk
    assert (cofnieto, pominieto) == (1, 0)
```

### Step 3.2 — Run (FAIL)

```bash
uv run pytest src/przemapuj_prace_autora/test_service.py -q -k cofnij
```

Oczekiwane: `AttributeError: module ... has no attribute 'cofnij'`.

### Step 3.3 — Implementacja `cofnij`

Najpierw rozszerz import z `bpp.models` na górze `service.py` o `Jednostka`
(używane przez guard F6 poniżej):

```python
from bpp.models import (
    Jednostka,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
```

Dopisz do `src/przemapuj_prace_autora/service.py` (po `przemapuj`):

```python
def cofnij(przemapowanie):
    """Cofnij przemapowanie po wpisach historii. Zwraca ``(cofnieto, pominieto)``.

    Dla każdego wpisu przywraca ``autor_rekord_pk`` do ``jednostka_z_pk`` TYLKO
    gdy jego bieżąca ``jednostka == przemapowanie.jednostka_do`` (guard przed
    nadpisaniem późniejszych zmian). Przywrócenie robimy STRZEŻONYM
    querysetowym ``.update()`` (guard + brak rekordu w JEDNYM atomowym
    zapytaniu) — SYMETRYCZNIE z forward ``przemapuj`` (też ``.update()``), więc
    OMIJAMY ``clean()``/side-effecty ``Wydawnictwo_*_Autor.save()``
    (``_waliduj_dyscypline``/``_waliduj_afiliacje`` → ``ValidationError``,
    auto-tworzenie ``Autor_Jednostka``). Inaczej undo pracy z dyscypliną bez
    ``Autor_Dyscyplina`` na rok rekordu wywróciłoby CAŁE ``transaction.atomic``.
    Wpisy bez pk (sprzed enrichmentu), nieistn. rekordy, wpisy ze SKASOWANĄ
    jednostką źródłową (F6) i te niepasujące do guarda → ``pominieto``. NIE
    kasuje rekordu ``PrzemapoaniePracAutora`` (audyt) — guard czyni undo
    idempotentnym.
    """
    cofnieto = 0
    pominieto = 0
    historie = (
        (przemapowanie.prace_ciagle_historia, Wydawnictwo_Ciagle_Autor),
        (przemapowanie.prace_zwarte_historia, Wydawnictwo_Zwarte_Autor),
    )
    # F6: jednostka źródłowa undo mogła zostać usunięta w międzyczasie →
    # querysetowy ``.update(jednostka_id=jz)`` z FK na nieistniejącą jednostkę
    # rzuca `IntegrityError` i wywraca CAŁE `transaction.atomic` (rollback już
    # cofniętych wpisów). Zbierz istniejące pk RAZ; wpis wskazujący
    # nieistniejącą jednostkę pomijamy BEZ próby zapisu.
    jz_pks = {
        wpis.get("jednostka_z_pk")
        for historia, _ in historie
        for wpis in historia or []
        if wpis.get("jednostka_z_pk") is not None
    }
    istniejace = set(
        Jednostka.objects.filter(pk__in=jz_pks).values_list("pk", flat=True)
    )
    with transaction.atomic():
        for historia, model in historie:
            for wpis in historia or []:
                pk = wpis.get("autor_rekord_pk")
                jz = wpis.get("jednostka_z_pk")
                if pk is None or jz is None:
                    pominieto += 1
                    continue
                if jz not in istniejace:
                    pominieto += 1
                    continue
                # Strzeżony queryset update: guard (jednostka==jednostka_do) +
                # brak rekordu w JEDNYM zapytaniu; OMIJA clean()/side-effecty
                # (symetrycznie z forward `przemapuj`).
                n = model.objects.filter(
                    pk=pk, jednostka_id=przemapowanie.jednostka_do_id
                ).update(jednostka_id=jz)
                if n == 1:
                    cofnieto += 1
                else:
                    # pk nie istnieje ALBO praca zmieniła afiliację po
                    # przemapowaniu (guard niespełniony).
                    pominieto += 1
    return cofnieto, pominieto
```

### Step 3.4 — Run (PASS)

```bash
uv run pytest src/przemapuj_prace_autora/test_service.py -q
```

Oczekiwane: wszystkie testy serwisu PASS (Task 2 + Task 3).

### Step 3.5 — Commit

```bash
git add src/przemapuj_prace_autora/service.py \
    src/przemapuj_prace_autora/test_service.py
git commit -m "feat(przemapuj): service.cofnij — idempotentne undo z guardem"
```

---

## Task 4 — Przepięcia w fazie commit (`pipeline/integrate.py`)

**Files:**
- Modify: `src/import_pracownikow/models.py` (helpery kwalifikacji F1/F2/F3)
- Modify: `src/import_pracownikow/pipeline/integrate.py`
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html`
  (F7 — liczniki przepięć/odpięć/nowych autorów)
- Create: `src/import_pracownikow/tests/test_pipeline/test_integrate_przepiecia.py`

**Interfaces — Consumes:** `service.przemapuj(...)`,
`ImportPracownikowRow.przepnij_prace`, `parent.owner`, `Jednostka`.
**Produces:**
- `ImportPracownikow.pary_z_pliku() -> set[(autor_id, jednostka_id)]` — zbiór
  „par z pliku” (wiersze z autorem i jednostką); używane też przez Task 5.
- `wiersz_kwalifikuje_do_przepiecia(autor_id, stara_id, jednostka_id,
  pary_z_pliku) -> bool` — wspólny warunek kwalifikacji (F1/F2/F3), używany też
  przez Task 5.
- `_wykonaj_przepiecia(parent, stare_jednostki, user, p) ->
  (przepieto_wierszy, przepieto_prac)`.
- `p.result(...)` dostaje klucze `przepieto_wierszy`, `przepieto_prac`.
- `row.log_zmian["przepiecie"] = {"pk", "prace_ciagle", "prace_zwarte", "z",
  "do"}`; przy duplikacie (F3) `row.log_zmian["przepiecie_pominiete"]` (str).

### Step 4.1 — Failing testy pipeline

Utwórz `src/import_pracownikow/tests/test_pipeline/test_integrate_przepiecia.py`:

```python
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


def _autor_ze_starą_jednostką():
    stara = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == stara.pk
    return autor, stara


@pytest.mark.django_db
def test_commit_przepina_prace_opt_in(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(
        Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=stara
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == nowa.pk
    assert pz.jednostka_id == nowa.pk

    prz = PrzemapoaniePracAutora.objects.get(autor=autor)
    assert prz.zrodlowy_import_id == imp.pk
    assert prz.jednostka_z_id == stara.pk
    assert prz.jednostka_do_id == nowa.pk
    assert p.result_context["przepieto_wierszy"] == 1
    assert p.result_context["przepieto_prac"] == 2

    row.refresh_from_db()
    assert row.log_zmian["przepiecie"]["pk"] == prz.pk
    assert row.log_zmian["przepiecie"]["prace_ciagle"] == 1
    assert row.log_zmian["przepiecie"]["prace_zwarte"] == 1


@pytest.mark.django_db
def test_commit_bez_roznicy_jednostki_nie_przepina(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    # jednostka wiersza == aktualna (stara) → brak różnicy, nic do przepięcia
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=stara,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0


@pytest.mark.django_db
def test_commit_bez_flagi_nie_przepina(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=False,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0


@pytest.mark.django_db
def test_commit_nie_przepina_gdy_stara_jednostka_jest_w_pliku(admin_user):
    # F1 „pułapka drugiego etatu”: plik ma wiersz A (etat = stara jednostka)
    # ORAZ wiersz B (różnica jednostki). Guard „para z pliku” MUSI pominąć
    # przepięcie A→B, bo etat A jest POTWIERDZONY w pliku (wiersz A).
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    # wiersz A: potwierdza etat w starej jednostce (para (autor, stara) z pliku)
    ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    # wiersz B: różnica jednostki, opt-in przepięcia
    row_b = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    pa.refresh_from_db()
    assert pa.jednostka_id == stara.pk  # prace A NIETKNIĘTE (guard zadziałał)
    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0
    row_b.refresh_from_db()
    assert "przepiecie" not in (row_b.log_zmian or {})


@pytest.mark.django_db
def test_commit_duplikat_autora_przepina_raz(admin_user):
    # F3: dwa wiersze tego samego autora (stara → B, stara → C), brak wiersza
    # A w pliku (F1-guard nie łapie). Przepięcie wykonujemy RAZ (pierwszy po
    # pk), drugi wiersz dostaje ślad „duplikat” bez pustego rekordu.
    autor, stara = _autor_ze_starą_jednostką()
    jed_b = baker.make(Jednostka, nazwa="B", skrot="BB")
    jed_c = baker.make(Jednostka, nazwa="C", skrot="CC")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    row_b = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jed_b,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )
    row_c = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jed_c,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    # JEDNO przemapowanie; prace w jednej jednostce (pierwszy wiersz po pk)
    assert PrzemapoaniePracAutora.objects.filter(autor=autor).count() == 1
    prz = PrzemapoaniePracAutora.objects.get(autor=autor)
    pa.refresh_from_db()
    assert pa.jednostka_id == prz.jednostka_do_id
    assert prz.jednostka_do_id == jed_b.pk  # row_b ma mniejszy pk
    assert p.result_context["przepieto_wierszy"] == 1
    row_b.refresh_from_db()
    row_c.refresh_from_db()
    assert row_b.log_zmian["przepiecie"]["do"] == jed_b.skrot
    assert "przepiecie" not in (row_c.log_zmian or {})
    assert "przepiecie_pominiete" in row_c.log_zmian
```

### Step 4.2 — Run (FAIL)

```bash
uv run pytest \
    src/import_pracownikow/tests/test_pipeline/test_integrate_przepiecia.py -q
```

Oczekiwane: `KeyError: 'przepieto_wierszy'` (result nie ma jeszcze kluczy) /
brak przepięcia.

### Step 4.3a — Wspólne helpery kwalifikacji w `models.py` (F1/F2/F3)

W `src/import_pracownikow/models.py` dodaj metodę `pary_z_pliku` do klasy
`ImportPracownikow` (obok `autorzy_spoza_pliku_set`) oraz czystą funkcję
modułową `wiersz_kwalifikuje_do_przepiecia` (na końcu pliku albo przed klasami
— byle importowalna). Te dwa helpery są JEDYNYM źródłem prawdy o tym, które
wiersze kwalifikują się do przepięcia — użyte identycznie w commit (Task 4) i
w UI (Task 5).

W klasie `ImportPracownikow` (po `autorzy_spoza_pliku_set`) dodaj:

```python
    def pary_z_pliku(self):
        """Zbiór par ``(autor_id, jednostka_id)`` OBECNYCH w wierszach importu
        (autor i jednostka ustawione) — „para z pliku”, tj. potwierdzony etat.

        Wspólne źródło dla guardu „para z pliku” w przepięciach (F1) i dla
        definicji „spoza pliku” w odpięciach (§9). Semantyka identyczna z
        per-wierszowym ``.filter(autor_id=, jednostka_id=).exists()`` guardu G1.
        """
        return set(
            self.importpracownikowrow_set.filter(
                autor__isnull=False, jednostka__isnull=False
            )
            .values_list("autor_id", "jednostka_id")
            .distinct()
        )
```

Zrefaktoruj przy okazji `autorzy_spoza_pliku_set`, żeby korzystała z tej metody
(DRY, gwarancja tego samego zbioru): zastąp wewnętrzne budowanie `pary_z_pliku`

```python
        pary_z_pliku = set(
            self.importpracownikowrow_set.filter(
                autor__isnull=False, jednostka__isnull=False
            )
            .values_list("autor_id", "jednostka_id")
            .distinct()
        )
```

przez:

```python
        pary_z_pliku = self.pary_z_pliku()
```

Na końcu pliku (funkcja modułowa) dodaj:

```python
def wiersz_kwalifikuje_do_przepiecia(
    autor_id, stara_id, jednostka_id, pary_z_pliku
):
    """Czy wiersz kwalifikuje się do przepięcia prac (§10 D6/D7, F1/F2/F3).

    Wspólny warunek dla podglądu (kolumna/toggle/bulk) i fazy commit — MUSI
    dać identyczny zbiór kwalifikujących wierszy wszędzie. ``stara_id`` =
    ``aktualna_jednostka`` autora sprzed importu (w podglądzie odczyt live, w
    commit ze snapshotu — trigger DB zdążył ją przestawić).

    True gdy: autor ustawiony, stara i nowa jednostka ustawione (F2) i różne
    (jest co przepiąć), a para ``(autor_id, stara_id)`` NIE jest parą Z PLIKU
    (stara jednostka nie jest potwierdzona jako aktywny etat w innym wierszu —
    inaczej „pułapka drugiego etatu”, F1).
    """
    if autor_id is None or stara_id is None or jednostka_id is None:
        return False
    if stara_id == jednostka_id:
        return False
    if (autor_id, stara_id) in pary_z_pliku:
        return False
    return True
```

### Step 4.3 — Dodaj `_wykonaj_przepiecia` + snapshot + wołanie w `integruj`

W `src/import_pracownikow/pipeline/integrate.py`:

1. Dodaj `Jednostka` do importu z `bpp.models`:

```python
from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Wymiar_Etatu,
)
```

2. Rozszerz istniejący import z `import_pracownikow.models` o helpery
   kwalifikacji (obok `ImportPracownikow`):

```python
from import_pracownikow.models import (
    ImportPracownikow,
    wiersz_kwalifikuje_do_przepiecia,
)
```

   oraz dodaj import serwisu na końcu bloku importów:

```python
from przemapuj_prace_autora import service as przemapuj_service
```

3. Dodaj funkcję `_wykonaj_przepiecia` (obok `_wykonaj_odpiecia`):

```python
def _wykonaj_przepiecia(parent, stare_jednostki, user, p):
    """Przepina prace dla wierszy ``przepnij_prace=True`` (§10 D6/D7).

    ``stare_jednostki`` = ``{row.pk: aktualna_jednostka_id sprzed importu}``
    zebrane PRZED pętlą integracji (trigger DB przestawia ``aktualna_jednostka``
    na jednostkę z pliku). Kwalifikacja wiersza przez wspólny
    ``wiersz_kwalifikuje_do_przepiecia`` (F1/F2/F3 — identyczny warunek co w
    UI): autor+jednostki ustawione i różne, a stara jednostka NIE jest
    potwierdzona jako etat w innym wierszu pliku (guard „para z pliku”, F1).

    F4: filtr wyklucza wiersze ``pominiety_bo_nieaktualny=True`` (drift bazy —
    integracja się NIE wykonała, więc nie przepinamy na podstawie nieaktualnego
    podglądu) oraz ``jednostka__isnull=False`` (F2). F5: gdy stara == docelowa
    (możliwy restart po częściowej integracji) zostawiamy ślad przez ``p.log``.
    F3: dla duplikatu autora z tą samą starą jednostką (dwa wiersze, różne nowe
    jednostki) przepięcie wykonujemy RAZ (pierwszy po ``pk`` — iterujemy z
    ``order_by("pk")``), kolejnym wpisujemy ślad ``przepiecie_pominiete`` bez
    pustego rekordu. Zwraca ``(przepieto_wierszy, przepieto_prac)``.
    """
    przepieto_wierszy = 0
    przepieto_prac = 0
    pary_z_pliku = parent.pary_z_pliku()
    juz_przepiete = set()
    for row in (
        parent.importpracownikowrow_set.filter(
            przepnij_prace=True,
            autor__isnull=False,
            jednostka__isnull=False,
            pominiety_bo_nieaktualny=False,
        )
        .select_related("autor")
        .order_by("pk")
    ):
        stara_id = stare_jednostki.get(row.pk)
        # F5: snapshot czyta bieżący stan — po restarcie stara może już być
        # docelową; zostawiamy ślad, nie przepinamy.
        if stara_id is not None and stara_id == row.jednostka_id:
            p.log(
                f"Wiersz {row.pk}: pominięto przepięcie — jednostka źródłowa "
                "== docelowa (brak zmiany do przepięcia)"
            )
            continue
        if not wiersz_kwalifikuje_do_przepiecia(
            row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
        ):
            continue
        # F3: duplikat autora z tą samą starą jednostką — przepinamy raz.
        if (row.autor_id, stara_id) in juz_przepiete:
            if row.log_zmian is None:
                row.log_zmian = {"autor": [], "autor_jednostka": []}
            row.log_zmian["przepiecie_pominiete"] = (
                "pominięto — prace tego autora ze starej jednostki już "
                "przepięte w innym wierszu tego importu"
            )
            row.save(update_fields=["log_zmian"])
            continue
        # G3: jednostka źródłowa (ze snapshotu) lub docelowa mogła zostać
        # usunięta między snapshotem a przepięciem — pomiń wiersz przez
        # `filter().first()` zamiast `get()`, żeby nieobsłużony `DoesNotExist`
        # nie wywrócił CAŁEGO taska integracji (okno = cała pętla, minuty).
        jednostka_z = Jednostka.objects.filter(pk=stara_id).first()
        jednostka_do = Jednostka.objects.filter(pk=row.jednostka_id).first()
        if jednostka_z is None or jednostka_do is None:
            p.log(
                f"Wiersz {row.pk}: pominięto przepięcie — jednostka źródłowa "
                "lub docelowa usunięta"
            )
            continue
        with transaction.atomic():
            prz = przemapuj_service.przemapuj(
                row.autor,
                jednostka_z,
                jednostka_do,
                user,
                zrodlowy_import=parent,
            )
            if row.log_zmian is None:
                row.log_zmian = {"autor": [], "autor_jednostka": []}
            row.log_zmian["przepiecie"] = {
                "pk": prz.pk,
                "prace_ciagle": prz.liczba_prac_ciaglych,
                "prace_zwarte": prz.liczba_prac_zwartych,
                "z": jednostka_z.skrot,
                "do": jednostka_do.skrot,
            }
            row.save(update_fields=["log_zmian"])
            juz_przepiete.add((row.autor_id, stara_id))
            przepieto_wierszy += 1
            przepieto_prac += (
                prz.liczba_prac_ciaglych + prz.liczba_prac_zwartych
            )
    return przepieto_wierszy, przepieto_prac
```

4. W `integruj` — na SAMYM POCZĄTKU (przed pętlą nowych autorów) zbierz
   snapshot; po `_wykonaj_odpiecia` wywołaj przepięcia; dorzuć klucze do
   `p.result`. Zmodyfikuj `integruj` tak:

```python
def integruj(parent, p):
    # Snapshot starych jednostek PRZED integracją: trigger DB
    # `bpp_autor_ustaw_jednostka_aktualna` przestawi `aktualna_jednostka` na
    # jednostkę z pliku, więc to jedyny moment, gdy widać stan sprzed importu.
    # Snapshot jest SZERSZY niż finalny filtr w `_wykonaj_przepiecia` (F4): na
    # tym etapie nie wiemy jeszcze, które wiersze zostaną `pominiety_bo_
    # nieaktualny`; kwalifikację (w tym `pominiety_bo_nieaktualny=False`)
    # rozstrzyga dopiero pętla w `_wykonaj_przepiecia`.
    stare_jednostki = {}
    for row in parent.importpracownikowrow_set.filter(
        przepnij_prace=True, autor__isnull=False, jednostka__isnull=False
    ).select_related("autor"):
        stare_jednostki[row.pk] = row.autor.aktualna_jednostka_id

    utworzono_nowych = 0
    # (… istniejąca pętla nowych autorów bez zmian …)
    nowi_autorzy_cache = {}
    for row in list(
        parent.importpracownikowrow_set.filter(
            confidence=STATUS_BRAK, utworz_nowego=True, autor__isnull=True
        )
    ):
        if _przygotuj_nowego_autora(row, nowi_autorzy_cache):
            utworzono_nowych += 1

    qs = parent.zmiany_potrzebne_set.all()
    for row in p.track(list(qs), total=qs.count(), label="Integracja"):
        _integruj_wiersz(row)

    odpieto = _wykonaj_odpiecia(parent)
    przepieto_wierszy, przepieto_prac = _wykonaj_przepiecia(
        parent, stare_jednostki, parent.owner, p
    )

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])

    pominieto_nieaktualne = parent.importpracownikowrow_set.filter(
        pominiety_bo_nieaktualny=True
    ).count()
    zintegrowano = parent.zmiany_potrzebne_set.count() - pominieto_nieaktualne

    pominieto_niedopasowane = parent.importpracownikowrow_set.filter(
        confidence__in=[STATUS_BRAK, STATUS_WIELU], autor__isnull=True
    ).count()
    p.result(
        {
            "zintegrowano": zintegrowano,
            "pominieto_nieaktualne": pominieto_nieaktualne,
            "pominieto_niedopasowane": pominieto_niedopasowane,
            "wymaga_uwagi": pominieto_niedopasowane > 0,
            "odpieto": odpieto,
            "przepieto_wierszy": przepieto_wierszy,
            "przepieto_prac": przepieto_prac,
            "utworzono_nowych_autorow": utworzono_nowych,
            "stan": parent.stan,
        }
    )
```

(Zachowaj istniejące komentarze wewnątrz `integruj` — powyżej skrócone tylko
w prezentacji planu; w kodzie NIE usuwaj objaśnień przy `zintegrowano` /
`pominieto_niedopasowane`.)

### Step 4.3c — Liczniki przepięć/odpięć/nowych autorów w panelu wyniku (F7)

Szablon `import_pracownikow_result.html` (liveops result fragment, kontekst =
klucze z `result_context`, patrz Task 4 `p.result`) renderuje na razie tylko
`zintegrowano`/`pominieto_nieaktualne`. Dołóż w gałęzi `{% else %}` (faza
integracji), PO akapicie „Zintegrowano wierszy…” a PRZED linkiem „Zobacz
szczegóły”, widoczność nowych i Fazy-4 kluczy:

```django
        {% if odpieto %}
            <p>Zakończono zatrudnień (odpięcia):
                <strong>{{ odpieto }}</strong>.</p>
        {% endif %}
        {% if utworzono_nowych_autorow %}
            <p>Utworzono nowych autorów:
                <strong>{{ utworzono_nowych_autorow }}</strong>.</p>
        {% endif %}
        {% if przepieto_wierszy %}
            <p>Przepięto prace:
                <strong>{{ przepieto_wierszy }}</strong> wierszy /
                <strong>{{ przepieto_prac }}</strong> prac.</p>
        {% endif %}
```

Zaktualizuj też komentarz `{# … faza integracji: … #}` na górze szablonu, żeby
wymieniał nowe klucze (`odpieto`, `utworzono_nowych_autorow`, `przepieto_wierszy`,
`przepieto_prac`) — każda linia własne jednoliniowe `{# #}`.

### Step 4.4 — Run (PASS) + regresja odpięć

```bash
uv run pytest \
    src/import_pracownikow/tests/test_pipeline/test_integrate_przepiecia.py \
    src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py -q
```

Oczekiwane: nowe 5 testów PASS; testy odpięć nadal PASS (`p.result_context`
dostaje dodatkowe klucze, nie usuwa starych).

### Step 4.5 — Commit

```bash
git add src/import_pracownikow/models.py \
    src/import_pracownikow/pipeline/integrate.py \
    src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html \
    src/import_pracownikow/tests/test_pipeline/test_integrate_przepiecia.py
git commit -m "feat(import-prac): przepięcie prac w fazie commit (_wykonaj_przepiecia)"
```

---

## Task 5 — UI podglądu: kolumna, toggle HTMX, akcja zbiorcza

**Files:**
- Modify: `src/import_pracownikow/views.py`
- Modify: `src/import_pracownikow/urls.py`
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
- Create: `src/import_pracownikow/tests/test_views_przepiecie.py`

**Interfaces — Consumes:** `ImportPracownikowRow.przepnij_prace`,
`_WierszImportuMixin`, `_ImportPodgladMixin`, `get_details_set()`,
`ImportPracownikow.pary_z_pliku()`, `wiersz_kwalifikuje_do_przepiecia(...)`
(z Task 4 / `models.py` — F1/F2 identyczny warunek co commit).
**Produces:**
- `oznacz_przepiecie_prac(rows, parent)` — ustawia na wierszach
  `przepnij_dostepne`, `przepnij_stara_jednostka`, `przepnij_liczba_prac`.
- `PrzepnijPraceView` (name `przepnij-prace`) — walidacja 400 TYLKO przy
  WŁĄCZANIU niekwalifikującego wiersza (F2/G2); odznaczanie zawsze dozwolone.
  `ZaznaczWszystkiePrzepieciaView` (name `zaznacz-przepiecia`) — bulk po
  wspólnym warunku kwalifikacji (F1/F2).

### Step 5.1 — Failing testy widoków

Utwórz `src/import_pracownikow/tests/test_views_przepiecie.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


def _autor_z_aktualna(nazwa="Stara"):
    stara = baker.make(Jednostka, nazwa=nazwa, skrot=nazwa[:2].upper())
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    return autor, stara


def _import(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(ImportPracownikow, owner=owner, stan=stan)


@pytest.mark.django_db
def test_toggle_przepnij_prace_ustawia_flage(admin_client, admin_user):
    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.przepnij_prace is True

    resp = admin_client.post(url, {})
    row.refresh_from_db()
    assert row.przepnij_prace is False


@pytest.mark.django_db
def test_toggle_blokada_poza_podgladem(admin_client, admin_user):
    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_bulk_zaznacza_tylko_wiersze_z_roznica(admin_client, admin_user):
    # UWAGA: różni autorzy dla row_diff i row_same — inaczej jednostka „stara”
    # autora z row_diff stałaby się parą Z PLIKU (przez row_same) i guard F1
    # słusznie by ją odrzucił. Tu izolujemy sam warunek różnicy jednostki.
    autor_diff, stara_diff = _autor_z_aktualna("Sda")
    autor_same, stara_same = _autor_z_aktualna("Ssa")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    # różnica jednostki, stara jednostka NIE w innym wierszu → zaznaczony
    row_diff = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor_diff, jednostka=nowa, zmiany_potrzebne=False
    )
    # brak różnicy (jednostka == aktualna) → NIE zaznaczony
    row_same = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor_same, jednostka=stara_same,
        zmiany_potrzebne=False,
    )
    # bez autora → NIE zaznaczony
    row_bez = ImportPracownikowRow.objects.create(
        parent=imp, autor=None, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:zaznacz-przepiecia", kwargs={"pk": imp.pk}
    )
    resp = admin_client.post(url)
    assert resp.status_code == 302
    for row, oczekiwane in (
        (row_diff, True),
        (row_same, False),
        (row_bez, False),
    ):
        row.refresh_from_db()
        assert row.przepnij_prace is oczekiwane


@pytest.mark.django_db
def test_bulk_pomija_wiersz_gdy_stara_jednostka_w_pliku(admin_client, admin_user):
    # F1: autor z etatem w „stara” potwierdzonym osobnym wierszem pliku
    # (jednostka=stara) ORAZ wierszem z różnicą (jednostka=nowa). Bulk NIE
    # zaznacza wiersza-różnicy — stara jednostka jest parą Z PLIKU.
    autor, stara = _autor_z_aktualna("Pul")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    imp = _import(admin_user)
    row_a = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    row_b = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=nowa, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:zaznacz-przepiecia", kwargs={"pk": imp.pk}
    )
    resp = admin_client.post(url)
    assert resp.status_code == 302
    row_a.refresh_from_db()
    row_b.refresh_from_db()
    assert row_a.przepnij_prace is False
    assert row_b.przepnij_prace is False  # guard „para z pliku”


@pytest.mark.django_db
def test_kolumna_widoczna_tylko_przy_roznicy_jednostki(admin_client, admin_user):
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor

    autor, stara = _autor_z_aktualna()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    imp = _import(admin_user)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    # dodatkowo import ma finished_successfully, by tabela się wyrenderowała
    ImportPracownikow.objects.filter(pk=imp.pk).update(
        finished_successfully=True
    )
    url = reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )
    resp = admin_client.get(url)
    content = resp.content.decode("utf-8")
    assert "przepnij_prace" in content
    assert "(1 prac)" in content


@pytest.mark.django_db
def test_toggle_wlaczenie_niekwalifikujacego_400(admin_client, admin_user):
    # G7/F2: włączenie przepięcia na wierszu BEZ różnicy jednostki
    # (jednostka == aktualna) → 400, flaga NIEZMIENIona.
    autor, stara = _autor_z_aktualna()
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"przepnij_prace": "on"})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.przepnij_prace is False


@pytest.mark.django_db
def test_toggle_odznaczenie_niekwalifikujacego_dozwolone(
    admin_client, admin_user
):
    # G2: wiersz, który przestał się kwalifikować (jednostka == aktualna), z
    # flagą-zombie przepnij_prace=True musi dać się ODZNACZYĆ — odznaczanie nie
    # waliduje kwalifikacji (inaczej flagi nie dałoby się zdjąć).
    autor, stara = _autor_z_aktualna()
    imp = _import(admin_user)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=stara,
        zmiany_potrzebne=False,
        przepnij_prace=True,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
    )
    url = reverse(
        "import_pracownikow:przepnij-prace",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.przepnij_prace is False
```

### Step 5.2 — Run (FAIL)

```bash
uv run pytest src/import_pracownikow/tests/test_views_przepiecie.py -q
```

Oczekiwane: `NoReverseMatch` (brak URL `przepnij-prace` / `zaznacz-przepiecia`).

### Step 5.3 — Helper + widoki w `views.py`

W `src/import_pracownikow/views.py`:

1. Rozszerz importy z `django.db.models` o `Count` (istniejące:
   `Case, IntegerField, Prefetch, Q, Value, When`). `F` NIE jest potrzebne —
   bulk (F1) liczymy w Pythonie, nie przez `.exclude(F())`:

```python
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Prefetch,
    Q,
    Value,
    When,
)
```

2. Rozszerz import z `bpp.models` (istniejący ma tylko `Tytul`):

```python
from bpp.models import (
    Jednostka,
    Tytul,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
```

2b. Rozszerz istniejący import z `import_pracownikow.models` (blok w liniach
    ~20–26) o funkcję `wiersz_kwalifikuje_do_przepiecia` (F1/F2 — ta sama
    funkcja, której używa commit). `pary_z_pliku` z Task 4 jest METODĄ na
    `ImportPracownikow` (`parent.pary_z_pliku()`), więc jej NIE importujemy —
    wywołujemy przez instancję. Zachowaj dotychczas importowane nazwy z tego
    bloku, dodając tylko:

```python
    wiersz_kwalifikuje_do_przepiecia,
```

3. Dodaj helper (po `GROUP_REQUIRED`, przed klasami widoków):

```python
def oznacz_przepiecie_prac(rows, parent):
    """Dokłada do każdego wiersza atrybuty sterujące kolumną „Przepnij prace”.

    ``przepnij_dostepne`` (bool), ``przepnij_stara_jednostka`` (Jednostka|None),
    ``przepnij_liczba_prac`` (int). N liczone AGREGATEM (dwa GROUP BY na
    Wydawnictwo_*_Autor) dla wszystkich kwalifikujących się wierszy naraz —
    bez N+1. Kwalifikacja przez wspólny ``wiersz_kwalifikuje_do_przepiecia``
    (F1/F2 — IDENTYCZNY warunek co faza commit i akcja zbiorcza): autor
    ustawiony, stara i nowa jednostka ustawione i różne, a stara jednostka NIE
    jest „parą z pliku” (potwierdzonym etatem w innym wierszu — pułapka drugiego
    etatu). ``parent.pary_z_pliku()`` liczone RAZ na całym imporcie (dla
    pojedynczego wiersza w swapie HTMX też patrzymy na cały plik).
    """
    pary_z_pliku = parent.pary_z_pliku()
    stare = {}
    pary = set()
    for row in rows:
        stara_id = row.autor.aktualna_jednostka_id if row.autor_id else None
        stare[row.pk] = stara_id
        if wiersz_kwalifikuje_do_przepiecia(
            row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
        ):
            pary.add((row.autor_id, stara_id))
    liczby = {}
    jednostki_map = {}
    if pary:
        autor_ids = {a for a, _ in pary}
        jednostka_ids = {j for _, j in pary}
        for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
            agg = (
                model.objects.filter(
                    autor_id__in=autor_ids, jednostka_id__in=jednostka_ids
                )
                .values("autor_id", "jednostka_id")
                .annotate(n=Count("id"))
            )
            for w in agg:
                klucz = (w["autor_id"], w["jednostka_id"])
                liczby[klucz] = liczby.get(klucz, 0) + w["n"]
        jednostki_map = Jednostka.objects.in_bulk(jednostka_ids)
    for row in rows:
        stara_id = stare[row.pk]
        dostepne = (row.autor_id, stara_id) in pary
        row.przepnij_dostepne = dostepne
        row.przepnij_stara_jednostka = (
            jednostki_map.get(stara_id) if dostepne else None
        )
        row.przepnij_liczba_prac = liczby.get((row.autor_id, stara_id), 0)
    return rows
```

4. W `_WierszImportuMixin._render_wiersz` dołóż adnotację przed renderem:

```python
    def _render_wiersz(self):
        # Re-pobierz wiersz przez get_details_set(), żeby partial miał adnotacje
        # nr_arkusza/nr_wiersza (RawSQL) — inaczej te komórki byłyby puste po
        # swapie HTMX. Odzwierciedla zapisane właśnie zmiany.
        row = self.parent_object.get_details_set().get(pk=self.row.pk)
        oznacz_przepiecie_prac([row], self.parent_object)
        return render(
            self.request,
            self.partial_template,
            {"row": row, "parent_object": self.parent_object},
        )
```

5. Dodaj widok toggle (po `PrzelaczUtworzNowegoView`):

```python
class PrzepnijPraceView(_WierszImportuMixin):
    """POST (HTMX): przełącz flagę ``przepnij_prace`` wiersza (§10 D6/D7).

    Samo przepięcie prac wykona się dopiero w fazie commit (integracja).
    Owner/superuser-scoped + bramka stanu ``przeanalizowany`` — via
    ``_WierszImportuMixin``. F2/G2: odrzuca 400 TYLKO przy WŁĄCZANIU, gdy wiersz
    nie kwalifikuje się do przepięcia (autor/jednostka nieustawione,
    aktualna==jednostka, albo stara jednostka jest „parą z pliku”) — inaczej
    commit crashowałby na ``Jednostka.objects.get(pk=None)`` / przepinałby wbrew
    guardowi F1. ODZNACZANIE jest zawsze dozwolone: wiersz mógł przestać się
    kwalifikować po fakcie (inny wiersz rozstrzygnięto na starą jednostkę,
    rematch zmienił autora) i renderuje „—”, ale flagę-zombie w DB trzeba dać
    zdjąć. Warunek IDENTYCZNY z commit i bulk
    (``wiersz_kwalifikuje_do_przepiecia``). Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        nowa_wartosc = request.POST.get("przepnij_prace") is not None
        # G2: waliduj kwalifikację TYLKO przy włączaniu — odznaczanie musi
        # przejść nawet dla wiersza-zombie, który przestał się kwalifikować.
        if nowa_wartosc:
            pary_z_pliku = self.parent_object.pary_z_pliku()
            stara_id = (
                row.autor.aktualna_jednostka_id if row.autor_id else None
            )
            if not wiersz_kwalifikuje_do_przepiecia(
                row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
            ):
                return HttpResponseBadRequest(
                    "Wiersz nie kwalifikuje się do przepięcia prac."
                )
        row.przepnij_prace = nowa_wartosc
        row.save(update_fields=["przepnij_prace"])
        return self._render_wiersz()
```

6. Dodaj widok akcji zbiorczej (po `PrzepnijPraceView`):

```python
class ZaznaczWszystkiePrzepieciaView(_ImportPodgladMixin):
    """POST: zaznacz ``przepnij_prace`` dla WSZYSTKICH wierszy KWALIFIKUJĄCYCH
    się do przepięcia. Owner/superuser-scoped + bramka podglądu. Redirect na
    tabelę.

    F1: warunek kwalifikacji IDENTYCZNY z podglądem i commit
    (``wiersz_kwalifikuje_do_przepiecia`` z guardem „para z pliku”). Guardu
    „stara jednostka jest w pliku” nie da się wprost wyrazić jednym
    ``.exclude(F())``, więc zbieramy pary z pliku w Pythonie i aktualizujemy po
    ``pk__in`` liście kwalifikujących wierszy."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        parent = self.parent_object
        pary_z_pliku = parent.pary_z_pliku()
        kwalifikujace = []
        for row in parent.importpracownikowrow_set.filter(
            autor__isnull=False, jednostka__isnull=False
        ).select_related("autor"):
            stara_id = row.autor.aktualna_jednostka_id
            if wiersz_kwalifikuje_do_przepiecia(
                row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
            ):
                kwalifikujace.append(row.pk)
        n = parent.importpracownikowrow_set.filter(
            pk__in=kwalifikujace
        ).update(przepnij_prace=True)
        messages.success(
            request, f"Zaznaczono przepięcie prac dla {n} wierszy."
        )
        return HttpResponseRedirect(
            reverse(
                "import_pracownikow:importpracownikow-results",
                kwargs={"pk": parent.pk},
            )
        )
```

7. W `ImportPracownikowResultsView` — zmień `parent_object` na `cached_property`
   (import `cached_property` już jest na górze `views.py`; jak w
   `_ImportPodgladMixin`), żeby `get_queryset` + `get_context_data` w JEDNYM
   żądaniu nie robiły osobnych `get_object_or_404` (G4). Zamień dekorator:

```python
    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if (
            obj.owner_id != self.request.user.pk
            and not self.request.user.is_superuser
        ):
            raise Http404
        return obj
```

   oraz zaadnotuj stronę wyników — agregat przepięć liczymy TYLKO w podglądzie
   przed commitem (po integracji `przepnij_dostepne` jest zawsze `False`, więc
   dwa GROUP BY byłyby zmarnowaną pracą — G4):

```python
    def get_context_data(self, **kwargs):
        parent = self.parent_object
        odpiecia = parent.odpiecia.select_related(
            "autor_jednostka__autor",
            "autor_jednostka__autor__tytul",
            "autor_jednostka__jednostka",
        )
        ctx = super().get_context_data(
            parent_object=parent,
            odpiecia=odpiecia,
            **kwargs,
        )
        if parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY:
            oznacz_przepiecie_prac(list(ctx["object_list"]), parent)
        return ctx
```

8. **Reset ``przepnij_prace`` przy ZMIANIE ``row.autor`` (G2).** Opt-in
   przepięcia jest związany z KONKRETNYM autorem+jednostką; gdy user zmienia
   autora wiersza (wybór kandydata lub korekta imion/nazwiska), stary opt-in
   „przeniósłby się” na innego autora i przepiąłby cudze prace. Zeruj flagę w
   OBU miejscach ustawiających ``row.autor``:

   a) W `WybierzKandydataView.post`, tuż po `row.autor = autor`, dołóż
      `row.przepnij_prace = False` oraz dopisz `"przepnij_prace"` do listy
      `update_fields` przekazywanej do `row.save(...)`:

```python
        autor = kandydat.autor
        row.wybrany_kandydat = autor
        row.autor = autor
        row.confidence = STATUS_TWARDY
        # G2: zmiana autora unieważnia opt-in przepięcia poprzedniego autora.
        row.przepnij_prace = False
```

```python
        row.save(
            update_fields=[
                "wybrany_kandydat",
                "autor",
                "confidence",
                "autor_jednostka",
                "diff_do_utworzenia",
                "zmiany_potrzebne",
                "przepnij_prace",
            ]
        )
```

   b) W `_rematch_wiersz`, tuż po `row.autor = autor` (przed
      `row.wybrany_kandydat = None`), dołóż `row.przepnij_prace = False`.
      `_rematch_wiersz` kończy pełnym `row.save()` (bez `update_fields`), więc
      dodatkowa lista pól nie jest potrzebna:

```python
    row.confidence = status
    row.autor = autor
    # G2: zmiana autora unieważnia opt-in przepięcia poprzedniego autora.
    row.przepnij_prace = False
    row.wybrany_kandydat = None
```

### Step 5.4 — URL-e

W `src/import_pracownikow/urls.py`, dołóż do `urlpatterns`:

```python
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/przepnij-prace/",
        views.PrzepnijPraceView.as_view(),
        name="przepnij-prace",
    ),
    path(
        "<uuid:pk>/przepnij-prace/zaznacz-wszystkie/",
        views.ZaznaczWszystkiePrzepieciaView.as_view(),
        name="zaznacz-przepiecia",
    ),
```

### Step 5.5 — Kolumna w partialu i nagłówku

W `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
dodaj NOWĄ komórkę jako ostatnią (po `</td>` kolumny „Akcje / zmiany”, przed
`</tr>`):

```django
    <td>
        {% if parent_object.stan == "przeanalizowany" and row.przepnij_dostepne %}
            {# opt-in przepięcia prac — POST toggluje przepnij_prace #}
            <form method="post"
                  hx-post="{% url "import_pracownikow:przepnij-prace" pk=parent_object.pk row_pk=row.pk %}"
                  hx-target="#wiersz-{{ row.pk }}"
                  hx-swap="outerHTML"
                  hx-trigger="change">
                {% csrf_token %}
                <label>
                    <input type="checkbox" name="przepnij_prace"
                           {% if row.przepnij_prace %}checked{% endif %}>
                    <span class="fi-shuffle"></span>
                    z {{ row.przepnij_stara_jednostka.skrot }}
                    do {{ row.jednostka.skrot }}
                    ({{ row.przepnij_liczba_prac }} prac)
                </label>
            </form>
        {% elif row.log_zmian.przepiecie %}
            {# po integracji: audyt wykonanego przepięcia #}
            <span class="label success">
                <span class="fi-check"></span>
                przepięto {{ row.log_zmian.przepiecie.prace_ciagle }}+{{ row.log_zmian.przepiecie.prace_zwarte }}
            </span>
        {% else %}
            —
        {% endif %}
    </td>
```

W `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`:

1. Dodaj nagłówek kolumny po `<th>Akcje / zmiany</th>`:

```django
                        <th>Przepnij prace</th>
```

2. Zmień `colspan="8"` w wierszu „empty” na `colspan="9"`.

3. Nad tabelą (po `<script ... htmx ...>`, przed `{% if parent_object.finished_successfully %}`) dodaj przycisk akcji zbiorczej dla podglądu:

```django
    {% if parent_object.stan == "przeanalizowany" %}
        {# akcja zbiorcza: zaznacz przepięcie prac dla wierszy z różnicą jednostki #}
        <form method="post"
              action="{% url "import_pracownikow:zaznacz-przepiecia" pk=parent_object.pk %}">
            {% csrf_token %}
            <button type="submit" class="button small secondary">
                <span class="fi-shuffle"></span>
                Zaznacz przepięcie prac dla wszystkich z różnicą jednostki
            </button>
        </form>
    {% endif %}
```

### Step 5.6 — Run (PASS) + regresja renderów partiala

```bash
uv run pytest src/import_pracownikow/tests/test_views_przepiecie.py \
    src/import_pracownikow/tests/test_views_wiersz.py \
    src/import_pracownikow/tests/test_views_utworz_nowego.py \
    src/import_pracownikow/tests/test_views_preview_render.py -q
```

Oczekiwane: nowe 7 testów PASS; istniejące rendery partiala PASS (nowa kolumna
renderuje się także w swapach HTMX dzięki
`oznacz_przepiecie_prac([row], self.parent_object)`).

### Step 5.7 — Commit

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
    src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html \
    src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html \
    src/import_pracownikow/tests/test_views_przepiecie.py
git commit -m "feat(import-prac): UI podglądu przepięcia prac (kolumna, toggle, bulk)"
```

---

## Task 6 — UI cofania w `przemapuj_prace_autora`

**Files:**
- Modify: `src/przemapuj_prace_autora/views.py`
- Modify: `src/przemapuj_prace_autora/urls.py`
- Modify:
  `src/przemapuj_prace_autora/templates/przemapuj_prace_autora/przemapuj_prace.html`
- Create: `src/przemapuj_prace_autora/test_cofnij_view.py`

**Interfaces — Consumes:** `service.cofnij(przemapowanie)`,
`PrzemapoaniePracAutora`.
**Produces:** `cofnij_przemapowanie(request, pk)` (name
`cofnij_przemapowanie`), przycisk „Cofnij” w historii przemapowań.

### Step 6.1 — Failing test widoku cofania

Utwórz `src/przemapuj_prace_autora/test_cofnij_view.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from przemapuj_prace_autora import service
from przemapuj_prace_autora.models import PrzemapoaniePracAutora

User = get_user_model()


@pytest.fixture
def kl(db):
    User.objects.create_user(
        username="cof", password="pass", is_staff=True, is_superuser=True
    )
    c = Client()
    c.login(username="cof", password="pass")
    return c


@pytest.mark.django_db
def test_cofnij_view_przywraca_i_redirect(kl):
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    jz = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    jd = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jz
    )
    prz = service.przemapuj(autor, jz, jd, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jd.pk

    url = reverse(
        "przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk}
    )
    resp = kl.post(url)
    assert resp.status_code == 302
    pa.refresh_from_db()
    assert pa.jednostka_id == jz.pk
    # rekord audytu NIE skasowany
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()


@pytest.mark.django_db
def test_cofnij_view_odrzuca_get(kl):
    autor = baker.make(Autor)
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
    )
    url = reverse(
        "przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk}
    )
    resp = kl.get(url)
    assert resp.status_code == 405
```

### Step 6.2 — Run (FAIL)

```bash
uv run pytest src/przemapuj_prace_autora/test_cofnij_view.py -q
```

Oczekiwane: `NoReverseMatch` (brak URL `cofnij_przemapowanie`).

### Step 6.3 — Widok cofania

W `src/przemapuj_prace_autora/views.py`:

1. Rozszerz import z `django.http`:

```python
from django.http import HttpResponseNotAllowed
```

2. Dodaj widok (na końcu pliku):

```python
@login_required
def cofnij_przemapowanie(request, pk):
    """POST: cofnij przemapowanie (``service.cofnij``) i pokaż raport
    (cofnięto N, pominięto M z powodu późniejszych zmian). Redirect na widok
    przemapowania autora."""
    przemapowanie = get_object_or_404(PrzemapoaniePracAutora, pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cofnieto, pominieto = service.cofnij(przemapowanie)
    if pominieto:
        messages.warning(
            request,
            f"Cofnięto {cofnieto} przypisań prac; pominięto {pominieto} "
            "z powodu późniejszych zmian afiliacji.",
        )
    else:
        messages.success(request, f"Cofnięto {cofnieto} przypisań prac.")
    return redirect(
        "przemapuj_prace_autora:przemapuj_prace",
        autor_id=przemapowanie.autor_id,
    )
```

### Step 6.4 — URL

W `src/przemapuj_prace_autora/urls.py`, dołóż do `urlpatterns`:

```python
    path(
        "przemapowanie/<int:pk>/cofnij/",
        views.cofnij_przemapowanie,
        name="cofnij_przemapowanie",
    ),
```

### Step 6.5 — Przycisk „Cofnij” w historii

W `src/przemapuj_prace_autora/templates/przemapuj_prace_autora/przemapuj_prace.html`,
w tabeli „Historia przemapowań”:

1. Dodaj nagłówek po `<th>Szczegóły</th>`:

```django
                            <th>Cofnij</th>
```

2. Dodaj komórkę po komórce „Szczegóły” (po `</td>` z linkiem do admina), przed
   `</tr>`:

```django
                            <td>
                                <form method="post"
                                      action="{% url 'przemapuj_prace_autora:cofnij_przemapowanie' log.pk %}"
                                      onsubmit="return confirm('Cofnąć to przemapowanie prac?');">
                                    {% csrf_token %}
                                    <button type="submit" class="button tiny alert"
                                            title="Cofnij to przemapowanie">
                                        <span class="fi-loop"></span> Cofnij
                                    </button>
                                </form>
                            </td>
```

### Step 6.6 — Run (PASS) + regresja przemapuj

```bash
uv run pytest src/przemapuj_prace_autora/ -q
```

Oczekiwane: nowe 2 testy PASS; cała reszta pakietu (`test_history`,
`test_characterization_view`, `test_integration`, `test_service`,
`test_button_layout`, `test_improvements`) PASS.

### Step 6.7 — Commit

```bash
git add src/przemapuj_prace_autora/views.py \
    src/przemapuj_prace_autora/urls.py \
    src/przemapuj_prace_autora/templates/przemapuj_prace_autora/przemapuj_prace.html \
    src/przemapuj_prace_autora/test_cofnij_view.py
git commit -m "feat(przemapuj): widok + przycisk cofania przemapowania prac"
```

---

## Task 7 — E2E (commit → przepięte → cofnij → przywrócone) + newsfragment

**Files:**
- Create: `src/import_pracownikow/tests/test_pipeline/test_faza5_e2e.py`
- Create: `src/bpp/newsfragments/import-pracownikow-przepiecie-prac.feature.rst`

**Interfaces — Consumes:** `integruj`, `service.cofnij` (przez widok),
`PrzemapoaniePracAutora`, endpoint `cofnij_przemapowanie`.

### Step 7.1 — Failing e2e

Utwórz `src/import_pracownikow/tests/test_pipeline/test_faza5_e2e.py`:

```python
"""E2E Fazy 5: przepięcie prac w commit + cofnięcie przez widok."""

import pytest
from django.urls import reverse
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.mark.django_db
def test_e2e_przepiecie_i_cofniecie(admin_client, admin_user):
    stara = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == stara.pk

    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara
    )
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(
        Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=stara
    )

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    # commit → przepięcie
    integruj(imp, MockProgress(imp))
    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == nowa.pk
    assert pz.jednostka_id == nowa.pk
    prz = PrzemapoaniePracAutora.objects.get(zrodlowy_import=imp)

    # cofnięcie przez widok
    url = reverse(
        "przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk}
    )
    resp = admin_client.post(url)
    assert resp.status_code == 302

    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == stara.pk
    assert pz.jednostka_id == stara.pk
    # audyt przetrwał
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()
```

### Step 7.2 — Run (PASS oczekiwany, bo funkcje już istnieją)

```bash
uv run pytest \
    src/import_pracownikow/tests/test_pipeline/test_faza5_e2e.py -q
```

Oczekiwane: PASS (Task 4 + Task 6 dostarczyły potrzebną logikę). Jeśli FAIL —
diagnozuj wg `systematic-debugging`, nie obchodź.

### Step 7.3 — Newsfragment

Utwórz `src/bpp/newsfragments/import-pracownikow-przepiecie-prac.feature.rst`:

```rst
Import pracowników potrafi teraz przepiąć prace autora ze starej jednostki na
jednostkę z pliku: w podglądzie pojawia się kolumna „Przepnij prace” z checkboxem
(oraz akcja zbiorcza dla wszystkich wierszy z różnicą jednostki), a samo
przepięcie wykonuje się dopiero w fazie zapisu do bazy. Każde przepięcie jest
rejestrowane jako powiązane z importem i można je cofnąć z widoku „Przemapowanie
prac autora” — z raportem, ile przypisań przywrócono, a ile pominięto z powodu
późniejszych zmian afiliacji.
```

### Step 7.4 — Pełny przebieg pakietów Fazy 5 + pre-commit

```bash
uv run pytest src/import_pracownikow/tests/ \
    src/przemapuj_prace_autora/ -q
pre-commit run --files \
    src/import_pracownikow/models.py \
    src/import_pracownikow/views.py \
    src/import_pracownikow/urls.py \
    src/import_pracownikow/pipeline/integrate.py \
    src/przemapuj_prace_autora/service.py \
    src/przemapuj_prace_autora/views.py \
    src/przemapuj_prace_autora/urls.py \
    src/przemapuj_prace_autora/models.py
```

Ręcznie sprawdź linie >88 znaków w kodzie Pythona:

```bash
awk 'length>88{print FILENAME":"FNR": "length}' \
    src/przemapuj_prace_autora/service.py \
    src/przemapuj_prace_autora/views.py \
    src/import_pracownikow/views.py \
    src/import_pracownikow/pipeline/integrate.py
```

Oczekiwane: wszystkie testy PASS; pre-commit czysty; `awk` bez wyniku.

### Step 7.5 — Commit

```bash
git add src/import_pracownikow/tests/test_pipeline/test_faza5_e2e.py \
    src/bpp/newsfragments/import-pracownikow-przepiecie-prac.feature.rst
git commit -m "test(import-prac): e2e przepięcia+cofnięcia + newsfragment (Faza 5)"
```

---

## Nota końcowa — baseline

Migracje 0015 (import_pracownikow) i 0003 (przemapuj_prace_autora) zmieniają
schemat, ale **NIE** odświeżaj `make baseline-update` na tej gałęzi — baseline
odświeżamy JEDEN raz przy scaleniu wszystkich faz importu (równoległe odświeżanie
w feature-branchach daje nierozwiązywalny konflikt na jednym wielkim pliku
`baseline-sql/baseline.sql`). Zaznacz to w opisie PR.

---

## Self-review

### Pokrycie §10 punkt po punkcie

- „Ekstrakcja logiki → service.py: `przemapuj(...)` bez request/messages” —
  Task 2 (Step 2.3), sygnatura + refaktor widoku (Step 2.5). ✅
- „Zakres D7: tylko prace ze starej jednostki, wszystkie niezależnie od roku” —
  `filter(autor=, jednostka=jednostka_z).update(jednostka=jednostka_do)` w
  serwisie; test `test_przemapuj_przenosi_tylko_prace_ze_starej_jednostki`. ✅
- „UI: kolumna „przepnij prace: ☐ z ⟨stara⟩ do ⟨nowa⟩ (N prac)” tylko gdy
  jednostka z pliku ≠ dotychczasowa; opt-in per-wiersz + akcja zbiorcza” —
  Task 5 (partial + `PrzepnijPraceView` + `ZaznaczWszystkiePrzepieciaView`);
  test widoczności kolumny + bulk. ✅
- „N liczone agregatem przy budowie preview” — `oznacz_przepiecie_prac` (dwa
  `values().annotate(Count)`); Assumption 4. ✅
- „Wykonanie w commit, po `row.integrate()`; wynik do `log_zmian`” —
  `_wykonaj_przepiecia` (per-wiersz `transaction.atomic`,
  `log_zmian["przepiecie"]`); wołane po pętli integracji + `_wykonaj_odpiecia`.
  ⚠️ ODSTĘPSTWO od litery „w transakcji wiersza” — przepięcia biegną w OSOBNEJ
  pętli po całej integracji (każde w własnym `transaction.atomic`), bo poprawny
  snapshot starej jednostki wymaga odczytu PRZED pętlą integracji i wykonania
  PO niej (trigger DB przestawia `aktualna_jednostka`, patrz Assumption 2/11).
  Świadome, udokumentowane (Assumption 11).
- „Cofanie D6 z ograniczeniami; wpisy historii rozszerzone o
  `{autor_rekord_pk, jednostka_z_pk, ...}` + nullable FK do importu” — Task 2
  enrichment (`zrodlowy_import`), Task 3 `cofnij` z guardem; test guarda. ✅
- „Algorytm undo: przywróć tylko gdy bieżąca `jednostka == jednostka_do`;
  niepasujące → pomiń i zaraportuj; `transaction.atomic`” — `cofnij` Step 3.3;
  testy guard/idempotencja/brak-pk. ✅
- „Przycisk „cofnij” z raportem (cofnięto N, pominięto M)” — Task 6 widok +
  `messages` + przycisk. ✅
- „Autor z wieloma starymi jednostkami: v1 przepina tylko z jednostki, którą
  import zmienia w tym wierszu” — snapshot po `aktualna_jednostka` + guard
  `stara_id == row.jednostka_id`; Assumption 5. ✅

### Skan placeholderów

Każdy step z kodem zawiera pełny kod (test + implementacja). Brak „TODO”,
„add appropriate…”, „similar to Task N”, „handle edge cases” bez kodu.
Sprawdź przed startem: `grep -nE 'TODO|FIXME|add appropriate|similar to Task' \
docs/superpowers/plans/2026-07-09-import-pracownikow-faza-5-przepiecie.md` →
wyniki tylko w tej linii self-review (self-referencyjnie). ✅

### Spójność typów/sygnatur

- `service.przemapuj(autor, jednostka_z, jednostka_do, user,
  zrodlowy_import=None) -> PrzemapoaniePracAutora` — identyczna w Task 2 (def),
  Task 2.5 (widok, `zrodlowy_import` domyślne), Task 4 (`_wykonaj_przepiecia`
  przekazuje instancje `Jednostka` + `zrodlowy_import=parent`). ✅
- `service.cofnij(przemapowanie) -> (cofnieto, pominieto)` (krotka) — Task 3
  def, Task 6 widok rozpakowuje `cofnieto, pominieto`, testy asertują krotkę.
  Assumption 7. ✅
- `_wykonaj_przepiecia(parent, stare_jednostki, user, p) -> (przepieto_wierszy,
  przepieto_prac)` — Task 4 def + wołanie w `integruj` (`parent.owner`, `p` dla
  śladu F5). Klucze result `przepieto_wierszy`/`przepieto_prac` spójne z
  testami. ✅
- `oznacz_przepiecie_prac(rows, parent)` — ustawia `przepnij_dostepne`,
  `przepnij_stara_jednostka`, `przepnij_liczba_prac`; użyte w partialu i w
  `_render_wiersz`/`get_context_data` (oba przekazują `self.parent_object`). ✅
- `ImportPracownikow.pary_z_pliku() -> set[(autor_id, jednostka_id)]` oraz
  `wiersz_kwalifikuje_do_przepiecia(autor_id, stara_id, jednostka_id,
  pary_z_pliku) -> bool` (models.py, Task 4) — JEDEN warunek kwalifikacji
  używany identycznie w commit (`_wykonaj_przepiecia`), preview
  (`oznacz_przepiecie_prac`), toggle (`PrzepnijPraceView`, walidacja 400) i bulk
  (`ZaznaczWszystkiePrzepieciaView`). Gwarant „identyczny zbiór wszędzie”
  (F1/F2/F3). ✅
- Wpisy historii: klucze `id/tytul/rok/zrodlo|isbn|wydawnictwo` (czytane przez
  admin.py i test_history) ZACHOWANE; dodane `autor_rekord_pk`,
  `jednostka_z_pk` (czytane przez `cofnij`). ✅

### Skan ASCII-" w polskich stringach

- Komunikat sukcesu w `_wykonaj_przemapowanie` używa delimitera apostrofowego
  (`f'...'`) z ASCII `"` wokół nazw jednostek — bezpieczne (nie zamyka
  literału), zgodne z oryginałem. ✅
- Wszystkie inne literały z polskimi cudzysłowami używają U+201E „ + U+201D ”:
  docstring `oznacz_przepiecie_prac` („Przepnij prace”), `PrzepnijPraceView`,
  komunikaty `messages` (bez „…” — czysty tekst), newsfragment („Przepnij
  prace”, „Przemapowanie prac autora”). Żaden literał double-quote-delimited nie
  zawiera surowego U+201E bez domknięcia U+201D. ✅
- Django `{# … #}` komentarze w partialu/liście — każdy jednoliniowy,
  domknięty w tej samej linii. ✅
- Ikony: `fi-shuffle`, `fi-check`, `fi-loop` (Foundation-Icons `<span>`), nie
  emoji. ✅
