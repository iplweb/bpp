# Import: słowniki stopień/stanowisko — Plan 3: Pipeline + ekrany weryfikacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wpiąć słowniki `StopienSluzbowy` (na `Autor`) i `StanowiskoDydaktyczne` (na `Autor_Jednostka`) w cały przepływ importu pracowników — model decyzji + migracja `import_pracownikow 0023`, `AutorForm`, reconcilery i klasyfikacja w `analyze`, rozstrzyganie i dopięcie FK w `integrate`, ekrany weryfikacji + bramki. Przy okazji wpiąć parsery (komórka złożona, „nazwisko imię", niepełna nazwa jednostki) oraz kolumnę `email` do analizy.

**Architecture:** Pełny mirror podsystemu TYTUŁÓW ×2 (Approach C ze specu). `ImportPracownikowStopien`/`ImportPracownikowStanowisko` = kopie `ImportPracownikowTytul`; `_ReconcilerStopni`/`_ReconcilerStanowisk` = kopie `_ReconcilerTytulow`; `_rozstrzygnij_stopnie`/`_rozstrzygnij_stanowiska` = kopie `_rozstrzygnij_tytuly`; `WeryfikacjaStopniView`/`WeryfikacjaStanowiskView` = kopie `WeryfikacjaTytulowView`. Rozstrzyganie słowników leży w FAZIE STRUKTURY `integruj` (gated `zakres != ZAKRES_JEDNOSTKI`, przed early-exitem), a dopięcie FK do osób w FAZIE OSÓB (`ZAKRES_PELNY`). Polityki nadpisywania: stopień + stanowisko = **overwrite-if-different** (jak tytuł/funkcja), e-mail = **no-overwrite** (nowy autor → zapis, istniejący → nietknięty; poza predykatami zmian). Parser komórki zasila reconciler jednostek nowym parametrem `skrot_hint` (skrót z pliku → `skrot_sugerowany`, nadpisywany ZAWSZE przy re-analizie).

**Tech Stack:** Django, PostgreSQL trigram (`pg_trgm`), pytest + `@pytest.mark.django_db`, `model_bakery.baker`, pytest-testcontainers (PostgreSQL), ruff.

**Spec:** `docs/superpowers/specs/2026-07-12-import-slowniki-stopnie-stanowiska-design.md` (§10 model importu, §11 pipeline + polityki nadpisywania, §12 widoki/szablony/bramki; kontekst: §6 niepełna nazwa, §7 parser komórki, §8 nazwisko-imię).

**Zależność:** wymaga Planu 1 (`bpp.StopienSluzbowy`/`StanowiskoDydaktyczne` + FK `Autor.stopien_sluzbowy`/`Autor_Jednostka.stanowisko`) ORAZ Planu 2 (klasyfikatory `import_common.core.stopien`/`stanowisko`, `sklasyfikuj_jednostke_niepelna`, parsery `parsuj_komorke`/`rozbij_nazwisko_imie`, cele mapowania `email`/`stopień_służbowy`/`stanowisko_dydaktyczne`/`nazwisko_imię`/`komórka_złożona`/`nazwa_jednostki_niepelna`).

## Global Constraints

- **ZAWSZE `uv run`** przed każdą komendą Python (`uv run python …`, `uv run pytest …`). NIGDY gołe `python`/`pytest`.
- **Max długość linii: 88 znaków** (ruff).
- **Nazewnictwo (kolizja — KRYTYCZNE):** pole domenowe to `Autor_Jednostka.stanowisko` (Plan 1), ale w WARSTWIE IMPORTU klucz `stanowisko` jest zajęty przez legacy string FUNKCJI (`AutorForm.stanowisko` → `Funkcja_Autora`). Dlatego wszystkie NOWE identyfikatory stanowiska dydaktycznego w imporcie noszą nazwę `stanowisko_dydaktyczne`: cel mapowania (Plan 2), pole `AutorForm`, FK i `zrodlo_` na `ImportPracownikowRow`, param/atrybut w pipeline. **NIE nazywaj pola `ImportPracownikowRow` samym `stanowisko`.**
- **Migracja `import_pracownikow` = następny numer po `0022` → `0023`** (na branchu feature najnowsza to `0022_alter_importpracownikowrow_confidence`). Generuj przez `makemigrations`; NIE modyfikuj wydanych migracji.
- **NIE odświeżać baseline** (`baseline-sql/`) w tym branchu — refresh dopiero przy scalaniu do `dev`.
- **E-mail tolerancyjny:** `AutorForm.email` = `CharField` (nie `EmailField`), `required=False`. `analyze._przetworz_wiersz` przy niepoprawnym `AutorForm.full_clean()` rzuca `XLSParseError` bez per-wiersz recovery — jeden zepsuty adres w pliku kadrowym wywaliłby CAŁY run (spec §10/§17). `CharField` przyjmuje dowolny string bez walidacji formatu. Ścisłe (ale miękkie) czyszczenie + porównywarka e-mail = Plan 4.
- **Testy:** wyłącznie konwencje pytest (funkcje, brak `unittest.TestCase`), `baker.make`. DB dostarcza pytest-testcontainers (Docker; OrbStack: `export DOCKER_HOST=unix:///Users/mpasternak/.orbstack/run/docker.sock`).
- **Branch:** `feat/import-pracownikow-slowniki-stopnie-stanowiska` (już utworzony od `dev`).

## Roadmap (4 plany; ten dokument = Plan 3)

1. **Plan 1 — Fundament domenowy**: modele `StopienSluzbowy`/`StanowiskoDydaktyczne`, FK, migracja `bpp 0468`, admin, menu. ✅ założenie.
2. **Plan 2 — import_common + parsery + mapowanie**: klasyfikatory `stopien`/`stanowisko`/`jednostka_niepelna`, parsery komórki i „nazwisko imię", cele/synonimy mapowania + reguła kontekstowa `stopień` + walidacja, profil „ostatnio użyty". ✅ założenie.
3. **Plan 3 — Pipeline + ekrany weryfikacji** (ten plik): modele decyzji + migracja `import_pracownikow 0023`, `AutorForm`, reconcilery, analyze/integrate, widoki/szablony weryfikacji, bramki, wpięcie parserów + e-mail. → E2E weryfikacja słowników i dopięcie do osób.
4. **Plan 4 — Email (łagodna walidacja) + porównywarka + E2E + newsfragment**: kolumny porównywarki (plik-vs-baza) e-mail/stopień/stanowisko, ewentualne miękkie czyszczenie e-mail, pełny test E2E na `struktura.xlsx`, newsfragment. (Wpięcie parserów — komórka, nazwisko-imię, niepełna nazwa — należy do TEGO planu, Planu 3.)

---

## File Structure (Plan 3)

- Modify: `src/import_pracownikow/models.py` — `AutorForm` (+`email`/`stopień_służbowy`/`stanowisko_dydaktyczne`); `ImportPracownikow` (+toggle `tworz_brakujace_stopnie`/`tworz_brakujace_stanowiska`, właściwości `stopnie_wymagaja_rozstrzygniecia`/`stanowiska_wymagaja_rozstrzygniecia`, `liczniki_stopni`/`liczniki_stanowisk`, tekst `ZAKRES_STRUKTURA`); `ImportPracownikowRow` (+FK/status/zrodlo dla stopnia i stanowiska, predykaty, dopięcia w `_integrate_*`); nowe modele `ImportPracownikowStopien`/`ImportPracownikowStanowisko`.
- Create (via `makemigrations`): `src/import_pracownikow/migrations/0023_slowniki_stopnie_stanowiska.py`.
- Modify: `src/import_pracownikow/pipeline/analyze.py` — reconcilery/klasyfikatory słowników, preprocessing (komórka `skrot_hint` + oddział→wydział, `rozbij_nazwisko_imie`, `sklasyfikuj_jednostke_niepelna`, `email`), `struktura_bez_decyzji`.
- Modify: `src/import_pracownikow/pipeline/integrate.py` — `_rozstrzygnij_stopnie`/`_rozstrzygnij_stanowiska` + `_podlacz_*` + `unikalny_skrot_*`, dopięcie FK + e-mail przy nowym autorze, liczniki.
- Modify: `src/import_pracownikow/views.py` — `WeryfikacjaStopniView`/`WeryfikacjaStanowiskView`, bramka `ZatwierdzImportView`, kontekst `PodgladImportuView`.
- Modify: `src/import_pracownikow/urls.py` — trasy `stopnie`/`stanowiska`.
- Modify: `src/import_pracownikow/forms.py` — checkboxy `tworz_brakujace_stopnie`/`tworz_brakujace_stanowiska`.
- Create: `src/import_pracownikow/templates/import_pracownikow/weryfikacja_stopni.html`, `weryfikacja_stanowisk.html`.
- Modify: `src/import_pracownikow/templates/import_pracownikow/przeglad.html` — konteksty + bramki OR.
- Modify: `src/import_pracownikow/tests/test_przeglad.py` — aktualizacja istniejących asercji tekstów huba (POZYTYWNYCH i NEGATYWNYCH `not in`; zmiana etykiet w `przeglad.html`: „Zapisz jednostki + tytuły"→„Zapisz jednostki + słowniki", „Najpierw tytuły"→„Najpierw słowniki", „Utwórz brakujące tytuły"→„Utwórz brakujące słowniki").
- Testy: `src/import_pracownikow/tests/test_models_slowniki_decyzji.py`, `test_autorform_slowniki.py`, `test_analyze_slowniki.py`, `test_integrate_slowniki.py`, `test_views_slowniki.py`.

---

## Task 1: Modele decyzji + pola `ImportPracownikowRow` + toggle + migracja `0023`

**Files:**
- Test: `src/import_pracownikow/tests/test_models_slowniki_decyzji.py` (create)
- Modify: `src/import_pracownikow/models.py`
- Create (via makemigrations): `src/import_pracownikow/migrations/0023_slowniki_stopnie_stanowiska.py`

**Interfaces:**
- Consumes: `bpp.StopienSluzbowy`/`StanowiskoDydaktyczne` (Plan 1); `ImportPracownikowTytul` (wzorzec).
- Produces:
  - `ImportPracownikowStopien` (mirror `ImportPracownikowTytul`; pola: `parent` FK related_name=`stopnie_do_decyzji`, `nazwa_zrodlowa`, `tryb` TRYB_{ZGADYWANIE,BRAK}, `auto_stopien` FK `bpp.StopienSluzbowy`, `auto_similarity`, `nazwa_do_utworzenia`, `skrot_do_utworzenia`, `decyzja` DECYZJA_{AKCEPTUJ,MAPUJ,POMIN}, `wybrany_stopien` FK, `utworzony` FK; `unique_together=(parent,nazwa_zrodlowa)`).
  - `ImportPracownikowStanowisko` (mirror; `parent` related_name=`stanowiska_do_decyzji`, `auto_stanowisko`, `wybrane_stanowisko`, `utworzone` FK `bpp.StanowiskoDydaktyczne`).
  - `ImportPracownikow.tworz_brakujace_stopnie`/`tworz_brakujace_stanowiska` (`BooleanField(default=True)`).
  - `ImportPracownikow.ZAKRES_STRUKTURA` display + `zakres_integracji.help_text` — tekst rozszerzony o stopnie/stanowiska.
  - `ImportPracownikowRow.stopien` (FK `bpp.StopienSluzbowy`, SET_NULL, null), `stopien_status`, `zrodlo_stopnia` (FK `ImportPracownikowStopien`, SET_NULL, related_name=`wiersze_stopien`).
  - `ImportPracownikowRow.stanowisko_dydaktyczne` (FK `bpp.StanowiskoDydaktyczne`, SET_NULL, null), `stanowisko_dydaktyczne_status`, `zrodlo_stanowiska_dydaktycznego` (FK `ImportPracownikowStanowisko`, SET_NULL, related_name=`wiersze_stanowisko`).

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_models_slowniki_decyzji.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
)


@pytest.mark.django_db
def test_decyzja_stopnia_ma_relacje_i_stale():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt."
    )
    assert dec in imp.stopnie_do_decyzji.all()
    assert dec.tryb in {
        ImportPracownikowStopien.TRYB_ZGADYWANIE,
        ImportPracownikowStopien.TRYB_BRAK,
    } or dec.tryb is not None
    assert ImportPracownikowStopien.DECYZJA_AKCEPTUJ == "akceptuj"
    assert ImportPracownikowStopien.DECYZJA_POMIN == "pomin"


