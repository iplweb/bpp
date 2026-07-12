# Import: słowniki stopień/stanowisko — Plan 4: e-mail (hardening) + porównywarka + E2E

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Domknięcie feature'u słowników stopień/stanowisko + e-mail: (1) łagodna
walidacja e-maila — niepoprawny adres NIE wywala całej analizy, tylko czyści pole
i zapisuje ostrzeżenie; (2) porównywarka „plik vs baza" (e-mail / stopień służbowy
/ stanowisko dydaktyczne) w tabeli podglądu — różnica PODŚWIETLONA (e-mail
read-only/no-overwrite, stopień/stanowisko overwrite-if-different w integracji);
(3) test E2E spinający komórkę złożoną → utworzenie jednostek
(Krok 1) → import osób ze stopniem/stanowiskiem/e-mailem (Krok 2); (4) newsfragment
podsumowujący cały feature.

**Architecture:** E-mail czyszczony CZYSTĄ funkcją (`oczysc_email` w
`parsers/wartosci.py`) PRZED `AutorForm.full_clean()` — dzięki temu zły adres nigdy
nie unieważnia formularza (analiza jest fail-fast, jeden `XLSParseError` ubija cały
run). Ostrzeżenie trafia do `row.dane_znormalizowane["ostrzeżenia"]` (obok danych
autora, tam gdzie audyt i porównywarka je odczytają). Porównywarka to CZYSTY
odczyt: metoda modelu `ImportPracownikowRow.porownaj_z_baza()` liczy trójki
`{plik, baza, rozne}` z `dane_znormalizowane` (strona pliku) i FK autora / AJ
(strona bazy); szablon renderuje trzy nowe kolumny z podświetleniem różnicy
(Foundation `label warning`). Bez N+1 — `get_details_set()` dostaje dwa nowe
`select_related`.
E2E to test pipeline'owy (analyze → integrate struktury → integrate osób) na
syntetycznych wierszach karmionych przez `patch(otworz_zrodlo)` — wzorzec
`test_e2e_jednostki.py`; słowniki seedowane `baker`iem (baseline testcontainers NIE
zawiera struktur APOŻ). Izolację pętli asyncio pod xdist zapewnia autouse-fixture
z `tests/conftest.py` (obejmuje też `tests/test_pipeline/`).

**Tech Stack:** Django, PostgreSQL, pytest + `model_bakery`, pytest-testcontainers,
`django.core.validators.validate_email`.

**Spec:** `docs/superpowers/specs/2026-07-12-import-slowniki-stopnie-stanowiska-design.md`
(§11 e-mail, §12 porównywarka, §14 testy/E2E, §16 poza zakresem).

**Zależność:** `Autor.email` (`EmailField max_length=128`) JUŻ istnieje na `dev`
(`src/bpp/models/autor.py:185`) — Plan 4 go nie dodaje. Wymaga Planu 1 (pola
`Autor.stopien_sluzbowy`, `Autor_Jednostka.stanowisko`, modele
`StopienSluzbowy`/`StanowiskoDydaktyczne`), Planu 2 (klasyfikatory +
`parsuj_komorke` + cele mapowania `email`/`stopień_służbowy`/
`stanowisko_dydaktyczne`/`komórka_złożona`/`nazwisko_imię`) oraz Planu 3 (wpięcie
parsera komórki, klasyfikatorów i e-maila/stopnia/stanowiska w
`analyze`/`integrate`, dodanie `email` do `AutorForm`, dodanie FK `stopien` i
`stanowisko_dydaktyczne` na `ImportPracownikowRow`). Zmiana etykiety/help_text
`ZAKRES_STRUKTURA` oraz przycisku hubu jest realizowana w Planie 3 (razem z migracją
modeli `import_pracownikow`). Task 4 (E2E) jest testem akceptacyjnym CAŁEGO
feature'u — przechodzi dopiero po ukończeniu Planów 1–3.

## Global Constraints

- **ZAWSZE `uv run`** przed komendami Python. Max linia **88 znaków** (ruff).
- Testy: pytest, `@pytest.mark.django_db` gdzie DB, `baker.make`, funkcje (bez
  klas). Docker dla testcontainers (OrbStack:
  `export DOCKER_HOST=unix:///Users/mpasternak/.orbstack/run/docker.sock`).
- **NIE modyfikować WYDANYCH migracji.** Świeże migracje na `dev` (niewydane) można
  edytować. Plan 4 nie generuje własnej migracji — migracja modeli
  `import_pracownikow` (w tym `AlterField` zakresu) powstaje w Planie 3.
- **E-mail no-overwrite dla istniejących:** import USTAWIA `Autor.email` tylko dla
  NOWO tworzonego autora; istniejącego NIGDY nie nadpisuje (logika w `integrate` z
  Planu 3 — tu tylko testujemy i pokazujemy różnicę). No-overwrite dotyczy
  WYŁĄCZNIE e-maila — stopień służbowy i stanowisko dydaktyczne to
  overwrite-if-different (Plan 3). Porównywarka jest read-only.
