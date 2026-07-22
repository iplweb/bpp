# Import pracowników — pobieranie plików (oryginał + „po imporcie") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na stronie rezultatów importu pracowników dodać dwa pobrania: (A) oryginalny XLSX (chroniony, sendfile) i (B) kanoniczny, SKORYGOWANY plik „po imporcie" odzwierciedlający stan bazy i gotowy do bezobsługowego re-importu.

**Architecture:** Builder pliku „po imporcie" to czysta funkcja w nowym module `eksport.py` (openpyxl → bytes), czytająca wartości z autorytatywnych rekordów `Autor` / `Autor_Jednostka`. Dwa cienkie widoki klasowe w `views.py` (sendfile dla oryginału, `HttpResponse` z bytes buildera dla „po imporcie"), gejtowane grupą `"wprowadzanie danych"` i scope'owane do właściciela. Dwa przyciski w szablonie rezultatów.

**Tech Stack:** Django, `django_sendfile`, `openpyxl`, `braces.GroupRequiredMixin`, pytest + `model_bakery`.

## Global Constraints

- Python `uv run` przed KAŻDYM poleceniem Python/pytest. Nigdy gołe `python`/`pytest`.
- Max długość linii: 88 znaków (ruff).
- **Bez zmian w modelach → bez migracji.** Nie tykać istniejących migracji.
- Testy: konwencja pytest (funkcje, `@pytest.mark.django_db`, `model_bakery.baker`), NIE `unittest.TestCase`.
- Grupa dostępu: `bpp.const.GR_WPROWADZANIE_DANYCH` == `"wprowadzanie danych"` (w `views.py` stała `GROUP_REQUIRED`).
- Ikony w szablonach frontu publicznego: Foundation-Icons (`<span class="fi-..."></span>`).
- Komentarze Django `{# #}` tylko jedno-liniowe (każda linia własne `{# #}`).
- Nagłówki kolumn pliku „po imporcie" MUSZĄ normalizować się do synonimów z `mapping._SYNONIMY` (normalizacja: lower + spacje/kropki/myślniki→`_`; nawiasy zostają!). Test round-trip (Task 3) to egzekwuje.
- Wartości „po imporcie" czytane z rekordów bazy: pola autora z `row.autor`, pola zatrudnienia z `row.autor_jednostka`. Nie z pliku, nie z proponowanych FK wiersza.

Spec: `docs/superpowers/specs/2026-07-14-import-pobieranie-plikow-design.md`

---

## Struktura plików

| Plik | Rola |
|---|---|
| `src/import_pracownikow/eksport.py` | **NOWY** — builder `zbuduj_plik_po_imporcie(import_obj) -> bytes` + rejestr kolumn |
| `src/import_pracownikow/views.py` | **MODYFIKACJA** — `PobierzOryginalView`, `PobierzPoImporcieView`, helper scope'ujący |
| `src/import_pracownikow/urls.py` | **MODYFIKACJA** — 2 ścieżki |
| `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html` | **MODYFIKACJA** — blok 2 przycisków |
| `src/import_pracownikow/tests/test_eksport.py` | **NOWY** — builder + round-trip |
| `src/import_pracownikow/tests/test_views_pobieranie.py` | **NOWY** — auth, scope, gate, sendfile |
| `src/bpp/newsfragments/import-pobieranie-plikow.feature.rst` | **NOWY** — changelog |

Referencje w kodzie (potwierdzone):
- Plik oryginału: `ImportPracownikow.plik_xls` (`FileField`, `protected/import_pracownikow/`).
- Stan zakończenia: `ImportPracownikow.STAN_ZINTEGROWANY` (`"zintegrowany"`).
- Kolejność wierszy + FK: `ImportPracownikow.get_details_set()`.
- Predykat „pominięty": `row.autor_id is None`.
- Użyte kolumny: `ImportPracownikow.mapowanie_kolumn` (dict), wartość `mapping.POLE_POMIN` = `"__pomin__"`.
- Autor: `nazwisko`, `imiona`, `orcid`, `pbn_uid_id`, `system_kadrowy_id`, `email`, `tytul`, `stopien_sluzbowy`.
- Autor_Jednostka: `jednostka`, `funkcja`, `stanowisko` (=StanowiskoDydaktyczne), `grupa_pracownicza`, `wymiar_etatu`, `rozpoczal_prace`, `zakonczyl_prace`, `podstawowe_miejsce_pracy`.
- Round-trip: `mapping.zaproponuj_mapowanie(naglowki) -> {h: cel}`, `mapping.waliduj_mapowanie(mapowanie) -> [błędy]`.
- sendfile wzorzec: `src/oswiadczenia/views.py:569`.
- Szablon rezultatów: `import_pracownikow/importpracownikowrow_list.html`, `{% block content %}`.