@pytest.mark.django_db
def test_decyzja_stanowiska_ma_relacje():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowStanowisko, parent=imp, nazwa_zrodlowa="adiunkt"
    )
    assert dec in imp.stanowiska_do_decyzji.all()


@pytest.mark.django_db
def test_row_ma_fk_stopnia_i_stanowiska_dydaktycznego():
    imp = baker.make(ImportPracownikow)
    st = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    sd = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    dec_st = baker.make(ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.")
    dec_sd = baker.make(
        ImportPracownikowStanowisko, parent=imp, nazwa_zrodlowa="adiunkt"
    )
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        stopien=st,
        stopien_status="twardy",
        zrodlo_stopnia=dec_st,
        stanowisko_dydaktyczne=sd,
        stanowisko_dydaktyczne_status="twardy",
        zrodlo_stanowiska_dydaktycznego=dec_sd,
    )
    row.refresh_from_db()
    assert row.stopien == st
    assert row.stanowisko_dydaktyczne == sd
    assert row in dec_st.wiersze_stopien.all()
    assert row in dec_sd.wiersze_stanowisko.all()


@pytest.mark.django_db
def test_toggle_slownikow_domyslnie_wlaczone():
    imp = baker.make(ImportPracownikow)
    assert imp.tworz_brakujace_stopnie is True
    assert imp.tworz_brakujace_stanowiska is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_models_slowniki_decyzji.py -v`
Expected: FAIL — `ImportError: cannot import name 'ImportPracownikowStopien'`.

- [ ] **Step 3: Dodaj modele decyzji (mirror `ImportPracownikowTytul`)**

Na końcu `src/import_pracownikow/models.py` (po `ImportPracownikowTytul`, przed `wiersz_kwalifikuje_do_przepiecia`) dodaj DWIE klasy — mirror `ImportPracownikowTytul` z podstawieniami. Dla `ImportPracownikowStopien` (rodzaj męski „stopień"):

```python
class ImportPracownikowStopien(models.Model):
    """Decyzja o jednym UNIKALNYM (znormalizowanym) stringu stopnia służbowego
    z pliku, którego nie da się dopasować dokładnie.

    Mirror ``ImportPracownikowTytul`` (Tytul→StopienSluzbowy, tytul→stopien).
    Deduplikowany po nazwie źródłowej; analiza wypełnia pola liczone
    (``tryb``/``auto_stopien``/``auto_similarity``), użytkownik ustawia wybór
    (``decyzja``/``wybrany_stopien``/``nazwa_do_utworzenia``/
    ``skrot_do_utworzenia``), integracja materializuje wynik do ``utworzony``.
    """

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nowy / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejący"),
        (DECYZJA_POMIN, "pomiń (nie ustawiaj stopnia tym wierszom)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="stopnie_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_stopien = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowany stopień",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    nazwa_do_utworzenia = models.CharField(
        "nazwa do utworzenia", max_length=512, blank=True, default=""
    )
    skrot_do_utworzenia = models.CharField(
        "skrót do utworzenia", max_length=128, blank=True, default=""
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrany_stopien = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrany istniejący stopień (mapuj)",
    )
    utworzony = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="stopień utworzony/rozstrzygnięty",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje stopni).",
    )

    class Meta:
        verbose_name = "decyzja o stopniu służbowym (import pracowników)"
        verbose_name_plural = "decyzje o stopniach służbowych (import pracowników)"
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"
```

Dla `ImportPracownikowStanowisko` — ten sam kod z podstawieniami `StopienSluzbowy`→`StanowiskoDydaktyczne`, `stopien`→`stanowisko` w nazwach relacji, oraz (rodzaj nijaki „stanowisko") polami `auto_stanowisko`/`wybrane_stanowisko`/`utworzone`:

```python
class ImportPracownikowStanowisko(models.Model):
    """Decyzja o jednym UNIKALNYM (znormalizowanym) stringu stanowiska
    dydaktycznego z pliku. Mirror ``ImportPracownikowStopien``
    (StopienSluzbowy→StanowiskoDydaktyczne)."""

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nowe / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejące"),
        (DECYZJA_POMIN, "pomiń (nie ustawiaj stanowiska tym wierszom)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="stanowiska_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowane stanowisko",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    nazwa_do_utworzenia = models.CharField(
        "nazwa do utworzenia", max_length=512, blank=True, default=""
    )
    skrot_do_utworzenia = models.CharField(
        "skrót do utworzenia", max_length=128, blank=True, default=""
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrane_stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrane istniejące stanowisko (mapuj)",
    )
    utworzone = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="stanowisko utworzone/rozstrzygnięte",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje stanowisk).",
    )

    class Meta:
        verbose_name = "decyzja o stanowisku dydaktycznym (import pracowników)"
        verbose_name_plural = (
            "decyzje o stanowiskach dydaktycznych (import pracowników)"
        )
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"
```

- [ ] **Step 4: Dodaj toggle na `ImportPracownikow` + tekst `ZAKRES_STRUKTURA`**

W `ImportPracownikow`, bezpośrednio pod polem `tworz_brakujace_tytuly` dodaj:

```python
    tworz_brakujace_stopnie = models.BooleanField(
        "Twórz brakujące stopnie służbowe",
        default=True,
        help_text="Gdy zaznaczone, stopnie służbowe nieobecne w bazie (i bez "
        "bliskiego dopasowania) trafiają na ekran weryfikacji do utworzenia. "
        "Gdy odznaczone — wiersze z niedopasowanym stopniem zostają bez stopnia.",
    )
    tworz_brakujace_stanowiska = models.BooleanField(
        "Twórz brakujące stanowiska dydaktyczne",
        default=True,
        help_text="Gdy zaznaczone, stanowiska dydaktyczne nieobecne w bazie (i "
        "bez bliskiego dopasowania) trafiają na ekran weryfikacji do utworzenia. "
        "Gdy odznaczone — wiersze z niedopasowanym stanowiskiem zostają bez "
        "stanowiska.",
    )
```

W `ZAKRES_CHOICES` zmień wpis:
```python
        (ZAKRES_STRUKTURA, "jednostki + tytuły (bez osób)"),
```
na:
```python
        (ZAKRES_STRUKTURA, "jednostki + tytuły + stopnie + stanowiska (bez osób)"),
```

W `zakres_integracji.help_text` zmień fragment „jednostki + tytuły (bez osób)" na „jednostki + tytuły + stopnie + stanowiska (bez osób)".

- [ ] **Step 5: Dodaj pola na `ImportPracownikowRow` (mirror `tytul`/`tytul_status`/`zrodlo_tytulu`)**

W `ImportPracownikowRow`, bezpośrednio pod blokiem `tytul`/`tytul_status`/`zrodlo_tytulu` dodaj:

```python
    stopien = models.ForeignKey(
        "bpp.StopienSluzbowy", on_delete=models.SET_NULL, null=True, blank=True
    )
    stopien_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_stopnia = models.ForeignKey(
        "ImportPracownikowStopien",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze_stopien",
        help_text="Decyzja o źródłowym stopniu służbowym (współdzielona przez "
        "wiersze o tej samej nazwie). Wypełniona, gdy stopień wymaga "
        "rozstrzygnięcia (utworzenie / mapowanie / auto-dopasowanie).",
    )
    stanowisko_dydaktyczne = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stanowisko_dydaktyczne_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_stanowiska_dydaktycznego = models.ForeignKey(
        "ImportPracownikowStanowisko",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze_stanowisko",
        help_text="Decyzja o źródłowym stanowisku dydaktycznym (współdzielona "
        "przez wiersze o tej samej nazwie). Wypełniona, gdy stanowisko wymaga "
        "rozstrzygnięcia (utworzenie / mapowanie / auto-dopasowanie).",
    )
```

- [ ] **Step 6: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name slowniki_stopnie_stanowiska`
Expected: utworzony `src/import_pracownikow/migrations/0023_slowniki_stopnie_stanowiska.py` z: `CreateModel` `ImportPracownikowStopien` + `ImportPracownikowStanowisko`; `AddField` `tworz_brakujace_stopnie`/`tworz_brakujace_stanowiska`; `AlterField` `zakres_integracji` (zmiana choices/help_text); `AddField` 6 pól na `ImportPracownikowRow`. Zależność: `0022_alter_importpracownikowrow_confidence`.

Zweryfikuj brak dryfu: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --check --dry-run` → „No changes detected".

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_models_slowniki_decyzji.py -v`
Expected: PASS (4 testy).

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/migrations/0023_slowniki_stopnie_stanowiska.py \
  src/import_pracownikow/tests/test_models_slowniki_decyzji.py
git commit -m "feat(import_pracownikow): modele decyzji + pola Row dla stopni i stanowisk"
```

---

## Task 2: `AutorForm` + właściwości bramek + liczniki + predykaty/dopięcia na `Row`

**Files:**
- Test: `src/import_pracownikow/tests/test_autorform_slowniki.py` (create)
- Modify: `src/import_pracownikow/models.py`

**Interfaces:**
- Consumes: modele decyzji (Task 1); `Autor.stopien_sluzbowy`/`Autor_Jednostka.stanowisko` (Plan 1); `_liczniki_decyzji` (istniejący).
- Produces:
  - `AutorForm.email`/`AutorForm.stopień_służbowy`/`AutorForm.stanowisko_dydaktyczne` (`CharField`, `required=False`).
  - `ImportPracownikow.stopnie_wymagaja_rozstrzygniecia`/`stanowiska_wymagaja_rozstrzygniecia` (property, mirror `tytuly_wymagaja_rozstrzygniecia`).
  - `ImportPracownikow.liczniki_stopni`/`liczniki_stanowisk` (mirror `liczniki_tytulow`).
  - `ImportPracownikowRow._check_autor_needs_update` += stopień (overwrite-if-different); `_check_autor_jednostka_needs_update` += stanowisko; `_integrate_autor` += `stopien_sluzbowy`; `_integrate_autor_jednostka` += `stanowisko`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_autorform_slowniki.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
)


def test_autorform_ma_nowe_pola_opcjonalne():
    for pole in ("email", "stopień_służbowy", "stanowisko_dydaktyczne"):
        assert pole in AutorForm.base_fields
        assert AutorForm.base_fields[pole].required is False


@pytest.mark.django_db
def test_stopnie_wymagaja_rozstrzygniecia():
    imp = baker.make(ImportPracownikow)
    assert imp.stopnie_wymagaja_rozstrzygniecia is False
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
        utworzony=None,
    )
    assert imp.stopnie_wymagaja_rozstrzygniecia is True


@pytest.mark.django_db
def test_stopnie_pomin_liczy_sie_jako_rozstrzygniete():
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_POMIN,
        utworzony=None,
    )
    assert imp.stopnie_wymagaja_rozstrzygniecia is False


@pytest.mark.django_db
def test_stanowiska_wymagaja_rozstrzygniecia():
    imp = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowStanowisko,
        parent=imp,
        nazwa_zrodlowa="adiunkt",
        decyzja=ImportPracownikowStanowisko.DECYZJA_AKCEPTUJ,
        utworzone=None,
    )
    assert imp.stanowiska_wymagaja_rozstrzygniecia is True


@pytest.mark.django_db
def test_predykat_stopnia_overwrite_if_different():
    imp = baker.make(ImportPracownikow)
    stary = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    nowy = baker.make("bpp.StopienSluzbowy", nazwa="brygadier", skrot="bryg.")
    autor = baker.make("bpp.Autor", stopien_sluzbowy=stary)
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        autor=autor,
        stopien=nowy,
    )
    assert row._check_autor_needs_update(row.dane_znormalizowane or {}) is True
    row.stopien = stary
    assert row._check_autor_needs_update(row.dane_znormalizowane or {}) is False


@pytest.mark.django_db
def test_predykat_stanowiska_overwrite_if_different():
    imp = baker.make(ImportPracownikow)
    sd = baker.make("bpp.StanowiskoDydaktyczne", nazwa="profesor", skrot="prof.")
    inne = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    # pmp=True neutralizuje predykat „podstawowe miejsce pracy" (#4) — bez tego
    # check_if_integration_needed() dawał True nawet BEZ implementacji stanowiska
    # (fałszywie-pozytywny test).
    aj = baker.make(
        "bpp.Autor_Jednostka", stanowisko=inne, podstawowe_miejsce_pracy=True
    )
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        autor=aj.autor,
        autor_jednostka=aj,
        stanowisko_dydaktyczne=sd,
        dane_znormalizowane={},
    )
    # inne stanowisko na wierszu niż na AJ → integracja potrzebna
    assert row.check_if_integration_needed() is True
    # to samo stanowisko (pmp=True, brak innych zmian) → predykat False
    aj.stanowisko = sd
    aj.save(update_fields=["stanowisko"])
    assert row.check_if_integration_needed() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_autorform_slowniki.py -v`