- **Nazwy (kontrakt spójny z Planami 1–3):** `Autor.email`,
  `Autor.stopien_sluzbowy` (FK `StopienSluzbowy`), `Autor_Jednostka.stanowisko`
  (FK `StanowiskoDydaktyczne`), `parsuj_komorke`. Klucze w `dane_znormalizowane`
  (strona pliku): `email`, `stopień_służbowy`, `stanowisko_dydaktyczne`.
- **Django `{# #}` jest jedno-liniowy** — każda linia własne `{# … #}`.
- **Ikony:** ten szablon rozszerza `base.html` (Foundation) → Foundation-Icons /
  klasy Foundation (`label warning`, `secondary`), NIE emoji.
- Branch: `feat/import-pracownikow-slowniki-stopnie-stanowiska` (ten sam co Plany
  1–3 — Plan 4 domyka serię).

## File Structure (Plan 4)

- Modify: `src/import_pracownikow/parsers/wartosci.py` — `oczysc_email`.
- Modify: `src/import_pracownikow/pipeline/analyze.py` — wpięcie `oczysc_email` +
  ostrzeżenie do `dane_znormalizowane`.
- Modify: `src/import_pracownikow/models.py` — `ImportPracownikowRow.porownaj_z_baza`
  (+ `ostrzezenie_email`), `select_related` w `get_details_set`.
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  — 3 nowe nagłówki + colspan + `columnDefs`.
- Modify: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html`
  — 3 nowe komórki porównania.
- Create: `src/import_pracownikow/templates/import_pracownikow/partials/_porownanie_kom.html`
  — wspólny render jednej komórki porównania (trójka `{plik, baza, rozne}` +
  ostrzeżenie e-maila).
- Testy: `src/import_pracownikow/tests/test_parsers/test_oczysc_email.py`,
  `src/import_pracownikow/tests/test_pipeline/test_analyze_email.py`,
  `src/import_pracownikow/tests/test_porownywarka.py`,
  `src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py`.
- Modify: `src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst`
  — uzupełnij fragment utworzony w Planie 1 o e-mail/porównywarkę (Plan 1 już go
  tworzy; NIE twórz drugiego).

---

## Task 1: `oczysc_email` — łagodna walidacja e-maila (czysta funkcja)

**Files:**
- Test: `src/import_pracownikow/tests/test_parsers/test_oczysc_email.py` (create)
- Modify: `src/import_pracownikow/parsers/wartosci.py`

**Interfaces:**
- Consumes: `django.core.validators.validate_email`.
- Produces: `oczysc_email(dane: dict) -> str | None` — mutuje `dane["email"]` na
  poprawny, znormalizowany (lower/strip) adres albo `""`; zwraca komunikat
  ostrzeżenia (gdy adres był niepusty i niepoprawny — w tym > 128 znaków) albo
  `None`. Czysta funkcja (bez ORM), nie rzuca.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_parsers/test_oczysc_email.py`:

```python
from import_pracownikow.parsers.wartosci import oczysc_email


def test_poprawny_email_przechodzi_i_normalizuje():
    dane = {"email": "  Jan.Kowalski@Example.COM "}
    ostrz = oczysc_email(dane)
    assert dane["email"] == "jan.kowalski@example.com"
    assert ostrz is None


def test_niepoprawny_email_czyszczony_i_ostrzega():
    dane = {"email": "to-nie-jest-email"}
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None
    assert "e-mail" in ostrz.lower()
    assert "to-nie-jest-email" in ostrz


def test_pusty_email_bez_ostrzezenia():
    dane = {"email": ""}
    assert oczysc_email(dane) is None
    assert dane["email"] == ""


def test_brak_klucza_no_op():
    dane = {"nazwisko": "Kowalski"}
    assert oczysc_email(dane) is None
    assert "email" not in dane


def test_wartosc_nietekstowa_nie_wywala():
    # openpyxl potrafi dać komórkę liczbową — str() + walidacja, bez wyjątku
    dane = {"email": 12345}
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None


def test_zbyt_dlugi_email_odrzucony():
    # Autor.email = EmailField(max_length=128) — dłuższy adres odrzucamy, żeby
    # nie wywalić Autor.objects.create
    dane = {"email": "a" * 120 + "@example.com"}  # 132 znaki
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None
    assert "e-mail" in ostrz.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_oczysc_email.py -v`
Expected: FAIL — `ImportError: cannot import name 'oczysc_email'`.

- [ ] **Step 3: Write implementation**

Dodaj na końcu `src/import_pracownikow/parsers/wartosci.py` (oraz import na górze):

```python
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
```