---

## Task 1: Builder — rdzeń (kotwice tożsamości, wartości z bazy, pomijanie, kolejność)

**Files:**
- Create: `src/import_pracownikow/eksport.py`
- Test: `src/import_pracownikow/tests/test_eksport.py`

**Interfaces:**
- Produces: `zbuduj_plik_po_imporcie(import_obj) -> bytes` (bytes skoroszytu XLSX). Wiersz 1 = nagłówki; dane w kolejności `get_details_set()`; tylko wiersze z `autor_id is not None`. Zawsze obecne kolumny: `BPP ID`, `Nazwisko`, `Imię`, `Nazwa jednostki`.
- Consumes: `mapping.POLE_POMIN`; `ImportPracownikow.get_details_set()`.

- [ ] **Step 1: Write the failing test**

Utwórz `src/import_pracownikow/tests/test_eksport.py`:

```python
from io import BytesIO

import pytest
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.eksport import zbuduj_plik_po_imporcie
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.tests._helpers import unikalna_nazwa


def _wczytaj(content):
    ws = load_workbook(BytesIO(content)).active
    naglowki = [c.value for c in ws[1]]
    wiersze = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
    return naglowki, wiersze


def _import_zintegrowany(**kw):
    return baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
        mapowanie_kolumn=kw.pop("mapowanie_kolumn", {}),
        **kw,
    )


def _wiersz(imp, *, loc, autor=None, autor_jednostka=None, dane=None):
    return baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        autor_jednostka=autor_jednostka,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": loc, **(dane or {})},
    )


@pytest.mark.django_db
def test_builder_pomija_wiersze_bez_autora_i_zachowuje_kolejnosc():
    imp = _import_zintegrowany(
        mapowanie_kolumn={"Nazwisko": "nazwisko", "Imię": "imię",
                          "Jednostka": "nazwa_jednostki"}
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Klinika Poprawna"))
    a2 = baker.make(Autor, nazwisko="Druga", imiona="Anna")
    aj2 = baker.make(Autor_Jednostka, autor=a2, jednostka=j)
    a1 = baker.make(Autor, nazwisko="Pierwszy", imiona="Jan")
    aj1 = baker.make(Autor_Jednostka, autor=a1, jednostka=j)
    # loc rosnąco: a1 (loc=0), a2 (loc=1); wiersz pominięty (loc=2, autor=None)
    _wiersz(imp, loc=0, autor=a1, autor_jednostka=aj1)
    _wiersz(imp, loc=1, autor=a2, autor_jednostka=aj2)
    _wiersz(imp, loc=2, autor=None, autor_jednostka=None)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert len(wiersze) == 2  # pominięty wypadł
    assert naglowki[:4] == ["BPP ID", "Nazwisko", "Imię", "Nazwa jednostki"]
    assert [w[0] for w in wiersze] == [a1.pk, a2.pk]  # kolejność z pliku
    assert [w[1] for w in wiersze] == ["Pierwszy", "Druga"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_eksport.py::test_builder_pomija_wiersze_bez_autora_i_zachowuje_kolejnosc -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'import_pracownikow.eksport'`.

- [ ] **Step 3: Write minimal implementation**

Utwórz `src/import_pracownikow/eksport.py`:

```python
"""Generator pliku „po imporcie" — kanoniczny, SKORYGOWANY XLSX.

Odbija stan BAZY po imporcie: wartości czytane z autorytatywnych rekordów
(``Autor`` / ``Autor_Jednostka``), nie z pliku ani z proponowanych FK wiersza.
Kanoniczne nagłówki (auto-rozpoznawane) + kolumna ``BPP ID`` → plik re-importuje
się bezobsługowo.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from import_pracownikow.mapping import POLE_POMIN


def _tekst(v):
    return "" if v is None else str(v)


def _iso(d):
    return "" if d is None else d.isoformat()


def _tak_nie(v):
    return "" if v is None else ("T" if v else "N")


def _jednostka(row):
    aj = row.autor_jednostka
    return aj.jednostka.nazwa if aj and aj.jednostka_id else ""


# (nagłówek, targety_włączające, getter(row), tryb)
# tryb: "always" | "attr" | "id_enrich"
REJESTR = [
    ("BPP ID", (), lambda r: r.autor_id, "always"),
    ("Nazwisko", ("nazwisko", "osoba_sklejona", "nazwisko_imię"),
     lambda r: _tekst(r.autor.nazwisko), "always"),
    ("Imię", ("imię", "osoba_sklejona", "nazwisko_imię"),
     lambda r: _tekst(r.autor.imiona), "always"),
    ("ORCID", ("orcid",), lambda r: _tekst(r.autor.orcid), "id_enrich"),
    ("PBN UUID", ("pbn_uuid",), lambda r: _tekst(r.autor.pbn_uid_id), "id_enrich"),
    ("Numer", ("numer",), lambda r: _tekst(r.autor.system_kadrowy_id), "id_enrich"),
    ("E-mail", ("email",), lambda r: _tekst(r.autor.email), "attr"),
    ("Nazwa jednostki",
     ("nazwa_jednostki", "nazwa_jednostki_niepelna", "komórka_złożona", "wydział"),
     _jednostka, "always"),
    ("Tytuł", ("tytuł_stopień",), lambda r: _tekst(r.autor.tytul), "attr"),
    ("Stopień służbowy", ("stopień_służbowy",),
     lambda r: _tekst(r.autor.stopien_sluzbowy), "attr"),
    ("Funkcja w jednostce", ("stanowisko",),
     lambda r: _tekst(r.autor_jednostka.funkcja) if r.autor_jednostka else "", "attr"),
    ("Stanowisko dydaktyczne", ("stanowisko_dydaktyczne",),
     lambda r: _tekst(r.autor_jednostka.stanowisko) if r.autor_jednostka else "",
     "attr"),
    ("Grupa pracownicza", ("grupa_pracownicza",),
     lambda r: _tekst(r.autor_jednostka.grupa_pracownicza) if r.autor_jednostka
     else "", "attr"),
    ("Wymiar etatu", ("wymiar_etatu_tekst", "wymiar_etatu_ulamek"),
     lambda r: _tekst(r.autor_jednostka.wymiar_etatu) if r.autor_jednostka else "",
     "attr"),
    ("Data zatrudnienia", ("data_zatrudnienia",),
     lambda r: _iso(r.autor_jednostka.rozpoczal_prace) if r.autor_jednostka else "",
     "attr"),
    ("Data końca zatrudnienia", ("data_końca_zatrudnienia",),
     lambda r: _iso(r.autor_jednostka.zakonczyl_prace) if r.autor_jednostka else "",
     "attr"),
    ("Podstawowe miejsce pracy", ("podstawowe_miejsce_pracy",),
     lambda r: _tak_nie(r.autor_jednostka.podstawowe_miejsce_pracy)
     if r.autor_jednostka else "", "attr"),
]


def _wiersze_do_eksportu(import_obj):
    qs = import_obj.get_details_set().select_related(
        "autor", "autor__tytul", "autor__stopien_sluzbowy",
        "autor_jednostka", "autor_jednostka__jednostka",
        "autor_jednostka__funkcja", "autor_jednostka__stanowisko",
        "autor_jednostka__grupa_pracownicza", "autor_jednostka__wymiar_etatu",
    )
    return [r for r in qs if r.autor_id is not None]


def _kolumny_do_emisji(import_obj, wiersze):
    uzyte = set((import_obj.mapowanie_kolumn or {}).values()) - {POLE_POMIN}
    kolumny = []
    for naglowek, targety, getter, tryb in REJESTR:
        if tryb == "always":
            emit = True
        elif tryb == "attr":
            emit = bool(set(targety) & uzyte)
        elif tryb == "id_enrich":
            emit = bool(set(targety) & uzyte) or any(getter(r) for r in wiersze)
        else:
            raise ValueError(f"Nieznany tryb kolumny: {tryb}")
        if emit:
            kolumny.append((naglowek, getter))
    return kolumny


def zbuduj_plik_po_imporcie(import_obj) -> bytes:
    wiersze = _wiersze_do_eksportu(import_obj)
    kolumny = _kolumny_do_emisji(import_obj, wiersze)

    wb = Workbook()
    ws = wb.active
    ws.title = "po imporcie"
    ws.append([naglowek for naglowek, _ in kolumny])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for r in wiersze:
        ws.append([getter(r) for _, getter in kolumny])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_eksport.py::test_builder_pomija_wiersze_bez_autora_i_zachowuje_kolejnosc -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/eksport.py src/import_pracownikow/tests/test_eksport.py
git commit -m "feat(import): builder pliku „po imporcie" — rdzeń (kotwice, wartości z bazy)"
```

---