Expected: FAIL — brak pól `AutorForm`/property.

- [ ] **Step 3: Rozszerz `AutorForm`**

W `AutorForm` (mniej-więcej po `stanowisko`/`wymiar_etatu`) dodaj — `email` jako `CharField` (tolerancyjny; NIE `EmailField`, patrz Global Constraints):

```python
    email = forms.CharField(max_length=128, required=False)
    stopień_służbowy = forms.CharField(max_length=200, required=False)
    stanowisko_dydaktyczne = forms.CharField(max_length=200, required=False)
```

`max_length=128` (NIE 254) celowo — `Autor.email` to `EmailField(max_length=128)`, więc adres 129–254 znaków wywaliłby `Autor.objects.create` w `_przygotuj_nowego_autora` przez nieprzechwycony `DataError`. Pełne czyszczenie/ograniczenie e-maila robi Plan 4 (`oczysc_email`); do tego czasu string z pliku (przycięty do 128) ląduje wprost do `Autor.email`.

- [ ] **Step 4: Dodaj właściwości bramek (mirror `tytuly_wymagaja_rozstrzygniecia`)**

W `ImportPracownikow`, bezpośrednio pod `tytuly_wymagaja_rozstrzygniecia` dodaj (uwaga: dla stanowiska pole rozstrzygnięcia to `utworzone`, dla stopnia `utworzony`):

```python
    @property
    def stopnie_wymagaja_rozstrzygniecia(self):
        """Mirror ``tytuly_wymagaja_rozstrzygniecia`` — bramka: import osób
        (zakres pełny) nie może po cichu tworzyć stopni służbowych. ``pomin``
        liczymy jako rozstrzygnięte."""
        return (
            self.stopnie_do_decyzji.filter(utworzony__isnull=True)
            .exclude(decyzja=ImportPracownikowStopien.DECYZJA_POMIN)
            .exists()
        )

    @property
    def stanowiska_wymagaja_rozstrzygniecia(self):
        """Mirror ``tytuly_wymagaja_rozstrzygniecia`` dla stanowisk
        dydaktycznych (pole rozstrzygnięcia: ``utworzone``)."""
        return (
            self.stanowiska_do_decyzji.filter(utworzone__isnull=True)
            .exclude(decyzja=ImportPracownikowStanowisko.DECYZJA_POMIN)
            .exists()
        )
```

- [ ] **Step 5: Dodaj liczniki (mirror `liczniki_tytulow`)**

W `ImportPracownikow`, pod `liczniki_tytulow` dodaj:

```python
    def liczniki_stopni(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o stopniach służbowych (``utworzony__isnull=True``)."""
        return self._liczniki_decyzji(
            self.stopnie_do_decyzji.filter(utworzony__isnull=True),
            ImportPracownikowStopien.TRYB_BRAK,
            ImportPracownikowStopien.TRYB_ZGADYWANIE,
        )

    def liczniki_stanowisk(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o stanowiskach dydaktycznych (``utworzone__isnull=True``)."""
        return self._liczniki_decyzji(
            self.stanowiska_do_decyzji.filter(utworzone__isnull=True),
            ImportPracownikowStanowisko.TRYB_BRAK,
            ImportPracownikowStanowisko.TRYB_ZGADYWANIE,
        )
```

- [ ] **Step 6: Rozszerz predykaty i dopięcia na `ImportPracownikowRow`**

W `_check_autor_needs_update`, bezpośrednio przed `return False` (po bloku `tytul`) dodaj:

```python
        # Stopień służbowy — overwrite-if-different (mirror tytuł, spec §11.2).
        if (
            self.stopien_id is not None
            and self.stopien_id != a.stopien_sluzbowy_id
        ):
            return True
```

W `_check_autor_jednostka_needs_update`, do listy `checks` dodaj element:

```python
            # Stanowisko dydaktyczne — overwrite-if-different (mirror funkcja).
            self.stanowisko_dydaktyczne_id is not None
            and aj.stanowisko_id != self.stanowisko_dydaktyczne_id,
```

W `_integrate_autor`, bezpośrednio po bloku ustawiającym `a.tytul_id` (przed `a.save()`) dodaj:

```python
        if self.stopien_id is not None:
            if a.stopien_sluzbowy_id != self.stopien_id:
                a.stopien_sluzbowy_id = self.stopien_id
                self.log_zmian["autor"].append(
                    "stopień służbowy -> "
                    f"{self.stopien.skrot if self.stopien_id else 'brak'}"
                )
```

W `_integrate_autor_jednostka`, bezpośrednio po bloku `funkcja` (przed blokiem `grupa_pracownicza`) dodaj:

```python
        if (
            self.stanowisko_dydaktyczne_id is not None
            and aj.stanowisko_id != self.stanowisko_dydaktyczne_id
        ):
            aj.stanowisko_id = self.stanowisko_dydaktyczne_id
            self.log_zmian["autor_jednostka"].append(
                f"stanowisko dydaktyczne na {self.stanowisko_dydaktyczne}"
            )
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_autorform_slowniki.py -v`
Expected: PASS (6 testów).

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/tests/test_autorform_slowniki.py
git commit -m "feat(import_pracownikow): AutorForm + bramki/liczniki/predykaty słowników"
```

---

## Task 3: `analyze.py` — reconcilery, klasyfikatory, preprocessing (parsery + e-mail)

**Files:**
- Test: `src/import_pracownikow/tests/test_analyze_slowniki.py` (create)
- Modify: `src/import_pracownikow/pipeline/analyze.py`

**Interfaces:**
- Consumes: `import_common.core.stopien.{sklasyfikuj_stopien,zaproponuj_skrot_stopnia,STATUS_STOPIEN_*}`, `import_common.core.stanowisko.{sklasyfikuj_stanowisko,zaproponuj_skrot_stanowiska,STATUS_STANOWISKO_*}`, `import_common.core.jednostka.sklasyfikuj_jednostke_niepelna` (Plan 2); `import_pracownikow.parsers.jednostka_zlozona.parsuj_komorke`, `import_pracownikow.parsers.wartosci.rozbij_nazwisko_imie` (Plan 2); modele decyzji (Task 1); `bpp.models.Wydzial`.
- Produces:
  - `_ReconcilerJednostek.reconciluj(..., skrot_hint=None)` — `skrot_hint` nadpisuje `skrot_sugerowany` ZAWSZE (create i update).
  - `_ReconcilerStopni`/`_ReconcilerStanowisk` (mirror `_ReconcilerTytulow`); `_STATUS_NA_TRYB_STOPIEN`/`_STATUS_NA_TRYB_STANOWISKO`.
  - `_klasyfikuj_stopien_wiersza`/`_klasyfikuj_stanowisko_wiersza` (mirror `_klasyfikuj_tytul_wiersza`).
  - `_zrodlo_jednostki_wiersza(dane_form)` → `(nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, skrot_hint)` — rozgałęzia komórkę / niepełną nazwę / zwykłą nazwę.
  - `_przetworz_wiersz(..., reconciler_stopni=None, reconciler_stanowisk=None)` — Row dostaje `stopien`/`stanowisko_dydaktyczne` + status + zrodlo; `email` do `dane_znormalizowane`.
  - `analizuj` konstruuje 2 nowe reconcilery, woła `usun_stale`, rozszerza `struktura_bez_decyzji`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_analyze_slowniki.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowStopien,
)
from import_pracownikow.pipeline.analyze import (
    _ReconcilerJednostek,
    _klasyfikuj_stopien_wiersza,
    _zrodlo_jednostki_wiersza,
)


@pytest.mark.django_db
def test_klasyfikuj_stopien_twardy_wprost():
    imp = baker.make(ImportPracownikow)
    st = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, dec = _klasyfikuj_stopien_wiersza(imp, "kpt.", None)
    assert obj == st
    assert status == "twardy"
    assert dec is None


@pytest.mark.django_db
def test_klasyfikuj_stopien_brak_tworzy_decyzje():
    imp = baker.make(ImportPracownikow, tworz_brakujace_stopnie=True)
    from import_pracownikow.pipeline.analyze import _ReconcilerStopni

    rec = _ReconcilerStopni(imp)
    obj, status, dec = _klasyfikuj_stopien_wiersza(imp, "mł. bryg.", rec)
    assert obj is None
    assert status == "brak"
    assert isinstance(dec, ImportPracownikowStopien)
    assert dec.nazwa_zrodlowa == "mł. bryg."


@pytest.mark.django_db
def test_klasyfikuj_stopien_pusty_bez_decyzji():
    imp = baker.make(ImportPracownikow)
    assert _klasyfikuj_stopien_wiersza(imp, "", None) == (None, None, None)


@pytest.mark.django_db
def test_reconciler_jednostek_skrot_hint_nadpisuje_zawsze():
    imp = baker.make(ImportPracownikow)
    rec = _ReconcilerJednostek(imp)
    dec = rec.reconciluj(
        "Zakład X", "brak", None, None, skrot_hint="RW-1/1"
    )
    assert dec.skrot_sugerowany == "RW-1/1"
    # re-analiza z nowym hintem nadpisuje ZAWSZE (nie tylko gdy puste)
    dec2 = rec.reconciluj("Zakład X", "brak", None, None, skrot_hint="RW-9")
    assert dec2.pk == dec.pk
    dec2.refresh_from_db()
    assert dec2.skrot_sugerowany == "RW-9"


@pytest.mark.django_db
def test_zrodlo_jednostki_z_komorki_parsuje_i_daje_skrot_hint():
    baker.make("bpp.Wydzial", nazwa="WIBiOL — pełna", skrot="WIBiOL")
    dane = {"komórka_złożona": "RW-6/3 Zakład Nauk Społecznych WIBiOL"}
    nazwa, wydzial, _jed, _st, _sim, skrot_hint = _zrodlo_jednostki_wiersza(dane)
    assert nazwa == "Zakład Nauk Społecznych"
    assert skrot_hint == "RW-6/3"
    assert wydzial == "WIBiOL — pełna"  # oddział→Wydzial.skrot→nazwa


@pytest.mark.django_db
def test_zrodlo_jednostki_niepelna_uzywa_klasyfikatora_niepelnego():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    dane = {"nazwa_jednostki_niepelna": "Medyczny"}
    nazwa, _wydz, jed, status, _sim, skrot_hint = _zrodlo_jednostki_wiersza(dane)
    assert nazwa == "Medyczny"
    assert jed == j
    assert status == "zgadywanie"
    assert skrot_hint is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_analyze_slowniki.py -v`
Expected: FAIL — brak `_klasyfikuj_stopien_wiersza`/`_zrodlo_jednostki_wiersza`/`skrot_hint`.

- [ ] **Step 3: Rozszerz importy `analyze.py`**

Do bloku `from bpp.models import ...` dodaj `Wydzial`. Dodaj nowe importy:

```python
from bpp.models import Autor_Jednostka, Uczelnia, Wydzial
...
from import_common.core.jednostka import (
    STATUS_JEDNOSTKA_TWARDY,
    sklasyfikuj_jednostke,
    sklasyfikuj_jednostke_niepelna,
    zaproponuj_skrot,
)
from import_common.core.stanowisko import (
    STATUS_STANOWISKO_BRAK,
    STATUS_STANOWISKO_TWARDY,
    STATUS_STANOWISKO_ZGADYWANIE,
    sklasyfikuj_stanowisko,
    zaproponuj_skrot_stanowiska,
)
from import_common.core.stopien import (
    STATUS_STOPIEN_BRAK,
    STATUS_STOPIEN_TWARDY,
    STATUS_STOPIEN_ZGADYWANIE,
    sklasyfikuj_stopien,
    zaproponuj_skrot_stopnia,
)
```