```python
def oczysc_email(dane: dict):
    """Łagodna walidacja e-maila (§11): mutuje ``dane["email"]`` na poprawny,
    znormalizowany adres (lower + strip) albo ``""``; zwraca komunikat
    ostrzeżenia (gdy adres był NIEPUSTY i niepoprawny) albo ``None``.

    Wołane PRZED ``AutorForm.full_clean()`` w analizie — dzięki temu zły adres
    NIGDY nie unieważnia formularza (analiza jest fail-fast: jeden
    ``XLSParseError`` z ``full_clean`` ubija cały run). ``str(...)`` bo XLSX
    (openpyxl) potrafi dać komórkę nietekstową. Adres > 128 znaków traktujemy
    jak niepoprawny (model ``Autor.email`` = ``EmailField(max_length=128)`` —
    dłuższy wywaliłby ``Autor.objects.create``). Nie rzuca (per-wiersz
    recovery)."""
    if "email" not in dane:
        return None
    surowy = str(dane.get("email") or "").strip()
    if not surowy:
        dane["email"] = ""
        return None
    kandydat = surowy.lower()
    if len(kandydat) > 128:
        dane["email"] = ""
        return "Pominięto zbyt długi adres e-mail (>128 znaków)."
    try:
        validate_email(kandydat)
    except ValidationError:
        dane["email"] = ""
        return f"Pominięto niepoprawny adres e-mail: „{surowy}”."
    dane["email"] = kandydat
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_oczysc_email.py -v`
Expected: PASS (6 testów).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/wartosci.py \
  src/import_pracownikow/tests/test_parsers/test_oczysc_email.py
git commit -m "feat(import_pracownikow): oczysc_email — łagodna walidacja e-maila"
```

---

## Task 2: Wpięcie `oczysc_email` w `analyze._przetworz_wiersz`

**Files:**
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_email.py` (create)
- Modify: `src/import_pracownikow/pipeline/analyze.py`

**Interfaces:**
- Consumes: `oczysc_email` (Task 1); istniejący `_dane_znormalizowane_z_parserem`,
  `AutorForm`, `analizuj`, `remapuj_wiersz`.
- Produces: niepoprawny e-mail w wierszu → wiersz przetworzony BEZ wyjątku;
  `row.dane_znormalizowane["email"] == ""` oraz komunikat w
  `row.dane_znormalizowane["ostrzeżenia"]` (lista). Poprawny e-mail →
  znormalizowany w `dane_znormalizowane`, brak klucza `ostrzeżenia`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_pipeline/test_analyze_email.py`:

```python
from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


def _imp():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    return imp


def _analizuj_z_wierszem(imp, wiersz):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))  # NIE rzuca


@pytest.mark.django_db
def test_niepoprawny_email_nie_wywala_analizy_i_ostrzega(uczelnia):
    imp = _imp()
    _analizuj_z_wierszem(
        imp,
        {
            "imię": "Jan",
            "nazwisko": "Kowalski",
            "nazwa_jednostki": "Zakład Testowy",
            "email": "nie-email",
            "__xls_loc_sheet__": 0,
            "__xls_loc_row__": 1,
        },
    )
    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane.get("email") == ""
    ostrzezenia = row.dane_znormalizowane.get("ostrzeżenia") or []
    assert any("e-mail" in o.lower() for o in ostrzezenia)


@pytest.mark.django_db
def test_poprawny_email_normalizowany_bez_ostrzezenia(uczelnia):
    imp = _imp()
    _analizuj_z_wierszem(
        imp,
        {
            "imię": "Anna",
            "nazwisko": "Nowak",
            "nazwa_jednostki": "Zakład Testowy",
            "email": "  Anna.Nowak@EXAMPLE.com ",
            "__xls_loc_sheet__": 0,
            "__xls_loc_row__": 2,
        },
    )
    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane.get("email") == "anna.nowak@example.com"
    assert "ostrzeżenia" not in row.dane_znormalizowane
```

Uwaga: `AutorForm` (po Planie 3) musi mieć pole `email = forms.EmailField(
required=False)` (albo CharField). Jeśli go NIE ma, `email` nie znajdzie się w
`cleaned_data` i test poprawnego adresu padnie — to sygnał braku Planu 3, nie
regresja Planu 4.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_email.py -v`
Expected: FAIL — brak czyszczenia (`email` nie znormalizowany / brak `ostrzeżenia`),
albo `XLSParseError` przy złym adresie.

- [ ] **Step 3: Write implementation**

W `src/import_pracownikow/pipeline/analyze.py` dodaj `oczysc_email` do istniejącego
importu z `parsers.wartosci` (linie 57–60):

```python
from import_pracownikow.parsers.wartosci import (
    normalizuj_wartosci_wiersza,
    oczysc_email,
    rozbij_nazwisko_imie,
    sklej_drugie_imie,
)
```