## Task 2: Builder — selekcja kolumn (użyte/ignorowane, id_enrich) + wartość SKORYGOWANA + brak zatrudnienia

**Files:**
- Modify: `src/import_pracownikow/eksport.py` (jeśli test wykryje brak — logika już jest w Task 1; ten task WERYFIKUJE i domyka zachowanie)
- Test: `src/import_pracownikow/tests/test_eksport.py`

**Interfaces:**
- Consumes: `zbuduj_plik_po_imporcie` (Task 1).

- [ ] **Step 1: Write the failing tests**

Dopisz do `test_eksport.py`:

```python
from datetime import date

from bpp.models import StopienSluzbowy


@pytest.mark.django_db
def test_ignorowane_kolumny_znikaja_uzyte_zostaja():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko", "Imię": "imię",
            "Jedn org": "nazwa_jednostki",
            "Dyscyplina": "__pomin__",  # ignorowana
            "Tytuł nauk.": "tytuł_stopień",  # użyta
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Katedra X"))
    a = baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(imp, loc=0, autor=a, autor_jednostka=aj,
            dane={"Dyscyplina": "nauki medyczne", "Tytuł nauk.": "dr"})

    naglowki, _ = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert "Tytuł" in naglowki
    assert "Dyscyplina" not in naglowki
    assert "nauki medyczne" not in naglowki
    assert "Stopień służbowy" not in naglowki  # nieużyty target → brak kolumny


@pytest.mark.django_db
def test_wartosc_skorygowana_wygrywa_z_plikiem():
    # Plik miał błędną nazwę jednostki; baza ma poprawną → w pliku wynikowym
    # jest wartość z BAZY.
    imp = _import_zintegrowany(
        mapowanie_kolumn={"Nazwisko": "nazwisko", "Imię": "imię",
                          "Jednostka": "nazwa_jednostki"}
    )
    poprawna = unikalna_nazwa("Klinika Chorób Wewnętrznych")
    j = baker.make(Jednostka, nazwa=poprawna)
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(imp, loc=0, autor=a, autor_jednostka=aj,
            dane={"Jednostka": "klin chor wewn", "Nazwisko": "Kowalksi"})

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["Nazwa jednostki"]] == poprawna  # nie "klin chor wewn"
    assert wiersze[0][kol["Nazwisko"]] == "Kowalski"  # nie "Kowalksi"


@pytest.mark.django_db
def test_id_enrich_orcid_gdy_niepusty_mimo_braku_mapowania():
    imp = _import_zintegrowany(
        mapowanie_kolumn={"Nazwisko": "nazwisko", "Imię": "imię",
                          "Jednostka": "nazwa_jednostki"}
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Zakład Y"))
    a = baker.make(Autor, nazwisko="Test", imiona="Orc",
                   orcid="0000-0002-1825-0097")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(imp, loc=0, autor=a, autor_jednostka=aj)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert "ORCID" in naglowki  # niepusty ORCID → kolumna mimo braku w mapowaniu
    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["ORCID"]] == "0000-0002-1825-0097"


@pytest.mark.django_db
def test_autor_bez_zatrudnienia_wchodzi_z_pustymi_polami_zatrudnienia():
    imp = _import_zintegrowany(
        mapowanie_kolumn={"Nazwisko": "nazwisko", "Imię": "imię",
                          "Jednostka": "nazwa_jednostki",
                          "Etat": "wymiar_etatu_tekst"}
    )
    a = baker.make(Autor, nazwisko="Sam", imiona="Autor")
    _wiersz(imp, loc=0, autor=a, autor_jednostka=None)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert len(wiersze) == 1  # autor wszedł, choć bez zatrudnienia
    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["BPP ID"]] == a.pk
    assert wiersze[0][kol["Nazwa jednostki"]] in (None, "")  # AJ None → puste
    assert wiersze[0][kol["Wymiar etatu"]] in (None, "")
```

- [ ] **Step 2: Run tests to verify pass/fail**

Run: `uv run pytest src/import_pracownikow/tests/test_eksport.py -v`
Expected: wszystkie PASS (logika z Task 1 już to obsługuje). Jeśli któryś FAIL — napraw `eksport.py` (najczęstsza przyczyna: getter `id_enrich` liczy pustość — upewnij się, że dla ORCID zwraca `_tekst(...)`).

- [ ] **Step 3: Commit**

```bash
git add src/import_pracownikow/tests/test_eksport.py src/import_pracownikow/eksport.py
git commit -m "test(import): builder — selekcja kolumn, wartość skorygowana, brak zatrudnienia"
```