Do importu z `import_pracownikow.models` dodaj `ImportPracownikowStanowisko`, `ImportPracownikowStopien`. Do importu z `import_pracownikow.parsers.wartosci` dodaj `rozbij_nazwisko_imie`. Dodaj:

```python
from import_pracownikow.parsers.jednostka_zlozona import parsuj_komorke
```

- [ ] **Step 4: Rozszerz `_ReconcilerJednostek.reconciluj` o `skrot_hint`**

Zamień sygnaturę i logikę skrótu (spec §7, „Luka 5": z `skrot_hint` nadpisujemy ZAWSZE, bo skrót jest liczony i nieedytowalny na ekranie jednostek):

```python
    def reconciluj(
        self, nazwa_zrodlowa, tryb, auto_jednostka, auto_similarity,
        skrot_hint=None,
    ):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        dec = self.parent.jednostki_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        skrot = (skrot_hint or "").strip()[:128]
        if dec is None:
            dec = ImportPracownikowJednostka.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb,
                auto_jednostka=auto_jednostka,
                auto_similarity=auto_similarity,
                skrot_sugerowany=skrot or zaproponuj_skrot(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb
            dec.auto_jednostka = auto_jednostka
            dec.auto_similarity = auto_similarity
            # skrot_hint (z komórki) nadpisuje ZAWSZE; bez hintu — dawne
            # zachowanie (uzupełnij tylko gdy puste).
            if skrot:
                dec.skrot_sugerowany = skrot
            elif not dec.skrot_sugerowany:
                dec.skrot_sugerowany = zaproponuj_skrot(nazwa_zrodlowa)
            dec.save(
                update_fields=[
                    "tryb",
                    "auto_jednostka",
                    "auto_similarity",
                    "skrot_sugerowany",
                ]
            )
        self.dotkniete.add(dec.pk)
        return dec
```

- [ ] **Step 5: Dodaj mapowania status→tryb + reconcilery słowników (mirror tytułów)**

Bezpośrednio po `_ReconcilerTytulow`/`_STATUS_NA_TRYB_TYTUL` dodaj (mirror z podstawieniami `tytul`→`stopien`/`stanowisko`):

```python
_STATUS_NA_TRYB_STOPIEN = {
    STATUS_STOPIEN_ZGADYWANIE: ImportPracownikowStopien.TRYB_ZGADYWANIE,
    STATUS_STOPIEN_BRAK: ImportPracownikowStopien.TRYB_BRAK,
}
_STATUS_NA_TRYB_STANOWISKO = {
    STATUS_STANOWISKO_ZGADYWANIE: ImportPracownikowStanowisko.TRYB_ZGADYWANIE,
    STATUS_STANOWISKO_BRAK: ImportPracownikowStanowisko.TRYB_BRAK,
}


class _ReconcilerStopni:
    """Mirror ``_ReconcilerTytulow`` dla ``ImportPracownikowStopien``."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_stopien, sim):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        tryb_model = _STATUS_NA_TRYB_STOPIEN[tryb]
        dec = self.parent.stopnie_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowStopien.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb_model,
                auto_stopien=auto_stopien,
                auto_similarity=sim,
                nazwa_do_utworzenia=nazwa_zrodlowa[:512],
                skrot_do_utworzenia=zaproponuj_skrot_stopnia(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb_model
            dec.auto_stopien = auto_stopien
            dec.auto_similarity = sim
            dec.save(update_fields=["tryb", "auto_stopien", "auto_similarity"])
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.stopnie_do_decyzji.exclude(pk__in=self.dotkniete).delete()


class _ReconcilerStanowisk:
    """Mirror ``_ReconcilerStopni`` dla ``ImportPracownikowStanowisko``."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_stanowisko, sim):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        tryb_model = _STATUS_NA_TRYB_STANOWISKO[tryb]
        dec = self.parent.stanowiska_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowStanowisko.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb_model,
                auto_stanowisko=auto_stanowisko,
                auto_similarity=sim,
                nazwa_do_utworzenia=nazwa_zrodlowa[:512],
                skrot_do_utworzenia=zaproponuj_skrot_stanowiska(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb_model
            dec.auto_stanowisko = auto_stanowisko
            dec.auto_similarity = sim
            dec.save(
                update_fields=["tryb", "auto_stanowisko", "auto_similarity"]
            )
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.stanowiska_do_decyzji.exclude(pk__in=self.dotkniete).delete()
```

- [ ] **Step 6: Dodaj klasyfikatory wiersza (mirror `_klasyfikuj_tytul_wiersza`)**

Bezpośrednio po `_klasyfikuj_tytul_wiersza` dodaj:

```python
def _klasyfikuj_stopien_wiersza(parent, stopien_str, reconciler_stopni):
    """Mirror ``_klasyfikuj_tytul_wiersza`` dla stopni służbowych. Gated
    ``parent.tworz_brakujace_stopnie``. Zwraca ``(stopien|None, status|None,
    decyzja|None)``."""
    if not stopien_str:
        return None, None, None
    obj, status, sim = sklasyfikuj_stopien(stopien_str)
    if status == STATUS_STOPIEN_TWARDY:
        return obj, status, None
    tworzy = status == STATUS_STOPIEN_ZGADYWANIE or (
        status == STATUS_STOPIEN_BRAK and parent.tworz_brakujace_stopnie
    )
    if tworzy:
        decyzja = None
        if reconciler_stopni is not None:
            decyzja = reconciler_stopni.reconciluj(stopien_str, status, obj, sim)
        return None, status, decyzja
    return None, STATUS_STOPIEN_BRAK, None


def _klasyfikuj_stanowisko_wiersza(parent, stanowisko_str, reconciler_stanowisk):
    """Mirror ``_klasyfikuj_stopien_wiersza`` dla stanowisk dydaktycznych.
    Gated ``parent.tworz_brakujace_stanowiska``."""
    if not stanowisko_str:
        return None, None, None
    obj, status, sim = sklasyfikuj_stanowisko(stanowisko_str)
    if status == STATUS_STANOWISKO_TWARDY:
        return obj, status, None
    tworzy = status == STATUS_STANOWISKO_ZGADYWANIE or (
        status == STATUS_STANOWISKO_BRAK and parent.tworz_brakujace_stanowiska
    )
    if tworzy:
        decyzja = None
        if reconciler_stanowisk is not None:
            decyzja = reconciler_stanowisk.reconciluj(
                stanowisko_str, status, obj, sim
            )
        return None, status, decyzja
    return None, STATUS_STANOWISKO_BRAK, None
```

- [ ] **Step 7: Dodaj helper źródła jednostki (komórka / niepełna / zwykła)**

Bezpośrednio przed `_przetworz_wiersz` dodaj:

```python
def _zrodlo_jednostki_wiersza(dane_form):
    """Rozstrzyga, skąd wziąć nazwę jednostki i jak ją sklasyfikować (spec §6/§7).

    Zwraca ``(nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim,
    skrot_hint)``. Trzy tory (priorytet):

    1. ``komórka_złożona`` → ``parsuj_komorke``: nazwa = czysta nazwa z parsera,
       ``skrot_hint`` = skrót z pliku (zasili ``Jednostka.skrot`` przy tworzeniu),
       oddział rozwiązany przez ``Wydzial.skrot`` → jego NAZWA jako wydzial-hint
       (``matchuj_wydzial`` robi tylko ``nazwa__iexact``; §7 finding #6).
       Klasyfikacja zwykłym ``sklasyfikuj_jednostke`` po skrócie/nazwie.
    2. ``nazwa_jednostki_niepelna`` (i brak ``nazwa_jednostki``) →
       ``sklasyfikuj_jednostke_niepelna`` (icontains/trigram, zawsze do
       weryfikacji). ``skrot_hint`` = None.
    3. zwykła ``nazwa_jednostki`` → dotychczasowy ``sklasyfikuj_jednostke``.

    Pusta/za długa (>512) nazwa → traktowana jak brak (wiersz pominięty).
    """
    wydzial = str(dane_form.get("wydział") or "").strip() or None
    skrot_hint = None

    komorka = str(dane_form.get("komórka_złożona") or "").strip()
    niepelna = str(dane_form.get("nazwa_jednostki_niepelna") or "").strip()
    zwykla = str(dane_form.get("nazwa_jednostki") or "").strip()

    if komorka:
        wynik = parsuj_komorke(komorka)
        nazwa = wynik["nazwa"]
        skrot_hint = wynik["skrot"]
        oddzial = wynik["oddzial"]
        if oddzial:
            w = Wydzial.objects.filter(skrot=oddzial).first()
            if w is not None:
                wydzial = w.nazwa
        nazwa_do_klas = nazwa if 0 < len(nazwa) <= 512 else ""
        jednostka, jed_status, jed_sim = sklasyfikuj_jednostke(
            nazwa_do_klas, wydzial
        )
        return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, skrot_hint

    if niepelna and not zwykla:
        nazwa_do_klas = niepelna if 0 < len(niepelna) <= 512 else ""
        jednostka, jed_status, jed_sim = sklasyfikuj_jednostke_niepelna(
            nazwa_do_klas, wydzial
        )
        return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, None

    nazwa_do_klas = zwykla if 0 < len(zwykla) <= 512 else ""
    jednostka, jed_status, jed_sim = sklasyfikuj_jednostke(nazwa_do_klas, wydzial)
    return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, None
```

- [ ] **Step 8: Wepnij w `_przetworz_wiersz` — preprocessing, klasyfikacja słowników, Row**

W sygnaturze `_przetworz_wiersz` dodaj parametry:

```python
def _przetworz_wiersz(
    parent,
    elem,
    parser_ctx=None,
    *,
    reconciler=None,
    reconciler_tytulow=None,
    reconciler_stopni=None,
    reconciler_stanowisk=None,
    tworz_brakujace=True,
):
```

W ciele, po `rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)` dodaj split „nazwisko imię" (no-op gdy brak klucza):

```python
    rozbij_nazwisko_imie(dane_form)
```

Zamień blok liczenia jednostki (od `nazwa_jed = ...` do wywołania `sklasyfikuj_jednostke(...)`) na jedno wywołanie helpera:

```python
    (
        nazwa_do_klas,
        wydzial,
        jednostka,
        jed_status,
        jed_sim,
        skrot_hint,
    ) = _zrodlo_jednostki_wiersza(dane_form)
    jednostka_odroczona = jed_status != STATUS_JEDNOSTKA_TWARDY
```

W wywołaniu `reconciler.reconciluj(...)` (decyzja jednostki) przekaż `skrot_hint`:

```python
            decyzja_jednostki = reconciler.reconciluj(
                nazwa_do_klas, jed_status, jednostka, jed_sim,
                skrot_hint=skrot_hint,
            )
```

Po `_klasyfikuj_tytul_wiersza(...)` dodaj klasyfikację słowników i wyciągnięcie e-maila:

```python
    row_stopien, row_stopien_status, row_zrodlo_stopnia = _klasyfikuj_stopien_wiersza(
        parent, data.get("stopień_służbowy"), reconciler_stopni
    )
    (
        row_stanowisko,
        row_stanowisko_status,
        row_zrodlo_stanowiska,
    ) = _klasyfikuj_stanowisko_wiersza(
        parent, data.get("stanowisko_dydaktyczne"), reconciler_stanowisk
    )
```

W konstruktorze `ImportPracownikowRow(...)` dodaj nowe pola (obok `tytul`/`tytul_status`/`zrodlo_tytulu`):

```python
        stopien=row_stopien,
        stopien_status=row_stopien_status,
        zrodlo_stopnia=row_zrodlo_stopnia,
        stanowisko_dydaktyczne=row_stanowisko,
        stanowisko_dydaktyczne_status=row_stanowisko_status,
        zrodlo_stanowiska_dydaktycznego=row_zrodlo_stanowiska,
```

`email` trafia do `dane_znormalizowane` naturalnie: `_dane_znormalizowane_z_parserem` kopiuje CAŁE `autor_form.cleaned_data`, w którym jest już klucz `email` (nowe pole `AutorForm`). Bez dodatkowego kodu — dopisz jedynie komentarz przy konstruktorze `dane_znormalizowane=...`:

```python
        # dane_znormalizowane zawiera też `email` (nowe pole AutorForm) —
        # zapisywany do porównywarki (Plan 4) i do zapisu przy tworzeniu autora
        # (integrate; e-mail = no-overwrite dla istniejących, spec §11.2).
```

- [ ] **Step 9: Wepnij reconcilery w `analizuj` + rozszerz `struktura_bez_decyzji`**

W `analizuj`, po `reconciler_tytulow = _ReconcilerTytulow(parent)` dodaj:

```python
    reconciler_stopni = _ReconcilerStopni(parent)
    reconciler_stanowisk = _ReconcilerStanowisk(parent)
```

W wywołaniu `_przetworz_wiersz(...)` w pętli dodaj argumenty:

```python
            reconciler_stopni=reconciler_stopni,
            reconciler_stanowisk=reconciler_stanowisk,
```

Po `reconciler_tytulow.usun_stale()` dodaj:

```python
    reconciler_stopni.usun_stale()
    reconciler_stanowisk.usun_stale()
```

Rozszerz `struktura_bez_decyzji` (auto-skip Krok 1→2; spec §11.1 finding #1) o nowe słowniki:

```python
    struktura_bez_decyzji = (
        not parent.jednostki_do_decyzji.exists()
        and not parent.tytuly_do_decyzji.exists()
        and not parent.stopnie_do_decyzji.exists()
        and not parent.stanowiska_do_decyzji.exists()
    )
```

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_analyze_slowniki.py -v`
Expected: PASS (6 testów).

- [ ] **Step 11: Regresja analizy tytułów**

Run: `uv run pytest src/import_pracownikow/tests/ -k "analyze or tytul" -q`
Expected: bez regresji (istniejące testy analizy/tytułów zielone).

- [ ] **Step 12: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_analyze_slowniki.py
git commit -m "feat(import_pracownikow): analyze — słowniki + parsery komórki/nazwiska + email"
```

---

## Task 4: `integrate.py` — rozstrzyganie słowników + dopięcie FK + e-mail + liczniki

**Files:**
- Test: `src/import_pracownikow/tests/test_integrate_slowniki.py` (create)
- Modify: `src/import_pracownikow/pipeline/integrate.py`

**Interfaces:**
- Consumes: `bpp.StopienSluzbowy`/`StanowiskoDydaktyczne`; `import_common.core.stopien.zaproponuj_skrot_stopnia`, `import_common.core.stanowisko.zaproponuj_skrot_stanowiska`; modele decyzji (Task 1); predykaty/dopięcia (Task 2).
- Produces:
  - `unikalny_skrot_stopnia`/`unikalny_skrot_stanowiska` (mirror `unikalny_skrot_tytulu`, na `StopienSluzbowy.skrot`/`StanowiskoDydaktyczne.skrot`).
  - `_rozstrzygnij_jeden_stopien`/`_rozstrzygnij_jedno_stanowisko` (mirror `_rozstrzygnij_jeden_tytul`).
  - `_podlacz_wiersze_do_stopni`/`_podlacz_wiersze_do_stanowisk` (mirror `_podlacz_wiersze_do_tytulow`; stopień gated `autor_id`, stanowisko gated `autor_id`+`autor_jednostka_id`).
  - `_rozstrzygnij_stopnie`/`_rozstrzygnij_stanowiska` (mirror `_rozstrzygnij_tytuly`) — zwracają liczbę utworzonych.
  - `integruj` — gałąź struktury woła nowe rozstrzyganie (gated `zakres != ZAKRES_JEDNOSTKI`), liczniki `utworzono_stopni`/`utworzono_stanowisk` w OBU `p.result(...)`.
  - `_materializuj_diff` — `get_or_create(Autor_Jednostka, defaults+={"stanowisko": row.stanowisko_dydaktyczne})`.
  - `_przygotuj_nowego_autora` — `Autor.objects.create(..., stopien_sluzbowy=row.stopien, email=<z dane>)`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_integrate_slowniki.py`:

```python
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import StanowiskoDydaktyczne, StopienSluzbowy
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStopien,
)
from import_pracownikow.pipeline.integrate import (
    _przygotuj_nowego_autora,
    _rozstrzygnij_stopnie,
    unikalny_skrot_stopnia,
)


@pytest.mark.django_db
def test_unikalny_skrot_stopnia_sufiks():
    baker.make(StopienSluzbowy, nazwa="kapitan", skrot="kpt.")
    assert unikalny_skrot_stopnia("kpt.") != "kpt."


@pytest.mark.django_db
def test_rozstrzygnij_stopnie_tworzy_i_podlacza():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="mł. bryg.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
        nazwa_do_utworzenia="mł. bryg.",
        skrot_do_utworzenia="mł. bryg.",
        utworzony=None,
    )
    row = baker.make(
        ImportPracownikowRow, parent=imp, zmiany_potrzebne=False,
        zrodlo_stopnia=dec,
    )
    utworzono = _rozstrzygnij_stopnie(imp, MockProgress(imp))
    assert utworzono == 1
    dec.refresh_from_db()
    row.refresh_from_db()
    assert dec.utworzony is not None
    assert row.stopien == dec.utworzony