Uwaga: `rozbij_nazwisko_imie` dodaje do TEGO SAMEGO importu już Plan 3 (Task 3).
Zachowaj je tutaj — verbatim-kopia bez tej pozycji nadpisałaby import Planu 3 i
dałaby `NameError` przy wołaniu `rozbij_nazwisko_imie` w `_przetworz_wiersz`.

W `_przetworz_wiersz`, tuż po `dane_form = normalizuj_wartosci_wiersza(elem)`
(przed `_rozbij_osoba_sklejona` / `AutorForm`), zbierz ostrzeżenia i wyczyść e-mail:

```python
    dane_form = normalizuj_wartosci_wiersza(elem)
    ostrzezenia = []
    ostrz_email = oczysc_email(dane_form)
    if ostrz_email:
        ostrzezenia.append(ostrz_email)
    rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)
```

Następnie w tym samym `_przetworz_wiersz` znajdź konstrukcję `ImportPracownikowRow(
... dane_znormalizowane=_dane_znormalizowane_z_parserem(autor_form.cleaned_data,
rozbicie), ...)`. Wyodrębnij ją do zmiennej i dołóż ostrzeżenia PRZED `Row(...)`:

```python
    dane_znorm = _dane_znormalizowane_z_parserem(
        autor_form.cleaned_data, rozbicie
    )
    if ostrzezenia:
        dane_znorm["ostrzeżenia"] = ostrzezenia
```

i w `ImportPracownikowRow(...)` zmień argument na `dane_znormalizowane=dane_znorm`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_email.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Regresja analizy (bez niespodzianek)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze.py src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py -q`
Expected: PASS (istniejąca analiza bez regresji).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_email.py
git commit -m "feat(import_pracownikow): zły e-mail nie wywala analizy (ostrzeżenie w wierszu)"
```

---

## Task 3: Porównywarka „plik vs baza" (e-mail / stopień / stanowisko)

**Files:**
- Test: `src/import_pracownikow/tests/test_porownywarka.py` (create)
- Modify: `src/import_pracownikow/models.py`
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html`

**Interfaces:**
- Consumes: `row.dane_znormalizowane` (klucze `email`/`stopień_służbowy`/
  `stanowisko_dydaktyczne` — wartości pliku do wyświetlenia), `row.autor.email`,
  `row.autor.stopien_sluzbowy_id`, `row.autor_jednostka.stanowisko_id` (strona
  bazy) oraz FK rozwiązane z pliku przez Plan 3: `row.stopien_id`,
  `row.stanowisko_dydaktyczne_id` (porównanie SEMANTYCZNE).
- Produces: `ImportPracownikowRow.porownaj_z_baza() -> dict` z kluczami
  `email`/`stopien`/`stanowisko`, każdy = `{"plik": str, "baza": str,
  "rozne": bool}`; `ImportPracownikowRow.ostrzezenie_email` (komunikat o
  odrzuconym adresie albo `None`); dwa nowe `select_related` w `get_details_set`;
  trzy kolumny w tabeli podglądu (nagłówki + komórki) z podświetleniem różnicy i
  ostrzeżeniem o odrzuconym e-mailu.

- [ ] **Step 1: Write the failing test (model helper)**

Create `src/import_pracownikow/tests/test_porownywarka.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_TWARDY


@pytest.mark.django_db
def test_porownaj_z_baza_wykrywa_roznice_emaila():
    # Stopień/stanowisko porównujemy SEMANTYCZNIE po FK (skrót w pliku „kpt." vs
    # nazwa w bazie „kapitan" dałyby fałszywe „różne"). Plan 3 rozwiązuje wartość
    # z pliku do FK na wierszu: row.stopien / row.stanowisko_dydaktyczne.
    stopien = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    stanow_prof = baker.make(
        "bpp.StanowiskoDydaktyczne", nazwa="profesor", skrot="prof."
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(
        Autor,
        nazwisko="Kowalski",
        imiona="Jan",
        email="stary@example.com",
        stopien_sluzbowy=stopien,
    )
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka,
                    stanowisko=stanow)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        stopien=stopien,  # plik → ten sam FK co w bazie (kpt.)
        stanowisko_dydaktyczne=stanow_prof,  # plik → inny FK niż baza (ad.)
        dane_znormalizowane={
            "email": "nowy@example.com",        # różni się od bazy
            "stopień_służbowy": "kpt.",         # zgodny skrótem (ten sam FK)
            "stanowisko_dydaktyczne": "prof.",  # różni się (inny FK)
        },
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["email"] == {
        "plik": "nowy@example.com",
        "baza": "stary@example.com",
        "rozne": True,
    }
    # zgodny stopień podany skrótem NIE daje różnicy (ten sam FK):
    assert wynik["stopien"]["rozne"] is False
    assert wynik["stanowisko"]["rozne"] is True
    assert wynik["stanowisko"]["plik"] == "prof."