---

## Task 3: Builder — test round-trip (gwarancja gładkiego re-importu)

**Files:**
- Modify: `src/import_pracownikow/eksport.py` (tylko jeśli test wykryje nierozpoznany nagłówek)
- Test: `src/import_pracownikow/tests/test_eksport.py`

**Interfaces:**
- Consumes: `zbuduj_plik_po_imporcie`; `mapping.zaproponuj_mapowanie`, `mapping.waliduj_mapowanie`, `mapping.POLE_POMIN`.

- [ ] **Step 1: Write the failing test**

Dopisz do `test_eksport.py`:

```python
from import_pracownikow.mapping import (
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)


@pytest.mark.django_db
def test_round_trip_naglowki_auto_mapuja_sie():
    # Plik „po imporcie" musi re-importować się bez ręcznego mapowania:
    # każdy nagłówek rozpoznany + walidacja mapowania bez błędów.
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko", "Imię": "imię",
            "Jednostka": "nazwa_jednostki", "Tytuł": "tytuł_stopień",
            "Stopień sł.": "stopień_służbowy", "Funkcja": "stanowisko",
            "St. dyd.": "stanowisko_dydaktyczne", "Grupa": "grupa_pracownicza",
            "Etat": "wymiar_etatu_tekst", "Od": "data_zatrudnienia",
            "Do": "data_końca_zatrudnienia", "Gł.": "podstawowe_miejsce_pracy",
            "Mail": "email", "Nr": "numer",
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Klinika RT"))
    stopien = baker.make(StopienSluzbowy)
    a = baker.make(Autor, nazwisko="Rt", imiona="Test",
                   orcid="0000-0002-1825-0097", stopien_sluzbowy=stopien)
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(imp, loc=0, autor=a, autor_jednostka=aj)

    naglowki, _ = _wczytaj(zbuduj_plik_po_imporcie(imp))

    mapowanie = zaproponuj_mapowanie(naglowki)
    nierozpoznane = [h for h, cel in mapowanie.items() if cel == POLE_POMIN]
    assert nierozpoznane == [], f"Nierozpoznane nagłówki: {nierozpoznane}"
    assert waliduj_mapowanie(mapowanie) == []
```

- [ ] **Step 2: Run test**

Run: `uv run pytest src/import_pracownikow/tests/test_eksport.py::test_round_trip_naglowki_auto_mapuja_sie -v`
Expected: PASS. **Jeśli FAIL** z listą nierozpoznanych nagłówków — zmień odpowiedni nagłówek w `REJESTR` (`eksport.py`) na string, który po normalizacji (lower, spacje/kropki/myślniki→`_`) jest kluczem w `mapping._SYNONIMY` (np. `"Numer"`→`numer`, `"E-mail"`→`e_mail`, `"Funkcja w jednostce"`→`funkcja_w_jednostce`). NIE używać nawiasów w nagłówku (nie normalizują się).

- [ ] **Step 3: Commit**

```bash
git add src/import_pracownikow/tests/test_eksport.py src/import_pracownikow/eksport.py
git commit -m "test(import): round-trip — nagłówki pliku „po imporcie" auto-mapują się"
```

---

## Task 4: Widok + URL „Pobierz oryginał" (sendfile, scope, 404)

**Files:**
- Modify: `src/import_pracownikow/views.py`
- Modify: `src/import_pracownikow/urls.py`
- Test: `src/import_pracownikow/tests/test_views_pobieranie.py`

**Interfaces:**
- Produces: URL `import_pracownikow:pobierz-oryginal` (kwarg `pk`); widok `PobierzOryginalView`; helper `_pobierz_wlasny_import(request, pk)`.

- [ ] **Step 1: Write the failing tests**

Utwórz `src/import_pracownikow/tests/test_views_pobieranie.py`:

```python
import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from import_pracownikow.models import ImportPracownikow


def _user_w_grupie(django_user_model, username="entry"):
    u = django_user_model.objects.create_user(username=username, password="pass")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    return u


def _import_z_plikiem(owner, nazwa="testdata.xlsx"):
    imp = baker.make(ImportPracownikow, owner=owner)
    imp.plik_xls.save(nazwa, SimpleUploadedFile(nazwa, b"PK\x03\x04udawany"),
                      save=True)
    return imp


@pytest.mark.django_db
def test_oryginal_pobiera_wlasciciel_z_grupa(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = _import_z_plikiem(u)
    resp = client.get(reverse("import_pracownikow:pobierz-oryginal",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code == 200
    assert "attachment" in resp["Content-Disposition"]
    assert "testdata.xlsx" in resp["Content-Disposition"]


@pytest.mark.django_db
def test_oryginal_bez_grupy_odmowa(client, django_user_model):
    u = django_user_model.objects.create_user(username="plain", password="pass")
    client.force_login(u)
    imp = _import_z_plikiem(u)
    resp = client.get(reverse("import_pracownikow:pobierz-oryginal",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code != 200  # braces GroupRequiredMixin blokuje


@pytest.mark.django_db
def test_oryginal_cudzy_import_404(client, django_user_model):
    wlasciciel = _user_w_grupie(django_user_model, "wlasciciel")
    obcy = _user_w_grupie(django_user_model, "obcy")
    imp = _import_z_plikiem(wlasciciel)
    client.force_login(obcy)
    resp = client.get(reverse("import_pracownikow:pobierz-oryginal",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_oryginal_brak_pliku_404(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = baker.make(ImportPracownikow, owner=u)  # bez plik_xls
    resp = client.get(reverse("import_pracownikow:pobierz-oryginal",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k oryginal -v`
Expected: FAIL — `NoReverseMatch: 'pobierz-oryginal'`.

- [ ] **Step 3: Dodaj importy i widok w `views.py`**

Upewnij się, że w nagłówku `views.py` są importy (dodaj brakujące):

```python
import os

from django.http import Http404, HttpResponse
from django_sendfile import sendfile
```

Dodaj na końcu `views.py`:

```python
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _pobierz_wlasny_import(request, pk):
    """Import właściciela (albo superusera) — inaczej 404 (jak results view)."""
    obj = get_object_or_404(ImportPracownikow, pk=pk)
    if obj.owner_id != request.user.pk and not request.user.is_superuser:
        raise Http404
    return obj


class PobierzOryginalView(GroupRequiredMixin, View):
    """Pobranie oryginalnego, wgranego pliku XLSX (chroniony, przez sendfile)."""

    group_required = GROUP_REQUIRED

    def get(self, request, pk):
        obj = _pobierz_wlasny_import(request, pk)
        if not obj.plik_xls or not os.path.exists(obj.plik_xls.path):
            raise Http404("Plik oryginalny nie istnieje.")
        return sendfile(
            request,
            obj.plik_xls.path,
            attachment=True,
            attachment_filename=os.path.basename(obj.plik_xls.name),
        )
```

(Jeśli `View`, `get_object_or_404` nie są jeszcze zaimportowane — dodaj
`from django.views.generic import View` / potwierdź istniejący import
`from django.shortcuts import get_object_or_404`.)

- [ ] **Step 4: Dodaj ścieżkę w `urls.py`**

W `urlpatterns` (przed zamykającym `]`):

```python
    path(
        "<uuid:pk>/pobierz-oryginal/",
        views.PobierzOryginalView.as_view(),
        name="pobierz-oryginal",
    ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k oryginal -v`
Expected: PASS (4 testy). Jeśli `test_oryginal_bez_grupy_odmowa` daje 200 — sprawdź, że widok dziedziczy `GroupRequiredMixin` PRZED `View`.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py src/import_pracownikow/tests/test_views_pobieranie.py
git commit -m "feat(import): widok „Pobierz oryginał" (sendfile, scope właściciela)"
```

---

## Task 5: Widok + URL „Pobierz plik po imporcie" (gate stanu, XLSX response)

**Files:**
- Modify: `src/import_pracownikow/views.py`
- Modify: `src/import_pracownikow/urls.py`
- Test: `src/import_pracownikow/tests/test_views_pobieranie.py`

**Interfaces:**
- Consumes: `_pobierz_wlasny_import` (Task 4), `XLSX_CONTENT_TYPE` (Task 4), `zbuduj_plik_po_imporcie` (Task 1).
- Produces: URL `import_pracownikow:pobierz-po-imporcie`; widok `PobierzPoImporcieView`.

- [ ] **Step 1: Write the failing tests**

Dopisz do `test_views_pobieranie.py`:

```python
from openpyxl import load_workbook
from io import BytesIO