@pytest.mark.django_db
def test_nowy_autor_dostaje_stopien_i_email():
    imp = baker.make(ImportPracownikow)
    st = baker.make(StopienSluzbowy, nazwa="brygadier", skrot="bryg.")
    jed = baker.make("bpp.Jednostka")
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        confidence="brak",
        utworz_nowego=True,
        autor=None,
        jednostka=jed,
        stopien=st,
        dane_znormalizowane={
            "nazwisko": "Kowalski",
            "imię": "Jan",
            "email": "jan@example.org",
        },
        diff_do_utworzenia={},
    )
    assert _przygotuj_nowego_autora(row, {}) is True
    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.stopien_sluzbowy == st
    assert row.autor.email == "jan@example.org"


@pytest.mark.django_db
def test_istniejacy_autor_email_no_overwrite():
    imp = baker.make(ImportPracownikow)
    autor = baker.make("bpp.Autor", email="stary@example.org")
    aj = baker.make("bpp.Autor_Jednostka", autor=autor)
    sd = baker.make(StanowiskoDydaktyczne, nazwa="adiunkt", skrot="ad.")
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=True,
        autor=autor,
        autor_jednostka=aj,
        jednostka=aj.jednostka,
        stanowisko_dydaktyczne=sd,
        dane_znormalizowane={"email": "nowy@example.org"},
        diff_do_utworzenia={},
    )
    row.integrate()
    autor.refresh_from_db()
    aj.refresh_from_db()
    assert autor.email == "stary@example.org"  # NIE nadpisano
    assert aj.stanowisko == sd  # stanowisko overwrite-if-different
```

Uwaga (progress do testów): używamy istniejącego `MockProgress` z
`liveops.testing` (`from liveops.testing import MockProgress`,
`MockProgress(imp)`) — TEGO SAMEGO, którego używa reszta suity importu (np.
Plan 4 `test_analyze_email.py`/`test_e2e_slowniki.py`, wzorzec
`test_e2e_jednostki.py`). NIE wprowadzaj własnego fixture'u `dummy_progress`
ani drugiego mocka progressu — jeden mechanizm dla całej suity.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_integrate_slowniki.py -v`
Expected: FAIL — brak `_rozstrzygnij_stopnie`/`unikalny_skrot_stopnia`; nowy autor bez stopnia/e-maila.

- [ ] **Step 3: Rozszerz importy `integrate.py`**

Do `from bpp.models import (...)` dodaj `StanowiskoDydaktyczne`, `StopienSluzbowy`. Dodaj:

```python
from import_common.core.stanowisko import zaproponuj_skrot_stanowiska
from import_common.core.stopien import zaproponuj_skrot_stopnia
```

Do importu z `import_pracownikow.models` dodaj `ImportPracownikowStanowisko`, `ImportPracownikowStopien`.

- [ ] **Step 4: Dodaj `unikalny_skrot_*` (mirror `unikalny_skrot_tytulu`)**

Bezpośrednio po `unikalny_skrot_tytulu` dodaj dwie kopie z podstawieniem modelu i fallbacku bazy:

```python
def unikalny_skrot_stopnia(base, zajete=None):
    """Mirror ``unikalny_skrot_tytulu`` na ``StopienSluzbowy.skrot``."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "ST"

    def wolny(s):
        return s not in zajete and not StopienSluzbowy.objects.filter(
            skrot=s
        ).exists()

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1


def unikalny_skrot_stanowiska(base, zajete=None):
    """Mirror ``unikalny_skrot_stopnia`` na ``StanowiskoDydaktyczne.skrot``."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "SD"

    def wolny(s):
        return s not in zajete and not StanowiskoDydaktyczne.objects.filter(
            skrot=s
        ).exists()

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1
```

- [ ] **Step 5: Dodaj rozstrzyganie jednej decyzji + podłączanie wierszy + fazę (mirror tytułów)**

Bezpośrednio po `_rozstrzygnij_tytuly` dodaj sekcję STOPNI (mirror `_rozstrzygnij_jeden_tytul`/`_podlacz_wiersze_do_tytulow`/`_rozstrzygnij_tytuly` z podstawieniami `Tytul`→`StopienSluzbowy`, `tytul`→`stopien`, `utworzony`→`utworzony`, `zaproponuj_skrot_tytulu`→`zaproponuj_skrot_stopnia`, `unikalny_skrot_tytulu`→`unikalny_skrot_stopnia`, related `zrodlo_tytulu`→`zrodlo_stopnia`):

```python
def _rozstrzygnij_jeden_stopien(dec, zajete_nazwy, zajete_skroty, p):
    """Mirror ``_rozstrzygnij_jeden_tytul`` dla ``StopienSluzbowy``."""
    if dec.utworzony_id is not None:
        return dec.utworzony, False
    if dec.decyzja == ImportPracownikowStopien.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowStopien.DECYZJA_MAPUJ:
        return dec.wybrany_stopien, False
    if dec.tryb == ImportPracownikowStopien.TRYB_ZGADYWANIE:
        return dec.auto_stopien, False

    nazwa = (dec.nazwa_do_utworzenia or "").strip() or (
        dec.nazwa_zrodlowa or ""
    ).strip()
    nazwa = nazwa[:512]
    istniejacy = StopienSluzbowy.objects.filter(nazwa__iexact=nazwa).first()
    if istniejacy is not None:
        return istniejacy, False
    baza_skrotu = dec.skrot_do_utworzenia or zaproponuj_skrot_stopnia(
        dec.nazwa_zrodlowa
    )
    skrot = unikalny_skrot_stopnia(baza_skrotu, zajete_skroty)
    nowy = StopienSluzbowy.objects.create(nazwa=nazwa, skrot=skrot)
    zajete_nazwy.add(nazwa)
    zajete_skroty.add(skrot)
    return nowy, True


def _podlacz_wiersze_do_stopni(parent):
    """Mirror ``_podlacz_wiersze_do_tytulow`` — ``row.stopien``. Recompute
    ``zmiany_potrzebne`` (monotone) TYLKO gdy autor ustawiony (stopień jest na
    Autorze; ``check_if_integration_needed`` sięga ``self.autor``)."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_stopnia__isnull=False
    ).select_related("zrodlo_stopnia", "autor", "autor_jednostka"):
        row.stopien = row.zrodlo_stopnia.utworzony
        if row.autor_id is not None:
            row.zmiany_potrzebne = (
                bool(row.diff_do_utworzenia)
                or row.check_if_integration_needed()
                or row.zmiany_potrzebne
            )
            row.save(update_fields=["stopien", "zmiany_potrzebne"])
        else:
            row.save(update_fields=["stopien"])


def _rozstrzygnij_stopnie(parent, p):
    """Mirror ``_rozstrzygnij_tytuly`` dla stopni służbowych."""
    zajete_nazwy = set()
    zajete_skroty = set()
    utworzono = 0
    for dec in parent.stopnie_do_decyzji.all():
        with transaction.atomic():
            stopien, utworzono_nowy = _rozstrzygnij_jeden_stopien(
                dec, zajete_nazwy, zajete_skroty, p
            )
            if stopien is not None and dec.utworzony_id != stopien.pk:
                dec.utworzony = stopien
                dec.save(update_fields=["utworzony"])
        if utworzono_nowy:
            utworzono += 1
    _podlacz_wiersze_do_stopni(parent)
    return utworzono
```