@pytest.mark.django_db
def test_porownaj_z_baza_bez_autora_daje_puste_baza():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        confidence="brak",
        zmiany_potrzebne=False,
        dane_znormalizowane={"email": "x@example.com"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 2},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["email"] == {"plik": "x@example.com", "baza": "", "rozne": False}


@pytest.mark.django_db
def test_tabela_podgladu_renderuje_kolumny_porownania(admin_client, admin_user):
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan",
                       email="baza@example.com")
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka,
                    stanowisko=stanow)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
        finished_successfully=True,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={
            "email": "plik@example.com",
            "stanowisko_dydaktyczne": "adiunkt",
        },
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    url = reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )
    tresc = admin_client.get(url).content.decode("utf-8")
    # nagłówki nowych kolumn
    assert "E-mail (plik → baza)" in tresc
    assert "Stopień służbowy" in tresc
    assert "Stanowisko dydaktyczne" in tresc
    # różnica e-maila podświetlona + obie wartości widoczne
    assert "import-porownanie-rozne" in tresc
    assert "plik@example.com" in tresc
    assert "baza@example.com" in tresc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka.py -v`
Expected: FAIL — brak `porownaj_z_baza` / brak kolumn w szablonie.

- [ ] **Step 3: Dodaj `porownaj_z_baza` do `ImportPracownikowRow`**

W `src/import_pracownikow/models.py`, w klasie `ImportPracownikowRow` (np. po
`confidence_badge`), dodaj:

```python
    @staticmethod
    def _porownaj_email(plik, baza):
        """Trójka porównania e-maila: ``{plik, baza, rozne}``. ``rozne`` = obie
        strony NIEPUSTE i różne (case-insensitive) — pole puste w pliku LUB w
        bazie NIE jest różnicą (e-mail to no-overwrite: import nie nadpisuje
        istniejącego). Pustej bazy nie podświetlamy, ale import i tak jej NIE
        uzupełnia — e-mail trafia do bazy WYŁĄCZNIE przy tworzeniu nowego autora
        (``Autor.objects.create``); ``MAPPING_DANE_NA_AUTOR`` nie zawiera
        ``email``, więc istniejący autor z pustym e-mailem tak czy inaczej go nie
        dostaje z tego importu."""
        p = str(plik or "").strip()
        b = str(baza or "").strip()
        rozne = bool(p) and bool(b) and p.casefold() != b.casefold()
        return {"plik": p, "baza": b, "rozne": rozne}

    @staticmethod
    def _porownaj_fk(plik_str, baza_obj, plik_id):
        """Trójka porównania pola FK (stopień/stanowisko): ``{plik, baza,
        rozne}``. Porównanie SEMANTYCZNE po ID — skrót w pliku vs nazwa w bazie
        NIE może decydować o różnicy. ``rozne`` = plik WSKAZUJE FK (``plik_id``
        ustawione) i baza ma inny (lub żaden) FK — overwrite-if-different
        (Plan 3), inaczej niż no-overwrite e-maila. ``plik`` = wartość z pliku
        (skrót); ``baza`` = ``str`` FK z bazy."""
        baza_id = baza_obj.pk if baza_obj else None
        return {
            "plik": str(plik_str or "").strip(),
            "baza": str(baza_obj) if baza_obj else "",
            "rozne": plik_id is not None and baza_id != plik_id,
        }

    def porownaj_z_baza(self):
        """Porównanie „plik vs baza" dla e-maila, stopnia służbowego i
        stanowiska dydaktycznego (§12). CZYSTY odczyt — NIC nie zapisuje ani nie
        nadpisuje. E-mail: no-overwrite (porównanie stringów). Stopień/stanowisko:
        overwrite-if-different, porównywane SEMANTYCZNIE po FK (skrót w pliku vs
        nazwa w bazie dałyby fałszywe „różne"); FK z pliku rozwiązuje Plan 3 na
        ``self.stopien`` / ``self.stanowisko_dydaktyczne``. Strona bazy: FK autora
        / powiązania; stanowisko z ``autor_jednostka`` (aktualizowanego przez ten
        wiersz). Dla wiersza bez autora/AJ strona bazy jest pusta."""
        dane = self.dane_znormalizowane or {}
        autor = self.autor
        aj = self.autor_jednostka
        stopien_baza = (
            autor.stopien_sluzbowy
            if autor and autor.stopien_sluzbowy_id
            else None
        )
        stanowisko_baza = aj.stanowisko if aj and aj.stanowisko_id else None
        return {
            "email": self._porownaj_email(
                dane.get("email"), autor.email if autor else ""
            ),
            "stopien": self._porownaj_fk(
                dane.get("stopień_służbowy"), stopien_baza, self.stopien_id
            ),
            "stanowisko": self._porownaj_fk(
                dane.get("stanowisko_dydaktyczne"),
                stanowisko_baza,
                self.stanowisko_dydaktyczne_id,
            ),
        }

    @property
    def ostrzezenie_email(self):
        """Komunikat o odrzuconym adresie e-mail (z
        ``dane_znormalizowane["ostrzeżenia"]``) albo ``None`` — renderowany w
        komórce e-mail porównywarki jako ``label alert``."""
        for o in (self.dane_znormalizowane or {}).get("ostrzeżenia") or []:
            if "e-mail" in o.lower():
                return o
        return None