@pytest.mark.django_db
def test_po_imporcie_przed_finalizacja_404(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = baker.make(ImportPracownikow, owner=u,
                     stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    resp = client.get(reverse("import_pracownikow:pobierz-po-imporcie",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_po_imporcie_po_finalizacji_zwraca_xlsx(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = _import_z_plikiem(u, nazwa="pracownicy_2026.xlsx")
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.mapowanie_kolumn = {"Nazwisko": "nazwisko", "Imię": "imię",
                            "Jednostka": "nazwa_jednostki"}
    imp.save()
    resp = client.get(reverse("import_pracownikow:pobierz-po-imporcie",
                              kwargs={"pk": imp.pk}))
    assert resp.status_code == 200
    assert "pracownicy_2026-po-imporcie.xlsx" in resp["Content-Disposition"]
    ws = load_workbook(BytesIO(resp.getvalue())).active
    assert [c.value for c in ws[1]][:4] == [
        "BPP ID", "Nazwisko", "Imię", "Nazwa jednostki"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k po_imporcie -v`
Expected: FAIL — `NoReverseMatch: 'pobierz-po-imporcie'`.

- [ ] **Step 3: Dodaj widok w `views.py`**

Dodaj po `PobierzOryginalView`:

```python
class PobierzPoImporcieView(GroupRequiredMixin, View):
    """Pobranie kanonicznego, SKORYGOWANEGO pliku „po imporcie".

    Dostępny dopiero po finalizacji (``STAN_ZINTEGROWANY``). Generowany w locie
    z autorytatywnych rekordów bazy — patrz ``eksport.zbuduj_plik_po_imporcie``.
    """

    group_required = GROUP_REQUIRED

    def get(self, request, pk):
        # Lazy import: openpyxl jest ciężki, nie ładujemy go przy starcie/urls.
        from import_pracownikow.eksport import zbuduj_plik_po_imporcie

        obj = _pobierz_wlasny_import(request, pk)
        if obj.stan != ImportPracownikow.STAN_ZINTEGROWANY:
            raise Http404(
                "Plik „po imporcie" dostępny dopiero po zakończeniu importu."
            )
        content = zbuduj_plik_po_imporcie(obj)
        stem = os.path.splitext(os.path.basename(obj.plik_xls.name))[0]
        resp = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
        resp["Content-Disposition"] = (
            f'attachment; filename="{stem}-po-imporcie.xlsx"'
        )
        return resp
```

- [ ] **Step 4: Dodaj ścieżkę w `urls.py`**

```python
    path(
        "<uuid:pk>/pobierz-po-imporcie/",
        views.PobierzPoImporcieView.as_view(),
        name="pobierz-po-imporcie",
    ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k po_imporcie -v`
Expected: PASS (2 testy).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py src/import_pracownikow/tests/test_views_pobieranie.py
git commit -m "feat(import): widok „Pobierz plik po imporcie" (gate stanu, XLSX)"
```

---

## Task 6: Przyciski na stronie rezultatów + newsfragment

**Files:**
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
- Create: `src/bpp/newsfragments/import-pobieranie-plikow.feature.rst`
- Test: `src/import_pracownikow/tests/test_views_pobieranie.py`

**Interfaces:**
- Consumes: URL-e z Task 4/5; kontekst szablonu `parent_object`.

- [ ] **Step 1: Write the failing test**

Dopisz do `test_views_pobieranie.py`:

```python
@pytest.mark.django_db
def test_rezultaty_pokazuje_przyciski(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = _import_z_plikiem(u)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save()
    resp = client.get(reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}))
    tresc = resp.content.decode()
    assert reverse("import_pracownikow:pobierz-oryginal",
                   kwargs={"pk": imp.pk}) in tresc
    assert reverse("import_pracownikow:pobierz-po-imporcie",
                   kwargs={"pk": imp.pk}) in tresc


@pytest.mark.django_db
def test_rezultaty_ukrywa_po_imporcie_przed_finalizacja(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = _import_z_plikiem(u)
    imp.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    imp.save()
    resp = client.get(reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}))
    tresc = resp.content.decode()
    assert reverse("import_pracownikow:pobierz-oryginal",
                   kwargs={"pk": imp.pk}) in tresc  # oryginał zawsze
    assert reverse("import_pracownikow:pobierz-po-imporcie",
                   kwargs={"pk": imp.pk}) not in tresc  # po-imporcie ukryty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k rezultaty -v`
Expected: FAIL (linki nieobecne w treści).

- [ ] **Step 3: Dodaj blok przycisków w szablonie**

W `importpracownikowrow_list.html`, tuż po linii
`<h1>Import danych {{ parent_object.plik_xls.name }}</h1>`, wstaw:

```django
    <div class="button-group">
        {# Pobranie oryginalnego, wgranego pliku XLSX (chroniony). #}
        <a class="button"
           href="{% url "import_pracownikow:pobierz-oryginal" pk=parent_object.pk %}">
            <span class="fi-download"></span> Pobierz oryginał
        </a>
        {# Skorygowany plik „po imporcie" — tylko po finalizacji. #}
        {% if parent_object.stan == "zintegrowany" %}
            <a class="button secondary"
               href="{% url "import_pracownikow:pobierz-po-imporcie" pk=parent_object.pk %}">
                <span class="fi-download"></span> Pobierz plik po imporcie
            </a>
        {% endif %}
    </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_pobieranie.py -k rezultaty -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Dodaj newsfragment**

Utwórz `src/bpp/newsfragments/import-pobieranie-plikow.feature.rst`:

```rst
Na stronie wyników importu pracowników można pobrać oryginalny plik XLSX oraz
kanoniczny, skorygowany plik „po imporcie" (z identyfikatorami BPP i poprawnymi
wartościami z bazy), gotowy do ponownego, bezobsługowego wczytania.
```

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html src/bpp/newsfragments/import-pobieranie-plikow.feature.rst src/import_pracownikow/tests/test_views_pobieranie.py
git commit -m "feat(import): przyciski pobierania na stronie rezultatów + newsfragment"
```

---

## Task 7: QA — pełna suita modułu + lint

**Files:** (bez zmian kodu; ewentualne poprawki lintu)

- [ ] **Step 1: ruff format + check (tylko zmienione pliki)**

Run:
```bash
uv run ruff format src/import_pracownikow/eksport.py src/import_pracownikow/views.py src/import_pracownikow/tests/test_eksport.py src/import_pracownikow/tests/test_views_pobieranie.py
uv run ruff check src/import_pracownikow/eksport.py src/import_pracownikow/views.py src/import_pracownikow/tests/test_eksport.py src/import_pracownikow/tests/test_views_pobieranie.py
```
Expected: brak błędów. Błędy naprawiaj ręcznie (Edit), NIE `--fix`.

- [ ] **Step 2: djlint szablonu**

Run: `uv run djlint src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html --lint`
Expected: brak nowych błędów na dodanych liniach (istniejące H-warny pliku ignoruj — nie ruszaj cudzych linii).

- [ ] **Step 3: Pełna suita modułu**

Run: `uv run pytest src/import_pracownikow/ -p no:randomly -q 2>&1 | tail -30`
Expected: wszystko zielone (moduł ~600+ testów). Zapisz liczbę passed.

- [ ] **Step 4: Commit (jeśli lint coś zmienił)**

```bash
git add -A
git commit -m "chore(import): lint po dodaniu pobierania plików" || echo "nic do commita"
```

---

## Self-Review (autor planu)

**1. Pokrycie spec:**
- A. Pobierz oryginał (sendfile, protected, grupa, oryginalna nazwa, 404 brak pliku) → Task 4. ✓
- B. Plik „po imporcie": gate `STAN_ZINTEGROWANY` → Task 5; wiersze tylko z autorem → Task 1; tylko użyte kolumny, ignorowane znikają → Task 2; kanoniczne nagłówki + wartości z bazy (SKORYGOWANE, autor/autor_jednostka) → Task 1/2; kotwice tożsamości (BPP ID/Nazwisko/Imię/Nazwa jednostki) + id_enrich ORCID/PBN/Numer → Task 1/2; brak zatrudnienia → puste → Task 2; round-trip re-import → Task 3; nazwa `-po-imporcie.xlsx` → Task 5. ✓
- C. Przyciski na `/rezultaty/`, po-imporcie warunkowy → Task 6. ✓
- D. Testy (auth, scope, gate, round-trip, skorygowany) → Task 1–6. ✓
- Higiena: newsfragment → Task 6; ruff/djlint/suita → Task 7; bez migracji. ✓

**2. Placeholder scan:** brak TBD/TODO; cały kod podany dosłownie. ✓

**3. Spójność typów/nazw:** `zbuduj_plik_po_imporcie(import_obj)->bytes`, `_pobierz_wlasny_import(request,pk)`, `XLSX_CONTENT_TYPE`, `zaproponuj_mapowanie`/`waliduj_mapowanie`/`POLE_POMIN` — używane spójnie między taskami. ✓

**Ryzyka do pilnowania przy wykonaniu:**
- Task 3: jeśli któryś nagłówek nierozpoznany — poprawić string w `REJESTR` na synonim (test to wykryje i wskaże). To JEDYNe miejsce, gdzie nagłówki mogą wymagać korekty.
- `test_oryginal_bez_grupy_odmowa` asertuje `!= 200` (braces domyślnie redirect 302); nie zakładać konkretnego kodu.