Analogicznie dla STANOWISK — te same trzy funkcje z podstawieniami `StopienSluzbowy`→`StanowiskoDydaktyczne`, `stopien`→`stanowisko`, `ImportPracownikowStopien`→`ImportPracownikowStanowisko`, `zrodlo_stopnia`→`zrodlo_stanowiska_dydaktycznego`, `unikalny_skrot_stopnia`→`unikalny_skrot_stanowiska`, `zaproponuj_skrot_stopnia`→`zaproponuj_skrot_stanowiska`. Uwaga na pola decyzji stanowiska (`wybrane_stanowisko`, `auto_stanowisko`, `utworzone`) oraz — stanowisko jest na **Autor_Jednostka**, więc `_podlacz_wiersze_do_stanowisk` recompute gated `autor_id is not None AND autor_jednostka_id is not None` (jak tytuł):

```python
def _rozstrzygnij_jedno_stanowisko(dec, zajete_nazwy, zajete_skroty, p):
    """Mirror ``_rozstrzygnij_jeden_stopien`` dla ``StanowiskoDydaktyczne``."""
    if dec.utworzone_id is not None:
        return dec.utworzone, False
    if dec.decyzja == ImportPracownikowStanowisko.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowStanowisko.DECYZJA_MAPUJ:
        return dec.wybrane_stanowisko, False
    if dec.tryb == ImportPracownikowStanowisko.TRYB_ZGADYWANIE:
        return dec.auto_stanowisko, False

    nazwa = (dec.nazwa_do_utworzenia or "").strip() or (
        dec.nazwa_zrodlowa or ""
    ).strip()
    nazwa = nazwa[:512]
    istniejace = StanowiskoDydaktyczne.objects.filter(nazwa__iexact=nazwa).first()
    if istniejace is not None:
        return istniejace, False
    baza_skrotu = dec.skrot_do_utworzenia or zaproponuj_skrot_stanowiska(
        dec.nazwa_zrodlowa
    )
    skrot = unikalny_skrot_stanowiska(baza_skrotu, zajete_skroty)
    nowe = StanowiskoDydaktyczne.objects.create(nazwa=nazwa, skrot=skrot)
    zajete_nazwy.add(nazwa)
    zajete_skroty.add(skrot)
    return nowe, True


def _podlacz_wiersze_do_stanowisk(parent):
    """Mirror ``_podlacz_wiersze_do_tytulow`` — ``row.stanowisko_dydaktyczne``.
    Stanowisko jest na Autor_Jednostka, więc recompute gated jak tytuł
    (autor + autor_jednostka ustawione)."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_stanowiska_dydaktycznego__isnull=False
    ).select_related(
        "zrodlo_stanowiska_dydaktycznego", "autor", "autor_jednostka"
    ):
        row.stanowisko_dydaktyczne = row.zrodlo_stanowiska_dydaktycznego.utworzone
        if row.autor_id is not None and row.autor_jednostka_id is not None:
            row.zmiany_potrzebne = (
                bool(row.diff_do_utworzenia)
                or row.check_if_integration_needed()
                or row.zmiany_potrzebne
            )
            row.save(
                update_fields=["stanowisko_dydaktyczne", "zmiany_potrzebne"]
            )
        else:
            row.save(update_fields=["stanowisko_dydaktyczne"])


def _rozstrzygnij_stanowiska(parent, p):
    """Mirror ``_rozstrzygnij_stopnie`` dla stanowisk dydaktycznych."""
    zajete_nazwy = set()
    zajete_skroty = set()
    utworzono = 0
    for dec in parent.stanowiska_do_decyzji.all():
        with transaction.atomic():
            stanowisko, utworzono_nowe = _rozstrzygnij_jedno_stanowisko(
                dec, zajete_nazwy, zajete_skroty, p
            )
            if stanowisko is not None and dec.utworzone_id != stanowisko.pk:
                dec.utworzone = stanowisko
                dec.save(update_fields=["utworzone"])
        if utworzono_nowe:
            utworzono += 1
    _podlacz_wiersze_do_stanowisk(parent)
    return utworzono
```

- [ ] **Step 6: Wepnij fazę słowników + liczniki w `integruj`**

W `integruj`, zaraz po bloku `utworzono_tytulow` (FAZA 0.5) rozszerz gałąź `zakres != ZAKRES_JEDNOSTKI`:

```python
    utworzono_tytulow = 0
    utworzono_stopni = 0
    utworzono_stanowisk = 0
    if zakres != ImportPracownikow.ZAKRES_JEDNOSTKI:
        utworzono_tytulow = _rozstrzygnij_tytuly(parent, p)
        # FAZA 0.6/0.7: stopnie + stanowiska (słowniki, jak tytuły) — PRZED
        # snapshotem/fazą osób (autorzy czytają row.stopien; AJ row.stanowisko).
        utworzono_stopni = _rozstrzygnij_stopnie(parent, p)
        utworzono_stanowisk = _rozstrzygnij_stanowiska(parent, p)
```

W bloku early-exit zakresu strukturalnego (`if zakres in (ZAKRES_JEDNOSTKI, ZAKRES_STRUKTURA)`), do `p.result({...})` dodaj:

```python
                "utworzono_stopni": utworzono_stopni,
                "utworzono_stanowisk": utworzono_stanowisk,
```

W finalnym `p.result({...})` (koniec `integruj`, zakres PELNY) dodaj te same dwa klucze:

```python
            "utworzono_stopni": utworzono_stopni,
            "utworzono_stanowisk": utworzono_stanowisk,
```

- [ ] **Step 7: Dopnij stanowisko przy materializacji AJ + stopień/e-mail przy nowym autorze**

W `_materializuj_diff`, w gałęzi `if "autor_jednostka" in diff:` rozszerz `defaults`:

```python
        row.autor_jednostka, _ = Autor_Jednostka.objects.get_or_create(
            autor_id=diff["autor_jednostka"]["autor"],
            jednostka_id=diff["autor_jednostka"]["jednostka"],
            defaults={
                "funkcja": row.funkcja_autora,
                "stanowisko": row.stanowisko_dydaktyczne,
            },
        )
```

W `_przygotuj_nowego_autora`, w wywołaniu `Autor.objects.create(...)` dodaj stopień i e-mail (e-mail = no-overwrite dotyczy tylko ISTNIEJĄCYCH; nowy autor zapisuje z pliku, spec §11.2):

```python
    dane = row.dane_znormalizowane or {}
    nazwisko = (dane.get("nazwisko") or "").strip()
    imiona = (dane.get("imię") or "").strip()
    email = (dane.get("email") or "").strip()
    if not imiona:
        return False
    klucz = (nazwisko, imiona, row.tytul_id)
    ...
        if utworzono:
            autor = Autor.objects.create(
                nazwisko=nazwisko,
                imiona=imiona,
                tytul=row.tytul,
                stopien_sluzbowy=row.stopien,
                email=email,
            )
            cache[klucz] = autor
```

(Uwaga: dedup-cache `(nazwisko, imiona, tytul_id)` bez zmian — dwa wiersze tej samej osoby z RÓŻNYM stopniem/e-mailem reużyją pierwszego autora; świadome ograniczenie, spec §17.)

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_integrate_slowniki.py -v`
Expected: PASS (4 testy).

- [ ] **Step 9: Regresja integracji tytułów**

Run: `uv run pytest src/import_pracownikow/tests/ -k "integrate or tytul" -q`
Expected: bez regresji.

- [ ] **Step 10: Commit**

```bash
git add src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/tests/test_integrate_slowniki.py \
  src/import_pracownikow/tests/conftest.py
git commit -m "feat(import_pracownikow): integrate — rozstrzyganie słowników + dopięcie FK/email"
```

---

## Task 5: Widoki weryfikacji + bramka Zatwierdź + trasy + toggle w `MapowanieForm`

**Files:**
- Test: `src/import_pracownikow/tests/test_views_slowniki.py` (create)
- Modify: `src/import_pracownikow/views.py`
- Modify: `src/import_pracownikow/urls.py`
- Modify: `src/import_pracownikow/forms.py`

**Interfaces:**
- Consumes: `WeryfikacjaTytulowView`/`ZatwierdzImportView` (wzorzec); `StopienSluzbowy`/`StanowiskoDydaktyczne`; modele decyzji.
- Produces:
  - `WeryfikacjaStopniView`/`WeryfikacjaStanowiskView` (mirror `WeryfikacjaTytulowView`).
  - `urls.py`: `path("<uuid:pk>/stopnie/", ..., name="stopnie")`, `path("<uuid:pk>/stanowiska/", ..., name="stanowiska")`.
  - `ZatwierdzImportView` — bramka PELNY rozszerzona o `stopnie_wymagaja_rozstrzygniecia`/`stanowiska_wymagaja_rozstrzygniecia`.
  - `MapowanieForm.tworz_brakujace_stopnie`/`tworz_brakujace_stanowiska`; `MapowanieView.form_valid` — zapis obu na `ImportPracownikow` (`update_fields`).

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_views_slowniki.py`:

```python
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowStopien,
)


@pytest.fixture
def owner(django_user_model):
    u = baker.make(django_user_model)
    grp, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    u.groups.add(grp)
    return u


@pytest.mark.django_db
def test_ekran_stopni_get_200(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow, owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    baker.make(
        ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
    )
    resp = client.get(reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}))
    assert resp.status_code == 200
    assert "kpt." in resp.content.decode()


@pytest.mark.django_db
def test_ekran_stanowisk_get_200(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow, owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    resp = client.get(
        reverse("import_pracownikow:stanowiska", kwargs={"pk": imp.pk})
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_zapisuje_decyzje_stopnia_akceptuj(client, owner):
    # Mirror test_views_tytuly.test_post_zapisuje_decyzje_* — POST decyzji
    # (akceptuj) redirectuje i zapisuje `decyzja`.
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow, owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    dec = baker.make(
        ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="mł. bryg.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
        decyzja=ImportPracownikowStopien.DECYZJA_MAPUJ,
    )
    resp = client.post(
        reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}),
        {f"dec_{dec.pk}_decyzja": ImportPracownikowStopien.DECYZJA_AKCEPTUJ},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.decyzja == ImportPracownikowStopien.DECYZJA_AKCEPTUJ


@pytest.mark.django_db
def test_post_mapuj_bez_celu_daje_blad_i_nie_zapisuje(client, owner):
    # Mirror walidacji „mapuj bez wybranego celu" — POST z decyzją MAPUJ i pustym
    # celem redirectuje z komunikatem błędu i NIE zapisuje decyzji.
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow, owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    dec = baker.make(
        ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.",
        tryb=ImportPracownikowStopien.TRYB_ZGADYWANIE,
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
    )
    resp = client.post(
        reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}),
        {
            f"dec_{dec.pk}_decyzja": ImportPracownikowStopien.DECYZJA_MAPUJ,
            f"dec_{dec.pk}_wybrana": "",
        },
    )
    assert resp.status_code == 302  # redirect z komunikatem błędu
    dec.refresh_from_db()
    # walidacja odrzuciła zapis — decyzja NIE zmieniona na MAPUJ
    assert dec.decyzja == ImportPracownikowStopien.DECYZJA_AKCEPTUJ


@pytest.mark.django_db
def test_zatwierdz_pelny_blokuje_gdy_stopnie_nierozstrzygniete(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow, owner=owner,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    baker.make(
        ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ, utworzony=None,
    )
    resp = client.post(
        reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk}),
        {"zakres": "pelny"},
    )
    assert resp.status_code == 400


def test_mapowanie_form_ma_toggle_slownikow():
    from import_pracownikow.forms import MapowanieForm

    f = MapowanieForm(naglowki=["nazwisko"])
    assert "tworz_brakujace_stopnie" in f.fields
    assert "tworz_brakujace_stanowiska" in f.fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_views_slowniki.py -v`
Expected: FAIL — brak tras/widoków/toggle.

- [ ] **Step 3: Dodaj widoki weryfikacji (mirror `WeryfikacjaTytulowView`)**

W `views.py` dodaj import modeli decyzji do bloku `from import_pracownikow.models import (...)`: `ImportPracownikowStanowisko`, `ImportPracownikowStopien`, oraz `StanowiskoDydaktyczne`, `StopienSluzbowy` do `from bpp.models import (...)`.

Dodaj `WeryfikacjaStopniView` — mirror `WeryfikacjaTytulowView` z PODSTAWIENIAMI: `ImportPracownikowTytul`→`ImportPracownikowStopien`, `tytuly_do_decyzji`→`stopnie_do_decyzji`, `auto_tytul`→`auto_stopien`, `wybrany_tytul`→`wybrany_stopien`, `wiersze_tytul`→`wiersze_stopien`, `Tytul`→`StopienSluzbowy`, `template_name`→`import_pracownikow/weryfikacja_stopni.html`, URL redirect `tytuly`→`stopnie`, komunikaty „tytuł(-ach)"→„stopień/stopniach służbowych". Pełny kod:

```python
class WeryfikacjaStopniView(GroupRequiredMixin, View):
    """Ekran weryfikacji decyzji o stopniach służbowych (mirror
    ``WeryfikacjaTytulowView``)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/weryfikacja_stopni.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _decyzje(self):
        return (
            self.parent_object.stopnie_do_decyzji.select_related(
                "auto_stopien", "wybrany_stopien"
            )
            .annotate(liczba_osob=Count("wiersze_stopien", distinct=True))
            .order_by("nazwa_zrodlowa")
        )

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        decyzje = list(self._decyzje())
        ctx = {
            "parent_object": parent,
            "decyzje_brak": [
                d for d in decyzje if d.tryb == ImportPracownikowStopien.TRYB_BRAK
            ],
            "decyzje_zgadywanie": [
                d
                for d in decyzje
                if d.tryb == ImportPracownikowStopien.TRYB_ZGADYWANIE
            ],
            "mapuj_opcje": StopienSluzbowy.objects.all().order_by("skrot"),
            "moze_edytowac": parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY,
            "DECYZJA_AKCEPTUJ": ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowStopien.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowStopien.DECYZJA_POMIN,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        parent = self.parent_object
        if parent.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Decyzje o stopniach można zmieniać tylko w podglądzie."
            )
        prawidlowe = {
            ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
            ImportPracownikowStopien.DECYZJA_MAPUJ,
            ImportPracownikowStopien.DECYZJA_POMIN,
        }
        decyzje = list(parent.stopnie_do_decyzji.all())
        bez_celu = [
            dec.nazwa_zrodlowa
            for dec in decyzje
            if request.POST.get(f"dec_{dec.pk}_decyzja")
            == ImportPracownikowStopien.DECYZJA_MAPUJ
            and not (request.POST.get(f"dec_{dec.pk}_wybrana") or "")
        ]
        if bez_celu:
            messages.error(
                request,
                'Wybierz stopień docelowy w kolumnie „Mapuj na" dla: '
                + ", ".join(bez_celu),
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:stopnie", kwargs={"pk": parent.pk})
            )
        for dec in decyzje:
            pref = f"dec_{dec.pk}_"
            decyzja = request.POST.get(pref + "decyzja")
            if decyzja in prawidlowe:
                dec.decyzja = decyzja
            mapuj_id = (request.POST.get(pref + "wybrana") or "").strip()
            dec.wybrany_stopien = (
                StopienSluzbowy.objects.filter(pk=int(mapuj_id)).first()
                if mapuj_id.isdigit()
                else None
            )
            update_fields = ["decyzja", "wybrany_stopien"]
            if dec.tryb == ImportPracownikowStopien.TRYB_BRAK:
                nazwa = request.POST.get(pref + "nazwa")
                if nazwa is not None:
                    dec.nazwa_do_utworzenia = nazwa.strip()[:512]
                    update_fields.append("nazwa_do_utworzenia")
                skrot = request.POST.get(pref + "skrot")
                if skrot is not None:
                    dec.skrot_do_utworzenia = skrot.strip()[:128]
                    update_fields.append("skrot_do_utworzenia")
            dec.save(update_fields=update_fields)
        messages.success(request, "Zapisano decyzje o stopniach służbowych.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:stopnie", kwargs={"pk": parent.pk})
        )
```

Dodaj `WeryfikacjaStanowiskView` — ten sam kod z podstawieniami `Stopien`→`Stanowisko`: `stopnie_do_decyzji`→`stanowiska_do_decyzji`, `auto_stopien`→`auto_stanowisko`, `wybrany_stopien`→`wybrane_stanowisko`, `wiersze_stopien`→`wiersze_stanowisko`, `StopienSluzbowy`→`StanowiskoDydaktyczne`, `ImportPracownikowStopien`→`ImportPracownikowStanowisko`, `template_name`→`weryfikacja_stanowisk.html`, URL `stopnie`→`stanowiska`, komunikaty „stopień/stopniach służbowych"→„stanowisko/stanowiskach dydaktycznych", oraz atrybut POST `dec.wybrane_stanowisko` (nie `wybrany_`) w `update_fields`.

- [ ] **Step 4: Dodaj trasy w `urls.py`**

Po trasie `tytuly` dodaj:

```python
    path(
        "<uuid:pk>/stopnie/",
        views.WeryfikacjaStopniView.as_view(),
        name="stopnie",
    ),
    path(
        "<uuid:pk>/stanowiska/",
        views.WeryfikacjaStanowiskView.as_view(),
        name="stanowiska",
    ),
```

- [ ] **Step 5: Rozszerz bramkę `ZatwierdzImportView` (PELNY)**