```

- [ ] **Step 4: Dołóż `select_related` w `get_details_set` (bez N+1)**

W `src/import_pracownikow/models.py`, w `ImportPracownikow.get_details_set`, do
listy `.select_related(...)` dodaj dwie ścieżki (jeśli Plan 3 ich nie dodał):

```python
                "autor__stopien_sluzbowy",
                "autor_jednostka__stanowisko",
```

(Obejmuje to zarówno tabelę wyników, jak i re-render po swapie HTMX — oba idą
przez `get_details_set()`.)

- [ ] **Step 5: Dodaj 3 nagłówki + popraw colspan/columnDefs w liście**

W `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`,
w `<thead>`, WSTAW trzy nagłówki MIĘDZY `<th>Jednostka (obecna → z pliku)</th>` a
`<th>Akcje / zmiany</th>`:

```django
                        <th>E-mail (plik → baza)</th>
                        <th>Stopień służbowy (plik → baza)</th>
                        <th>Stanowisko dydaktyczne (plik → baza)</th>
```

Zmień `colspan` pustego wiersza z `10` na `13`:

```django
                            <td colspan="13" class="text-center"><strong>
```

Zmień `columnDefs` DataTables (dwie ostatnie kolumny — Akcje, Przepnij — są teraz
pod indeksami 11 i 12):

```javascript
                columnDefs: [{orderable: false, searchable: false, targets: [11, 12]}]