W gałęzi `else:` (PELNY) `ZatwierdzImportView.post`, zamień warunek bramki na sumę słowników (spec §12 finding #2):

```python
            if (
                obj.tytuly_wymagaja_rozstrzygniecia
                or obj.stopnie_wymagaja_rozstrzygniecia
                or obj.stanowiska_wymagaja_rozstrzygniecia
            ):
                return HttpResponseBadRequest(
                    "Najpierw utwórz brakujące słowniki z pliku "
                    "(Krok 2: tytuły / stopnie służbowe / stanowiska "
                    "dydaktyczne) — import osób nie tworzy ich po cichu."
                )
```

- [ ] **Step 6: Toggle w `MapowanieForm` + zapis w `MapowanieView`**

W `forms.py`, w `MapowanieForm`, po `tworz_brakujace_tytuly` dodaj (mirror):

```python
    tworz_brakujace_stopnie = forms.BooleanField(
        required=False,
        initial=True,
        label="Twórz brakujące stopnie służbowe",
        help_text="Gdy zaznaczone, stopnie służbowe nieobecne w bazie trafią na "
        "ekran weryfikacji do utworzenia. Odznacz, aby pomijać niedopasowane.",
    )
    tworz_brakujace_stanowiska = forms.BooleanField(
        required=False,
        initial=True,
        label="Twórz brakujące stanowiska dydaktyczne",
        help_text="Gdy zaznaczone, stanowiska dydaktyczne nieobecne w bazie "
        "trafią na ekran weryfikacji do utworzenia. Odznacz, aby pomijać "
        "niedopasowane.",
    )
```

W `views.py` `MapowanieView.form_valid`, po ustawieniu `obj.tworz_brakujace_tytuly = ...` dodaj:

```python
        obj.tworz_brakujace_stopnie = form.cleaned_data.get(
            "tworz_brakujace_stopnie", True
        )
        obj.tworz_brakujace_stanowiska = form.cleaned_data.get(
            "tworz_brakujace_stanowiska", True
        )
```

oraz do listy `update_fields=[...]` (w `obj.save(...)`) dodaj `"tworz_brakujace_stopnie"`, `"tworz_brakujace_stanowiska"`.

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_views_slowniki.py -v`
Expected: PASS (6 testów: 2× GET ekranów, 2× POST decyzji stopnia, bramka PELNY 400, toggle w formularzu). (Ekrany renderują szablony z Task 6 — jeśli szablony jeszcze nie istnieją, GET-y w tym tasku FAILUJĄ z `TemplateDoesNotExist`; wtedy wykonaj Task 6 najpierw i wróć, albo utwórz puste szablony-stuby i uzupełnij w Task 6. POST-testy nie renderują szablonu — przechodzą niezależnie od Task 6. Rekomendacja: uruchom Step 7 PO Task 6.)

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/forms.py \
  src/import_pracownikow/tests/test_views_slowniki.py
git commit -m "feat(import_pracownikow): ekrany weryfikacji stopni/stanowisk + bramki + toggle"
```

---

## Task 6: Szablony weryfikacji + rozszerzenie huba `przeglad.html`

**Files:**
- Modify: `src/import_pracownikow/views.py` (kontekst `PodgladImportuView`)
- Create: `src/import_pracownikow/templates/import_pracownikow/weryfikacja_stopni.html`
- Create: `src/import_pracownikow/templates/import_pracownikow/weryfikacja_stanowisk.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/przeglad.html`

**Interfaces:**
- Consumes: `WeryfikacjaStopniView`/`WeryfikacjaStanowiskView` kontekst (Task 5); liczniki/właściwości (Task 2).
- Produces: dwa szablony weryfikacji (mirror `weryfikacja_tytulow.html`); `PodgladImportuView` kontekst `pokaz_stopnie`/`pokaz_stanowiska`/`liczniki_stopni`/`liczniki_stanowisk`/`slowniki_wymagaja_rozstrzygniecia`/`pokaz_struktura_slowniki`; `przeglad.html` bramki OR + linie liczników.

- [ ] **Step 1: Utwórz `weryfikacja_stopni.html`**

Skopiuj `weryfikacja_tytulow.html` do `weryfikacja_stopni.html` z PODSTAWIENIAMI tekstowymi:
- „weryfikacja tytułów" → „weryfikacja stopni służbowych"; „Weryfikacja tytułów" → „Weryfikacja stopni służbowych".
- „Tytuły wymienione w pliku" → „Stopnie służbowe wymienione w pliku"; „istniejącego tytułu" → „istniejącego stopnia"; „nowe tytuły" → „nowe stopnie".
- Nagłówki tabel „Auto-tytuł" → „Auto-stopień".
- Link `url "import_pracownikow:przeglad"` bez zmian; `{{ dec.auto_tytul.skrot }}` → `{{ dec.auto_stopien.skrot }}`; `{% if dec.wybrany_tytul_id == t.pk %}` → `{% if dec.wybrany_stopien_id == t.pk %}`.
- Pętla `{% for t in mapuj_opcje %}` i `{{ t.skrot }}` bez zmian (mapuj_opcje = `StopienSluzbowy`).
- Nazwy pól POST (`dec_{{ dec.pk }}_decyzja`/`_wybrana`/`_nazwa`/`_skrot`), zmienne `moze_edytowac`, `decyzje_brak`, `decyzje_zgadywanie`, `DECYZJA_*` — BEZ zmian (widok dostarcza je pod tymi samymi nazwami).

Reszta struktury (2 tabele „Dopasowane automatycznie" / „Do utworzenia", przyciski, callouty) identyczna.

- [ ] **Step 2: Utwórz `weryfikacja_stanowisk.html`**

Skopiuj `weryfikacja_stopni.html` do `weryfikacja_stanowisk.html` z PODSTAWIENIAMI:
- „stopni służbowych"/„stopnia"/„stopnie" → „stanowisk dydaktycznych"/„stanowiska"/„stanowiska"; „Auto-stopień" → „Auto-stanowisko".
- `{{ dec.auto_stopien.skrot }}` → `{{ dec.auto_stanowisko.skrot }}`; `{% if dec.wybrany_stopien_id == t.pk %}` → `{% if dec.wybrane_stanowisko_id == t.pk %}`.
- Reszta bez zmian (widok dostarcza `mapuj_opcje` = `StanowiskoDydaktyczne`, te same zmienne kontekstu).

- [ ] **Step 3: Rozszerz kontekst `PodgladImportuView.get_context_data`**

W `views.py`, w `ctx.update({...})` `PodgladImportuView`, dodaj klucze (obok `pokaz_tytuly`/`tytuly_wymagaja_rozstrzygniecia`):

```python
                "liczniki_stopni": parent.liczniki_stopni(),
                "liczniki_stanowisk": parent.liczniki_stanowisk(),
                "pokaz_stopnie": parent.stopnie_do_decyzji.exists(),
                "pokaz_stanowiska": parent.stanowiska_do_decyzji.exists(),
                # Bramka Kroku 2 (finding #2): import osób nie tworzy słowników
                # po cichu — dowolny nierozstrzygnięty słownik blokuje.
                "slowniki_wymagaja_rozstrzygniecia": (
                    parent.tytuly_wymagaja_rozstrzygniecia
                    or parent.stopnie_wymagaja_rozstrzygniecia
                    or parent.stanowiska_wymagaja_rozstrzygniecia
                ),
                # „Zapisz jednostki + słowniki" (zakres=struktura) ma sens, gdy
                # jest COKOLWIEK słownikowego do utworzenia poza jednostkami.
                "pokaz_struktura_slowniki": (
                    parent.tytuly_do_decyzji.exists()
                    or parent.stopnie_do_decyzji.exists()
                    or parent.stanowiska_do_decyzji.exists()
                ),
```

- [ ] **Step 4: Rozszerz `przeglad.html` — Krok 1 (callout struktury)**

W bloku `{% if faza_struktury %}`:

(a) Nagłówek Kroku 1 — rozszerz o słowniki:
```django
<h2>Krok 1 — struktura (jednostki{% if pokaz_tytuly or pokaz_stopnie or pokaz_stanowiska %} i słowniki{% endif %})</h2>
```

(b) Po bloku „Zobacz tytuły" (`{% if ma_tytuly %}...{% endif %}`) dodaj DWA analogiczne bloki (stopnie/stanowiska), każdy warunkowo:
```django
            {% if pokaz_stopnie %}
                <p>
                    <span class="fi-shield"></span>
                    {{ liczniki_stopni.do_utworzenia }} stopni służbowych do utworzenia ·
                    {{ liczniki_stopni.do_sprawdzenia }} do sprawdzenia.
                    <a href="{% url "import_pracownikow:stopnie" parent_object.pk %}"
                       class="button success">Zobacz stopnie</a>
                </p>
            {% endif %}
            {% if pokaz_stanowiska %}
                <p>
                    <span class="fi-torso-business"></span>
                    {{ liczniki_stanowisk.do_utworzenia }} stanowisk dydaktycznych do utworzenia ·
                    {{ liczniki_stanowisk.do_sprawdzenia }} do sprawdzenia.
                    <a href="{% url "import_pracownikow:stanowiska" parent_object.pk %}"
                       class="button success">Zobacz stanowiska</a>
                </p>
            {% endif %}
```

(c) Przycisk „Zapisz jednostki + tytuły" — rozszerz warunek widoczności i etykietę o słowniki:
```django
                {% if pokaz_struktura_slowniki %}
                    <button type="submit" name="zakres" value="struktura"
                            class="button">
                        <span class="fi-crown"></span> Zapisz jednostki + słowniki
                    </button>
                {% endif %}
```
(zamiast dotychczasowego `{% if pokaz_tytuly %}` wokół tego przycisku; pod spodem help-text „Zapisz tylko jednostki odkłada…" analogicznie owiń `{% if pokaz_struktura_slowniki %}`).

- [ ] **Step 5: Rozszerz `przeglad.html` — Krok 2 (bramka słowników)**

W bloku `{% elif moze_importowac_osoby %}`, zamień warunek `{% if tytuly_wymagaja_rozstrzygniecia %}` na `{% if slowniki_wymagaja_rozstrzygniecia %}` i uogólnij treść alertu na słowniki (tytuły/stopnie/stanowiska); przyciski „Zobacz tytuły"/„Zobacz stopnie"/„Zobacz stanowiska" warunkowo (`pokaz_tytuly`/`pokaz_stopnie`/`pokaz_stanowiska`), a formularz „Utwórz brakujące" z `zakres=struktura` bez zmian (rozstrzyga wszystkie słowniki naraz):

```django
            {% if slowniki_wymagaja_rozstrzygniecia %}
                <div class="callout alert">
                    <h3><span class="fi-alert"></span> Najpierw słowniki</h3>
                    <p>W pliku są tytuły/stopnie/stanowiska, których nie ma
                        jeszcze w bazie. Import osób <strong>nie</strong> utworzy
                        ich po cichu — najpierw je obejrzyj i utwórz.</p>
                    {% if pokaz_tytuly %}
                        <a href="{% url "import_pracownikow:tytuly" parent_object.pk %}"
                           class="button success">Zobacz tytuły</a>
                    {% endif %}
                    {% if pokaz_stopnie %}
                        <a href="{% url "import_pracownikow:stopnie" parent_object.pk %}"
                           class="button success">Zobacz stopnie</a>
                    {% endif %}
                    {% if pokaz_stanowiska %}
                        <a href="{% url "import_pracownikow:stanowiska" parent_object.pk %}"
                           class="button success">Zobacz stanowiska</a>
                    {% endif %}
                    <form method="post"
                          action="{% url "import_pracownikow:zatwierdz" parent_object.pk %}">
                        {% csrf_token %}
                        <input type="hidden" name="zakres" value="struktura">
                        <button type="submit" class="button">
                            <span class="fi-crown"></span> Utwórz brakujące słowniki
                        </button>
                    </form>
                </div>
            {% else %}
```

(reszta `{% else %}` — callout „Uwaga: zapis osób…" + przycisk „Zapisz osoby do bazy" — bez zmian.)

Uwaga (liczniki): uogólniony alert powyżej nie renderuje już liczb
`do_utworzenia`/`do_sprawdzenia`. Jeśli chcesz zachować je jak w wariancie
tytułów, pokaż liczniki słowników analogicznie do tytułów — obok „Zobacz
stopnie"/„Zobacz stanowiska" wstaw `{{ liczniki_stopni.do_utworzenia }}` /
`{{ liczniki_stopni.do_sprawdzenia }}` oraz `{{ liczniki_stanowisk.* }}` (jak w
callout Kroku 1, Step 4).

- [ ] **Step 6: Kafelki audytu (poza flow) — opcjonalne stopnie/stanowiska**

W dolnym `<div class="row">` (audyt zintegrowanego), po kafelku „Tytuły", dodaj analogiczne kafelki warunkowe dla stopni/stanowisk (mirror kafelka „Tytuły", `pokaz_stopnie`/`pokaz_stanowiska`, `liczniki_stopni`/`liczniki_stanowisk`, `url ...:stopnie`/`:stanowiska`). Zachowaj `and not faza_struktury and not moze_importowac_osoby`. (Przykład — mirror istniejącego bloku „Tytuły".)

- [ ] **Step 7: Zaktualizuj asercje `test_przeglad.py` (teksty huba)**

Zmiana etykiet w `przeglad.html` (Steps 4–5) łamie istniejące asercje w
`src/import_pracownikow/tests/test_przeglad.py`. Zaktualizuj **WSZYSTKIE**
wystąpienia starych brzmień — zarówno POZYTYWNE (`... in tresc`), jak i
NEGATYWNE (`... not in tresc`) — na nowe:
- „Zapisz jednostki + tytuły" → „Zapisz jednostki + słowniki"
- „Najpierw tytuły" → „Najpierw słowniki"
- „Utwórz brakujące tytuły" → „Utwórz brakujące słowniki"

Konkretnie:
- Pozytywne (relabel widoczny na hubie): linia ~179
  `assert "Zapisz jednostki + tytuły" in tresc`, ~274
  `assert "Najpierw tytuły" in tresc`, ~275
  `assert "Utwórz brakujące tytuły" in tresc`.
- **Negatywne (KRYTYCZNE — nie pomijaj):** linia ~252
  `assert "Zapisz jednostki + tytuły" not in tresc`, ~298 i ~317
  `assert "Najpierw tytuły" not in tresc` — te też przepisz na nowe
  brzmienie (`"Zapisz jednostki + słowniki" not in tresc`,
  `"Najpierw słowniki" not in tresc`).

**Pułapka (dopisz w kroku):** gdyby zaktualizować tylko asercje pozytywne, a
negatywne zostawić na starym stringu, po relabelingu przeszłyby „wakatowo" —
stary string zniknął z szablonu, więc `not in` jest trywialnie prawdziwe i
NIE pilnuje już semantyki (że w kontekście gdzie słowniki są rozstrzygnięte
blok „Najpierw słowniki" NIE ma się pojawić). Przepisanie negatywnych na
nowe brzmienie sprawia, że `not in` pilnuje teraz WŁAŚCIWEGO (nowego)
wariantu.

Run: `uv run pytest src/import_pracownikow/tests/test_przeglad.py -q`
Expected: PASS (asercje huba — pozytywne i negatywne — zgodne z nowymi
etykietami).

- [ ] **Step 8: Uruchom testy widoków (Task 5) + smoke szablonów**

Run: `uv run pytest src/import_pracownikow/tests/test_views_slowniki.py -v`
Expected: PASS (GET-y ekranów renderują szablony 200; bramka 400).

Sanity djLint (komentarze Django jedno-liniowe — reguła projektu):
Run: `uv run djlint src/import_pracownikow/templates/import_pracownikow/weryfikacja_stopni.html src/import_pracownikow/templates/import_pracownikow/weryfikacja_stanowisk.html src/import_pracownikow/templates/import_pracownikow/przeglad.html --check`
Expected: brak nowych błędów (istniejące H037/H025 na `przeglad.html` mogą być pre-existing — patrz pamięć „Pre-commit: pre-istniejące błędy").

- [ ] **Step 9: Commit**

```bash
git add src/import_pracownikow/views.py \
  src/import_pracownikow/templates/import_pracownikow/weryfikacja_stopni.html \
  src/import_pracownikow/templates/import_pracownikow/weryfikacja_stanowisk.html \
  src/import_pracownikow/templates/import_pracownikow/przeglad.html \
  src/import_pracownikow/tests/test_przeglad.py
git commit -m "feat(import_pracownikow): szablony weryfikacji słowników + hub bramki OR"
```

---

## Weryfikacja końcowa Planu 3

- [ ] **Step 1: Uruchom testy Planu 3**

Run:
```bash
uv run pytest \
  src/import_pracownikow/tests/test_models_slowniki_decyzji.py \
  src/import_pracownikow/tests/test_autorform_slowniki.py \
  src/import_pracownikow/tests/test_analyze_slowniki.py \
  src/import_pracownikow/tests/test_integrate_slowniki.py \
  src/import_pracownikow/tests/test_views_slowniki.py \
  -v 2>&1 | tee /tmp/plan3_tests.log
```
Expected: wszystkie PASS.

- [ ] **Step 2: Regresja całego modułu importu**

Run: `uv run pytest src/import_pracownikow/ -q 2>&1 | tee /tmp/plan3_regresja.log`
(pełen katalog obejmuje `test_przeglad.py` — testy huba zmienione etykietami.)
Expected: bez regresji (istniejące testy jednostek/tytułów/analyze/integrate/widoków + `test_przeglad.py` zielone). Uwaga: `test_przeglad.py` przejdzie TYLKO po aktualizacji asercji tekstów huba z Task 6 Step 7 (zmiana etykiet w `przeglad.html`) — bez niej NIE deklaruj „bez regresji".

- [ ] **Step 3: Sanity migracji**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --check --dry-run`
Expected: „No changes detected" (model i migracja `0023` spójne).

- [ ] **Step 4: ruff**

Run:
```bash
ruff check src/import_pracownikow/models.py \
  src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/forms.py
```
Expected: brak błędów (poprawiaj ręcznie, bez `--fix` na masę).

- [ ] **Step 5: Newsfragment**

Create `src/bpp/newsfragments/import-slowniki-pipeline.feature.rst`:
```
Import pracowników rozpoznaje i weryfikuje stopnie służbowe oraz stanowiska
dydaktyczne (pełne ekrany weryfikacji, jak tytuły), a także rozbija kolumnę
„nazwisko imię", parsuje złożoną nazwę komórki i importuje adres e-mail.
```
Commit:
```bash
git add src/bpp/newsfragments/import-slowniki-pipeline.feature.rst
git commit -m "docs(newsfragment): pipeline importu słowników stopień/stanowisko"
```

**Deliverable Planu 3:** pełny przepływ importu obsługuje słowniki `StopienSluzbowy`/`StanowiskoDydaktyczne` — analiza klasyfikuje (twardy/zgadywanie/brak) i tworzy decyzje, ekrany `weryfikacja_stopni`/`weryfikacja_stanowisk` pozwalają akceptować/mapować/pomijać/edytować, integracja rozstrzyga słowniki w fazie struktury i dopina FK do `Autor`/`Autor_Jednostka` w fazie osób (stopień + stanowisko overwrite-if-different, e-mail no-overwrite), a bramki „najpierw słowniki, potem osoby" pilnują braku cichego tworzenia. Wpięte parsery: komórka złożona (skrót → `Jednostka.skrot`, oddział → wydział), „nazwisko imię", niepełna nazwa jednostki oraz kolumna e-mail. Gotowe pod Plan 4 (porównywarka e-mail/stopień/stanowisko + E2E na `struktura.xlsx`).