```

- [ ] **Step 6: Dodaj 3 komórki porównania w partiału wiersza**

W `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html`,
WSTAW poniższy blok MIĘDZY zamknięciem komórki „Jednostka" (`</td>` kończące blok
`{% if row.jednostka %}…{% endif %}`) a otwarciem komórki „Akcje / zmiany"
(`<td>` z `{% if parent_object.edytowalny_podglad %}` dla akcji autora):

```django
{# Porównywarka „plik vs baza" (§12): e-mail / stopień służbowy / stanowisko #}
{# dydaktyczne. Różnicę PODŚWIETLAMY (Foundation label warning + klasa-hook #}
{# import-porownanie-rozne) — to sygnał dla operatora. No-overwrite dotyczy #}
{# WYŁĄCZNIE e-maila; stopień i stanowisko to overwrite-if-different (Plan 3). #}
{# W komórce e-mail pokazujemy też ostrzeżenie o odrzuconym adresie. #}
{% with porownanie=row.porownaj_z_baza %}
    <td>{% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.email ostrzezenie=row.ostrzezenie_email %}</td>
    <td>{% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.stopien %}</td>
    <td>{% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.stanowisko %}</td>
{% endwith %}
```

Create `src/import_pracownikow/templates/import_pracownikow/partials/_porownanie_kom.html`
(wspólny render jednej komórki porównania — trójka `{plik, baza, rozne}`):

```django
{# Jedna komórka porównywarki: pole = {plik, baza, rozne}. Gdy różnica — plik #}
{# w żółtym labelu + wartość z bazy wyszarzona pod spodem. Gdy zgodne/puste — #}
{# sama wartość z pliku (albo „—"). ``ostrzezenie`` (przekazywane tylko do #}
{# komórki e-mail) — komunikat o odrzuconym adresie jako czerwony label alert. #}
{% if pole.rozne %}
    <span class="label warning import-porownanie-rozne">{{ pole.plik }}</span>
    <br>
    <span class="secondary">baza: {{ pole.baza|default:"—" }}</span>
{% elif pole.plik %}
    {{ pole.plik }}
{% else %}
    <span class="secondary">—</span>
{% endif %}
{% if ostrzezenie %}
    <br>
    <span class="label alert" title="{{ ostrzezenie }}">e-mail odrzucony</span>
{% endif %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka.py src/import_pracownikow/tests/test_views_preview_render.py -v`
Expected: PASS (nowe testy porównywarki + istniejący render podglądu bez regresji —
liczba `<td>` = liczba `<th>` = 13).

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html \
  src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html \
  src/import_pracownikow/templates/import_pracownikow/partials/_porownanie_kom.html \
  src/import_pracownikow/tests/test_porownywarka.py
git commit -m "feat(import_pracownikow): porównywarka plik↔baza (e-mail/stopień/stanowisko)"
```

---

## Task 4: Test E2E — komórka złożona → jednostki (Krok 1) → osoby (Krok 2)

**Files:**
- Test: `src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py` (create)

**Interfaces:**
- Consumes (kontrakt Planów 1–3): `parsuj_komorke` wpięty w `analyze`
  (komórka → nazwa/skrót jednostki); split `nazwisko_imię`; klasyfikacja stopnia
  (`Autor.stopien_sluzbowy`) i stanowiska (`Autor_Jednostka.stanowisko`); zapis
  `Autor.email` dla NOWEGO autora + no-overwrite dla istniejącego; `integruj`
  honorujący `zakres_integracji`.
- Produces: test akceptacyjny całego przebiegu (analyze → integrate struktury →
  integrate osób) na syntetycznych wierszach APOŻ.

- [ ] **Step 1: Write the E2E test**

Create `src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py`:

```python
"""E2E słowników stopień/stanowisko + e-mail: komórka złożona APOŻ → utworzenie
jednostki (Krok 1) → import osób ze stopniem/stanowiskiem/e-mailem (Krok 2).

Baseline testcontainers NIE zawiera struktur APOŻ — test sam przechodzi Krok 1
(tworzy jednostkę z komórki) i seeduje słowniki ``baker``iem. Izolację wyciekłej
pętli asyncio pod xdist zapewnia autouse-fixture z ``tests/conftest.py`` (obejmuje
też ten podkatalog). Wzorzec przebiegu: ``test_e2e_jednostki.py`` (patch
``otworz_zrodlo`` + jawne stany + ``MockProgress``)."""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj

KOMORKA = (
    "RW-1/1 Zakład Kierowania Działaniami Ratowniczymi WIBiOL taktyka"
)

# Mapowanie nagłówków pliku → cele (jak po ekranie mapowania, Plan 2/3).
MAPOWANIE = {
    "komórka": "komórka_złożona",
    "nazwisko_imię": "nazwisko_imię",
    "email": "email",
    "stopień": "stopień_służbowy",
    "stanowisko_dyd": "stanowisko_dydaktyczne",
}


def _wiersz(nr, komorka, nazwisko_imie, email, stopien, stanowisko):
    return {
        "komórka": komorka,
        "nazwisko_imię": nazwisko_imie,
        "email": email,
        "stopień": stopien,
        "stanowisko_dyd": stanowisko,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": nr,
    }


def _run(imp, stan, zakres=None):
    imp.stan = stan
    if zakres is not None:
        imp.zakres_integracji = zakres
    imp.run(MockProgress(imp))
    imp.refresh_from_db()


@pytest.mark.django_db
def test_e2e_komorka_zlozona_stopnie_stanowiska_email(uczelnia):
    # --- Seed słowników (hard-match) + istniejący autor (no-overwrite e-mail) ---
    stopien = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    istniejacy = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", email="stary@example.com"
    )

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    imp.mapowanie_kolumn = MAPOWANIE
    imp.save(update_fields=["mapowanie_kolumn"])

    wiersze = [
        # NOWY autor — utworzony w Kroku 2; e-mail USTAWIONY.
        _wiersz(1, KOMORKA, "Anszczak Marcin", "marcin@example.com",
                "kpt.", "adiunkt"),
        # ISTNIEJĄCY autor — e-mail NIE nadpisany (no-overwrite §11).
        _wiersz(2, KOMORKA, "Kowalski Jan", "nowy@example.com",
                "kpt.", "adiunkt"),
    ]

    # --- KROK 1a: analiza (dry-run) ---
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = len(wiersze)
        MZ.return_value.data.return_value = iter(wiersze)
        analizuj(imp, MockProgress(imp))
    imp.refresh_from_db()

    # Jednostki z pliku nie ma w bazie → Krok 1 wymagany (nie auto-skip).
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    assert imp.jednostki_do_decyzji.exists()
    # nowy autor (brak dopasowania) — zaznacz „utwórz nowego" jak operator w UI.
    imp.importpracownikowrow_set.filter(autor__isnull=True).update(
        utworz_nowego=True
    )

    # --- KROK 1b: zapis STRUKTURY (jednostki + tytuły + stopnie/stanowiska) ---
    _run(
        imp,
        ImportPracownikow.STAN_ZATWIERDZONY,
        ImportPracownikow.ZAKRES_STRUKTURA,
    )
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    jednostka = Jednostka.objects.get(
        nazwa="Zakład Kierowania Działaniami Ratowniczymi"
    )
    assert jednostka.skrot == "RW-1/1"

    # --- KROK 2: import OSÓB (pełny) ---
    _run(
        imp,
        ImportPracownikow.STAN_ZATWIERDZONY,
        ImportPracownikow.ZAKRES_PELNY,
    )
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # Nowy autor: utworzony, e-mail + stopień USTAWIONE, AJ ze stanowiskiem.
    nowy = Autor.objects.get(nazwisko="Anszczak")
    assert nowy.email == "marcin@example.com"
    assert nowy.stopien_sluzbowy_id == stopien.pk
    aj_nowy = Autor_Jednostka.objects.get(autor=nowy, jednostka=jednostka)
    assert aj_nowy.stanowisko_id == stanow.pk

    # Istniejący autor: e-mail NIE nadpisany; stanowisko na AJ ustawione.
    istniejacy.refresh_from_db()
    assert istniejacy.email == "stary@example.com"  # no-overwrite §11
    aj_ist = Autor_Jednostka.objects.get(autor=istniejacy, jednostka=jednostka)
    assert aj_ist.stanowisko_id == stanow.pk
```

- [ ] **Step 2: Run the E2E test**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py -v`
Expected: PASS. Jeśli padnie na klasyfikacji komórki/stopnia/stanowiska albo na
zapisie e-maila/stanowiska — to sygnał braku wpięcia w Planie 3 (E2E jest testem
akceptacyjnym Planów 1–3), NIE regresja Planu 4. Zdiagnozuj przez
superpowers:systematic-debugging i dopnij brakujące wpięcie w odpowiednim planie.

- [ ] **Step 3: Powtórzenie (łapanie flake'ów kolejności)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py --count=3 -q`
Expected: 3× PASS (pytest-repeat; potwierdza brak flake'u pętli asyncio / ambient
data).

- [ ] **Step 4: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py
git commit -m "test(import_pracownikow): E2E komórka złożona → jednostki → osoby (stopień/stanowisko/e-mail)"
```

---

## Task 5: Newsfragment (towncrier) — podsumowanie feature'u

**Files:**
- Create: `src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst`

**Interfaces:**
- Produces: wpis do changeloga (kompiluje się do `HISTORY.md` przy wydaniu).

- [ ] **Step 1: Sprawdź, czy Plany 1–3 nie dodały już fragmentu**

Run: `ls src/bpp/newsfragments/ | grep -i slownik || echo BRAK`
Jeśli fragment już istnieje (dodany w Planie 1/2/3) — pomiń Task 5, ewentualnie
uzupełnij treść o e-mail/porównywarkę.

- [ ] **Step 2: Utwórz fragment**

Create `src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst`:

```rst
Import pracowników rozpoznaje stopień służbowy i stanowisko dydaktyczne
(nowe słowniki), importuje adres e-mail (ustawiany tylko dla nowo tworzonych
autorów — istniejących nie nadpisuje) oraz parsuje „komórkę złożoną" ze skrótem,
nazwą i oddziałem jednostki. Tabela podglądu porównuje e-mail, stopień i
stanowisko z danymi w bazie i podświetla różnice.
```

- [ ] **Step 3: Commit**

```bash
git add src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst
git commit -m "doc(import_pracownikow): newsfragment — słowniki stopień/stanowisko + e-mail"
```

---

## Weryfikacja końcowa Planu 4

- [ ] **Step 1: Uruchom testy Planu 4**

Run:
```bash
uv run pytest \
  src/import_pracownikow/tests/test_parsers/test_oczysc_email.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_email.py \
  src/import_pracownikow/tests/test_porownywarka.py \
  src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py \
  -v 2>&1 | tee /tmp/plan4_tests.log
```
Expected: wszystkie PASS.

- [ ] **Step 2: Regresja szerszej suity importu**

Run:
```bash
uv run pytest src/import_pracownikow/ -q -n auto 2>&1 | tee /tmp/plan4_regresja.log
```
Expected: PASS (żadnej regresji w podglądzie/analizie/integracji; szczególnie
`test_views_preview_render.py`, `test_pipeline/`, `test_przeglad.py`).

- [ ] **Step 3: Migracje bez driftu**

Run: `uv run python src/manage.py makemigrations --check --dry-run import_pracownikow`
Expected: „No changes detected".

- [ ] **Step 4: ruff**

Run:
```bash
ruff check src/import_pracownikow/parsers/wartosci.py \
  src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/models.py \
  src/import_pracownikow/tests/test_parsers/test_oczysc_email.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_email.py \
  src/import_pracownikow/tests/test_porownywarka.py \
  src/import_pracownikow/tests/test_pipeline/test_e2e_slowniki.py
```
Expected: brak błędów.

**Deliverable Planu 4:** e-mail waliduje się łagodnie (zły adres → puste +
ostrzeżenie w wierszu, bez crasha analizy; adres > 128 znaków też odrzucany);
tabela podglądu ma porównywarkę „plik vs baza" dla e-maila/stopnia/stanowiska z
podświetleniem różnic (read-only; e-mail no-overwrite, stopień/stanowisko
porównywane semantycznie po FK); test E2E spina komórkę złożoną → utworzenie
jednostek → import osób ze stopniem/stanowiskiem/e-mailem; newsfragment podsumowuje
cały feature. Seria słowników stopień/stanowisko (Plany 1–4) domknięta.
