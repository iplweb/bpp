# Import pracowników — Faza 4: „utwórz nowego autora" (D2) + odpięcia per-autor (§9)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Domknąć dwie decyzje produktowe importu pracowników: (D2) w fazie
commit tworzyć nowego `bpp.Autor` dla wierszy o statusie `brak`, które user
świadomie zaznaczył „utwórz nowego"; (§9/D3) materializować odpięcia autorów
spoza pliku jako per-autor decyzje (domyślnie ODZNACZONE), wykonywane dopiero w
commicie dla zaznaczonych. Po drodze naprawić regresję NULL w
`autorzy_spoza_pliku_set()` i usunąć Faza-0 stopgap (natychmiastowe odpięcie z
osobnego przycisku).

**Architecture:** Odpięcia przestają być liczone dynamicznie „w locie" i
wykonywane jednym przyciskiem. W fazie analizy (`pipeline/analyze.py`) po pętli
wierszy materializujemy je jako wiersze `ImportPracownikowOdpiecie(parent,
autor_jednostka, zaznaczone=False, wykonane=False)` — persystencja przeżywa
drift bazy między podglądem a commitem. Preview pokazuje je z checkboxami
(HTMX toggle `zaznaczone`, wzorzec `WybierzKandydataView` z Fazy 3:
owner-scoped, `GroupRequiredMixin`, bramka stanu `przeanalizowany`). Faza commit
(`pipeline/integrate.py`) iteruje `zaznaczone=True`, robi ŚWIEŻY re-check
(powiązanie mogło już zostać zakończone ręcznie) i kończy zatrudnienie. Zapytanie
`autorzy_spoza_pliku_set()` przepisujemy z porównania po pk `Autor_Jednostka`
(zawiera NULL-e po Fazie 0/3 → `NOT IN (…, NULL)` → pusty zbiór) na porównanie
po parach `(autor_id, jednostka_id)` z wierszy, z jawnym odfiltrowaniem NULL-i.
Dla D2: nowe pole `utworz_nowego` na wierszu (HTMX toggle dla `brak`), a faza
commit tworzy `bpp.Autor` z `dane_znormalizowane` i re-używa
`pewnosc.odtworz_autor_jednostka` (z Fazy 3), żeby powstało `Autor_Jednostka` +
diff, po czym wiersz przechodzi normalną integrację.

**Tech Stack:** Django, django-liveops, HTMX (unpkg 2.0.4, wzorzec
`importer_publikacji`/Faza 3), Foundation CSS (label + Foundation-Icons), pytest,
model_bakery, testcontainers.

## Global Constraints

- **Max 88 znaków/linia.** UWAGA: ruff IGNORUJE `E501` — sprawdzaj `.py`
  RĘCZNIE: `awk 'length>88{print FILENAME":"NR}' <plik>`.
- **Zawsze `uv run`** dla poleceń Pythona.
- **NIE modyfikować istniejących migracji** `src/*/migrations/`. Faza 4 dodaje
  JEDNĄ nową migrację (`0014_...`), generowaną przez
  `uv run python src/manage.py makemigrations` — NIGDY ręcznie. Po jej
  wygenerowaniu `makemigrations --check --dry-run` MUSI być czysty.
- **NIE dodawaj kroku `make baseline-update`** — baseline odświeżamy przy MERGE,
  nie na tym feature-branchu (reguła CLAUDE.md: równoległe branch'e nie mogą
  kolidować na jednym pliku `baseline.sql`).
- **Backward compat:** stany/przepływ Faz 0–3 (upload→map→analiza→[wybór/edycja]→
  zatwierdź→integracja) muszą działać; stare rekordy się nie wywalają. Nowe pola
  mają bezpieczne defaulty (`utworz_nowego` default False; model odpięcia jest
  całkowicie nowy).
- **Bez `except: pass`** — wąski typ wyjątku + komentarz WHY.
- **Komentarze szablonów Django `{# #}` JEDNOLINIOWE** — KAŻDA linia własne
  `{# ... #}`. Wieloliniowy komentarz wycieka do HTML.
- **Ikony we froncie publicznym: Foundation-Icons** (`<i class="fi-...">`), NIE
  emoji (emoji tylko w django-adminie).
- **pytest, nie unittest**; funkcje bez klas; `@pytest.mark.django_db` gdy DB;
  `model_bakery.baker.make`. `Tytul` przez `get_or_create` (baseline ma unique
  `dr`/`mgr`/`lek.`). Django `Client` do widoków.
- **Formatowanie: PINNED pre-commit hook** —
  `uv run pre-commit run ruff-format --files <pliki>` + `uv run ruff check`, NIE
  `uv run ruff format`. Gdy pre-commit zgłasza problemy: analizuj issue-by-issue,
  poprawiaj ręcznie Editem (NIE `ruff check --fix`).
- **Testy przez testcontainers** (Docker daemon wymagany); pełna suita do 10 min.

## Decyzje architektoniczne (podjęte — NIE zmieniać)

1. **§9 — przepisanie zapytania (nie „zachowanie").** Dzisiejsze
   `autorzy_spoza_pliku_set()` robi
   `exclude(pk__in=values_list("autor_jednostka"))`. Po Fazie 0/3
   `ImportPracownikowRow.autor_jednostka` bywa NULL (odroczone AJ, statusy
   `brak`/`wielu`) → subquery zawiera NULL-e → SQL `NOT IN (…, NULL)` zwraca
   **pusty zbiór** → żadnych odpięć (regresja). PRZEPISZ na porównanie po parach
   `(autor_id, jednostka_id)` z wierszy (znane nawet bez AJ), z jawnym
   odfiltrowaniem NULL-i, NIE po pk `Autor_Jednostka`. Zachowaj kryteria
   wykluczeń: jednostka `zarzadzaj_automatycznie=True`, nie-obca (uczelnia
   `obca_jednostka_id`), aktywne (`zakonczyl_prace` NULL lub `> today`),
   `autor__aktualna_jednostka` nie-NULL.
2. **Materializacja odpięć — w analizie, wykonanie — w commicie.**
   `analizuj` PO pętli wierszy tworzy wiersze `ImportPracownikowOdpiecie`
   (`zaznaczone=False`) dla `autorzy_spoza_pliku_set()`; idempotentnie
   (delete-first + `on_restart` kasuje odpięcia przy cofnięciu do `zmapowany`).
   `integruj` iteruje `zaznaczone=True, wykonane=False`, robi świeży re-check
   (pomiń AJ już zakończone ręcznie), kończy zatrudnienie
   (`zakonczyl_prace = wczoraj`, `podstawowe_miejsce_pracy=False`), ustawia
   `wykonane=True`. `autor_jednostka` w odpięciu wskazuje ISTNIEJĄCE AJ (realne,
   z pk).
3. **Usunięcie Faza-0 stopgap (decyzja A → wariant „a": usuń czysto).** Stary
   `odepnij_autorow_spoza_pliku` (models), `ImportPracownikowResetuj
   PodstawoweMiejscePracyView` (views), url `resetuj-podstawowe-miejsce-pracy`,
   link w templatce i dynamiczny kontekst `autorzy_spoza_pliku()` — USUWAMY,
   zastępując materializowanym przepływem analiza→commit. Konsumenci
   (`test_views.py`, `test_models/test_odepnij_autorow_spoza_pliku.py`) —
   usunięci/zastąpieni. Metoda `autorzy_spoza_pliku_set()` ZOSTAJE (używa jej
   analiza), tylko przepisana (pkt 1).
4. **D2 — tworzenie autora WYŁĄCZNIE w commicie (dry-run nic nie tworzy — §8).**
   Nowe pole `utworz_nowego = BooleanField(default=False)` na
   `ImportPracownikowRow`. UI: checkbox dla wierszy `confidence == brak`
   (HTMX toggle, wzorzec `WybierzKandydataView`; współdzieli `_WierszImportuMixin`
   z Fazy 3). W fazie commit, dla wierszy `confidence == brak`,
   `utworz_nowego == True`, `autor is None`: utwórz `bpp.Autor`
   (`nazwisko`/`imiona` z `dane_znormalizowane`, `tytul` z FK `row.tytul` z
   analizy), `row.autor = autor`, `odtworz_autor_jednostka(row, autor)` (z Fazy
   3), po czym wiersz przechodzi normalną pętlą integracji (materializacja AJ +
   `row.integrate()`). `brak` z `utworz_nowego=False` → NADAL pomijany.
5. **Granica Faza 4 / Faza 5.** Przepięcie prac naukowych (§10, `przepnij_prace`,
   `przemapuj_prace_autora`) = **Faza 5** — NIE implementować. To ostatni element
   D2 i §9.

## Assumptions / otwarte ryzyka (wpisane do planu)

- **A1.** `ImportPracownikow.autorzy_spoza_pliku_set(uczelnia=None, today=None)`
  po przepisaniu zwraca queryset `Autor_Jednostka`. Odfiltrowanie NULL-i przez
  `filter(autor__isnull=False, jednostka__isnull=False)` na wierszach; wykluczenie
  par przez rozłączne `Q(autor_id=…, jednostka_id=…)` (O(n) klauzul OR). Przy
  setkach wierszy to akceptowalny narzut; jeśli realne pliki kadrowe (§13 spec)
  okażą się rzędu tysięcy — do zamiany na `values`/tuple-`__in` w późniejszej
  iteracji. NIE optymalizujemy teraz (brak realnych danych — A6 Fazy 3).
- **A2.** Uczelnię w fazie analizy (bez `request`) ustala
  `Uczelnia.objects.get_single_uczelnia_or_none()` — jedyna uczelnia albo `None`
  (multi-hosted BPP nie ma „uczelni domyślnej"; `get_default` usunięty). `None` →
  pomijamy wykluczenie obcej jednostki (spójne z dotychczasowym `if uczelnia is
  not None`).
- **A3.** `bpp.Autor` wymaga tylko `nazwisko` i `imiona` (oba `CharField`, bez
  defaultu); `tytul` FK jest nullable; identyfikatory (`orcid`,
  `system_kadrowy_id`, `expertus_id`) są `unique` ale nullable — minimalny
  `Autor.objects.create(nazwisko=…, imiona=…, tytul=…)` NIE ustawia ich, więc
  brak kolizji unikalności. Pozostałe pola z pliku (orcid/pbn/numer) dograją
  istniejące `_integrate_autor()` w `row.integrate()` (MAPPING_DANE_NA_AUTOR).
  `Autor.save()` liczy `sort` — nie wymaga dodatkowych pól.
- **A4.** Zwykle wiersz `brak` przeszedł `AutorForm` (nazwisko ORAZ imię
  wymagane), więc `dane_znormalizowane["nazwisko"]`/`["imię"]` są niepuste. ALE
  NIE zawsze: `EdytujWierszView` waliduje TYLKO `nazwisko` (views.py:342–346), a
  `_rematch_wiersz` (views.py:282–284) zapisuje `dane["imię"]` z POST-a — więc
  korekta na samo nazwisko może zejść do `brak` z pustym `imię`. Dlatego
  `_przygotuj_nowego_autora` (T8, F5) sprawdza `imię`: przy pustym NIE tworzy
  autora (AutorForm wymaga obu) — wiersz zostaje `autor=None` i wpada w
  `pominieto_niedopasowane`. (Klucz to `"imię"` z AutorForm, mapowany na
  `Autor.imiona`.)
- **A5.** `check_if_integration_needed()` / `_integrate_autor_jednostka()` czytają
  `self.autor`/`self.autor_jednostka`; dla wierszy `brak` tworzenie autora +
  `odtworz_autor_jednostka` MUSI ustawić `row.autor` i AJ/diff PRZED wejściem w
  pętlę integracji — inaczej `aj.save()` na `None` (AttributeError). Realizuje to
  `_przygotuj_nowego_autora` w fazie pre-pass `integruj`, ustawiając
  `zmiany_potrzebne=True`, tak że główna pętla `zmiany_potrzebne_set` domyka
  integrację (bez podwójnego przetwarzania — pre-pass NIE woła `_integruj_wiersz`).
- **A6.** Re-check odpięcia (T5 `_wykonaj_odpiecia`) ma DWA warunki pomijające
  (oba: NIE wykonuj, NIE licz, `wykonane` zostaje `False`):
  - **(G1) Para stała się parą Z PLIKU.** Odpięcia materializują się w analizie,
    gdy wiersze `wielu`/`brak` mają `autor=None` — więc AJ prawdziwego autora z
    pliku trafia na listę „spoza pliku". Gdy user potem rozstrzygnie wiersz
    (`WybierzKandydataView`/`EdytujWierszView` ustawia `row.autor`),
    zmaterializowane odpięcie ZOSTAJE; wykonanie go zakończyłoby zatrudnienie
    pracownika, który JEST w pliku (korupcja). Dlatego przed wykonaniem
    sprawdzamy `parent.importpracownikowrow_set.filter(autor_id=aj.autor_id,
    jednostka_id=aj.jednostka_id).exists()` — jeśli para jest teraz w wierszach,
    POMIJAMY (spójne z definicją „spoza pliku" §9).
  - **(drift bazy) AJ zakończone ręcznie** (`zakonczyl_prace is not None and <=
    today`) → pomijamy (NIE nadpisujemy daty).
  Po wykonaniu: `podstawowe_miejsce_pracy=False` + `zakonczyl_prace = wczoraj`
  nie łamią `Autor_Jednostka.clean` (wczoraj < dziś) ani DEFERRED triggera
  podstawowego miejsca pracy.
- **A7.** HTMX ładowany z `https://unpkg.com/htmx.org@2.0.4` już jest w szablonie
  listy podglądu (Faza 3) — nie dokładamy skryptu.
- **A8.** `make baseline-update` robimy przy merge, nie na tym branchu.

## Kontekst i wzorce (przeczytaj przed implementacją)

- **Spec §8 (koniec — dry-run/create'y), §9 (odpięcia), §12 (struktura/migracje),
  §14 (Faza 4):**
  `docs/superpowers/specs/2026-07-09-import-pracownikow-elastyczny-design.md`.
- **Plan Fazy 3 (styl + wzorce widoków toggle / partiali / re-użycia
  `odtworz_autor_jednostka`):**
  `docs/superpowers/plans/2026-07-09-import-pracownikow-faza-3-parser.md`.
- **Model:** `src/import_pracownikow/models.py` —
  `ImportPracownikow` (`stan`, `on_restart`, `autorzy_spoza_pliku_set`,
  `odepnij_autorow_spoza_pliku`, `zmiany_potrzebne_set`, `get_details_set`);
  `ImportPracownikowRow` (`autor`/`jednostka`/`autor_jednostka` nullable FK,
  `dane_znormalizowane`, `diff_do_utworzenia`, `confidence`,
  `wybrany_kandydat`, `check_if_integration_needed`, `integrate`,
  `confidence_badge`).
- **Pewność (re-użycie):** `src/import_pracownikow/pewnosc.py` —
  `STATUS_BRAK`/`STATUS_WIELU`/`STATUS_TWARDY`, `odtworz_autor_jednostka(row,
  autor) -> None` (ustawia AJ/diff + `zmiany_potrzebne`; NIE zapisuje wiersza).
- **Analiza:** `src/import_pracownikow/pipeline/analyze.py` —
  `analizuj(parent, p)` (po pętli `p.track`, przed ustawieniem stanu, dorzucamy
  materializację odpięć); `_przetworz_wiersz`.
- **Integracja:** `src/import_pracownikow/pipeline/integrate.py` —
  `integruj(parent, p)` (pętla `zmiany_potrzebne_set`, `_integruj_wiersz`,
  `_materializuj_diff`, `_opisz_utworzone`, liczniki `zintegrowano`/
  `pominieto_nieaktualne`/`pominieto_niedopasowane`).
- **Widoki/URL:** `src/import_pracownikow/views.py`
  (`_WierszImportuMixin`, `WybierzKandydataView`, `EdytujWierszView`,
  `_blad_jesli_nie_podglad`, `ImportPracownikowResultsView`,
  `ImportPracownikowResetujPodstawoweMiejscePracyView`, `GROUP_REQUIRED`),
  `src/import_pracownikow/urls.py`.
- **Szablony:**
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  (sekcja `autorzy_spoza_pliku` — do zastąpienia materializowanymi odpięciami)
  + `.../partials/_wiersz_preview.html` (blok akcji `przeanalizowany` — dokładamy
  checkbox „utwórz nowego").
- **Modele bazy:** `src/bpp/models/autor.py` — `Autor` (wymagane `imiona`,
  `nazwisko`), `Autor_Jednostka` (`zakonczyl_prace`, `podstawowe_miejsce_pracy`,
  `clean`, unique_together `(autor, jednostka, rozpoczal_prace)`);
  `src/bpp/models/uczelnia.py` — `UczelniaManager.get_single_uczelnia_or_none`.
- **Fixtures:** `src/import_pracownikow/tests/conftest.py`
  (`import_pracownikow`, `import_pracownikow_performed`, `autor_z_pliku`,
  `jednostka_z_pliku`, `autor_spoza_pliku`, `jednostka_spoza_pliku`,
  `autor_jednostka_fixture`); root `conftest.py` (`today`, `yesterday`).

---

## File Structure

**Tworzone:**
- `src/import_pracownikow/migrations/0014_utworz_nowego_odpiecie.py` (generowana).
- `src/import_pracownikow/templates/import_pracownikow/partials/_odpiecie_row.html`.
- `src/import_pracownikow/tests/test_models/test_odpiecie_model.py`
- `src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py`
- `src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py`
- `src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py`
- `src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py`
- `src/import_pracownikow/tests/test_views_odpiecie.py`
- `src/import_pracownikow/tests/test_views_utworz_nowego.py`
- `src/import_pracownikow/tests/test_views_faza4_render.py`
- `src/import_pracownikow/tests/test_pipeline/test_faza4_e2e.py`
- `src/bpp/newsfragments/import-pracownikow-nowy-autor-odpiecia.feature.rst`

**Modyfikowane:**
- `src/import_pracownikow/models.py` — pole `utworz_nowego`, model
  `ImportPracownikowOdpiecie`, przepisany `autorzy_spoza_pliku_set`, kasowanie
  odpięć w `on_restart`, usunięty `odepnij_autorow_spoza_pliku`, import `Q`.
- `src/import_pracownikow/pipeline/analyze.py` — materializacja odpięć po pętli +
  licznik w `p.result`.
- `src/import_pracownikow/pipeline/integrate.py` — pre-pass tworzenia autorów
  (D2), `_wykonaj_odpiecia`, `_opisz_utworzone` o `nowy_autor`, liczniki
  `utworzono_nowych_autorow`/`odpieto`.
- `src/import_pracownikow/views.py` — bazowy `_ImportPodgladMixin` (wydzielony
  z `_WierszImportuMixin`; ten dziedziczy po nim — F3), `PrzelaczOdpiecieView`,
  `PrzelaczUtworzNowegoView`, usunięcie `ImportPracownikowResetuj...View` +
  `autorzy_spoza_pliku()`; kontekst `odpiecia` w `ImportPracownikowResultsView`.
- `src/import_pracownikow/urls.py` — trasy `przelacz-odpiecie`, `utworz-nowego`;
  usunięcie `resetuj-podstawowe-miejsce-pracy`.
- `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  — sekcja odpięć z checkboxami zamiast starego przycisku.
- `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
  — checkbox „utwórz nowego" dla wierszy `brak`.

**Usuwane:**
- `src/import_pracownikow/tests/test_views.py` (3 testy Resetuj/odpięć — obsolete).
- `src/import_pracownikow/tests/test_models/test_odepnij_autorow_spoza_pliku.py`
  (testują usuwaną metodę `odepnij_autorow_spoza_pliku`).

**Poza zakresem (Faza 5 — nie flagować jako braki):** `przepnij_prace`,
`przemapuj_prace_autora`/`service.py`, cofanie przepięć.

---

### Task 1: Migracja 0014 — pole `utworz_nowego` + model `ImportPracownikowOdpiecie`

Schemat Fazy 4: flaga D2 na wierszu + trwały model odpięć §9.

**Files:**
- Modify: `src/import_pracownikow/models.py` (pole `utworz_nowego` na
  `ImportPracownikowRow`; klasa `ImportPracownikowOdpiecie` na końcu pliku)
- Create: `src/import_pracownikow/migrations/0014_utworz_nowego_odpiecie.py` (gen.)
- Test: `src/import_pracownikow/tests/test_models/test_odpiecie_model.py`

**Interfaces:**
- Produces:
  - `ImportPracownikowRow.utworz_nowego` (BooleanField, default=False).
  - `ImportPracownikowOdpiecie(parent FK related_name="odpiecia" CASCADE,
    autor_jednostka FK bpp.Autor_Jednostka CASCADE, zaznaczone Boolean
    default=False, wykonane Boolean default=False)`; Meta verbose_name +
    `ordering=["autor_jednostka__autor__nazwisko"]`.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_models/test_odpiecie_model.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)


@pytest.mark.django_db
def test_row_ma_pole_utworz_nowego_default_false():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False)
    row.save()
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_odpiecie_defaults_i_relacja_parent():
    imp = baker.make(ImportPracownikow)
    aj = baker.make(Autor_Jednostka)
    odp = ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    assert odp.zaznaczone is False
    assert odp.wykonane is False
    assert list(imp.odpiecia.all()) == [odp]


@pytest.mark.django_db
def test_odpiecie_ordering_po_nazwisku_autora():
    imp = baker.make(ImportPracownikow)
    aj_b = baker.make(Autor_Jednostka, autor__nazwisko="Bielecki")
    aj_a = baker.make(Autor_Jednostka, autor__nazwisko="Adamski")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj_b)
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj_a)
    nazwiska = [o.autor_jednostka.autor.nazwisko for o in imp.odpiecia.all()]
    assert nazwiska == ["Adamski", "Bielecki"]
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_odpiecie_model.py -v`
Expected: FAIL (`ImportError: cannot import name 'ImportPracownikowOdpiecie'`).

- [ ] **Step 3: Dodaj pole + model do `models.py`**

W klasie `ImportPracownikowRow`, PO polu `wybrany_kandydat = ...`, dodaj:

```python
    utworz_nowego = models.BooleanField(default=False)
```

Na końcu pliku (po `ImportPracownikowRowKandydat`) dodaj model odpięcia:

```python
class ImportPracownikowOdpiecie(models.Model):
    """Materializowana decyzja o odpięciu jednego powiązania Autor+Jednostka
    spoza pliku (§9 D3).

    Powstaje w fazie analizy dla każdego powiązania z
    ``autorzy_spoza_pliku_set`` (domyślnie ODZNACZONE); user zaznacza w
    podglądzie; faza commit kończy zatrudnienie dla ``zaznaczone=True`` i
    ustawia ``wykonane=True``. ``autor_jednostka`` wskazuje ISTNIEJĄCE
    powiązanie (realne, z pk) — do zakończenia. Decyzja jest persystowana (nie
    liczona dynamicznie), żeby przeżyła drift bazy między podglądem a commitem.
    """

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="odpiecia",
        verbose_name="import pracowników",
    )
    autor_jednostka = models.ForeignKey(
        "bpp.Autor_Jednostka",
        on_delete=models.CASCADE,
        verbose_name="powiązanie autor-jednostka",
    )
    zaznaczone = models.BooleanField(default=False)
    wykonane = models.BooleanField(default=False)

    class Meta:
        verbose_name = "odpięcie autora spoza pliku (import pracowników)"
        verbose_name_plural = "odpięcia autorów spoza pliku (import pracowników)"
        ordering = ["autor_jednostka__autor__nazwisko"]

    def __str__(self):
        return f"odpięcie {self.autor_jednostka} (zaznaczone={self.zaznaczone})"
```

- [ ] **Step 4: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name utworz_nowego_odpiecie`
Expected: utworzony `0014_utworz_nowego_odpiecie.py` (AddField `utworz_nowego` +
CreateModel `ImportPracownikowOdpiecie`). **NIE** edytuj ręcznie.

- [ ] **Step 5: Sprawdź brak driftu**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: „No changes detected".

- [ ] **Step 6: Uruchom testy — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_odpiecie_model.py -v`
Expected: PASS (3).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/migrations/0014_utworz_nowego_odpiecie.py \
  src/import_pracownikow/tests/test_models/test_odpiecie_model.py
git commit -m "feat(import_pracownikow): pole utworz_nowego + model ImportPracownikowOdpiecie (Faza 4 T1)"
```

---

### Task 2: Przepisanie `autorzy_spoza_pliku_set()` na pary (autor_id, jednostka_id)

Naprawa regresji NULL (§9): porównanie po parach z wierszy zamiast po pk AJ.

**Files:**
- Modify: `src/import_pracownikow/models.py` (metoda `autorzy_spoza_pliku_set`;
  import `Q`)
- Test: `src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py`

**Interfaces:**
- Produces: `ImportPracownikow.autorzy_spoza_pliku_set(uczelnia=None,
  today=None) -> QuerySet[Autor_Jednostka]` (sygnatura BEZ zmian; przepisane
  ciało). Kryteria wykluczeń zachowane; NULL-e wierszy odfiltrowane.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_null_autor_jednostka_nie_zeruje_zbioru(today):
    """Regresja §9: wiersz z ``autor_jednostka=None`` (odroczone AJ) NIE może
    wyzerować zbioru odpięć (stary ``NOT IN (…, NULL)`` dawał pusty zbiór).
    Para z pliku (autor, jednostka) jest chroniona, a AJ spoza pliku — nie."""
    j = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a_plik = baker.make(Autor, aktualna_jednostka=j)
    aj_plik = baker.make(Autor_Jednostka, autor=a_plik, jednostka=j)
    a_spoza = baker.make(Autor, aktualna_jednostka=j)
    aj_spoza = baker.make(Autor_Jednostka, autor=a_spoza, jednostka=j)

    imp = baker.make(ImportPracownikow)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=a_plik,
        jednostka=j,
        autor_jednostka=None,
        zmiany_potrzebne=False,
    )

    zbior = set(imp.autorzy_spoza_pliku_set(today=today))
    assert aj_spoza in zbior
    assert aj_plik not in zbior


@pytest.mark.django_db
def test_pomija_jednostki_nie_zarzadzane_automatycznie(today):
    j = baker.make(Jednostka, zarzadzaj_automatycznie=False)
    a = baker.make(Autor, aktualna_jednostka=j)
    baker.make(Autor_Jednostka, autor=a, jednostka=j)
    imp = baker.make(ImportPracownikow)
    assert list(imp.autorzy_spoza_pliku_set(today=today)) == []


@pytest.mark.django_db
def test_pomija_autorow_bez_aktualnej_jednostki(today):
    j = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor, aktualna_jednostka=None)
    baker.make(Autor_Jednostka, autor=a, jednostka=j)
    # Trigger `bpp_autor_ustaw_jednostka_aktualna_trigger` (baseline.sql, AFTER
    # INSERT ON bpp_autor_jednostka) po wstawieniu aktywnego AJ NADPISUJE
    # autor.aktualna_jednostka_id = j — dlatego `baker.make(aktualna=None)` nie
    # przetrwa. Wymuszamy stan bezpośrednim UPDATE (NIE odpala triggera AJ), by
    # realnie sprawdzić kryterium `exclude(autor__aktualna_jednostka=None)`.
    Autor.objects.filter(pk=a.pk).update(aktualna_jednostka=None)
    imp = baker.make(ImportPracownikow)
    assert list(imp.autorzy_spoza_pliku_set(today=today)) == []


@pytest.mark.django_db
def test_pomija_juz_zakonczone(today, yesterday):
    """G3: izoluje kryterium ``zakonczyl_prace``. Autor dostaje DWA AJ:
    aktywne (utrzymuje ``aktualna_jednostka`` nie-NULL i samo JEST odpięciem)
    oraz zakończone. Bez tego drugiego, aktywnego AJ trigger
    ``bpp_autor_ustaw_jednostka_aktualna`` po wstawieniu samego zakończonego AJ
    (brak aktywnych) ZERUJE ``aktualna_jednostka`` (gałąź ELSE) — wynik ``[]``
    zostałby wtedy osiągnięty przez kryterium ``aktualna_jednostka=None``, więc
    regresja usunięcia ``exclude(zakonczyl_prace__lte=today)`` przeszłaby
    niezauważona. Aktywne AJ (nie-NULL ``aktualna_jednostka``) sprawia, że o
    wyniku decyduje TYLKO ``zakonczyl_prace``: aktywne MUSI być w zbiorze,
    zakończone — nie."""
    j_aktywne = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    j_zakonczone = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor)
    aj_aktywne = baker.make(Autor_Jednostka, autor=a, jednostka=j_aktywne)
    aj_zakonczone = baker.make(
        Autor_Jednostka, autor=a, jednostka=j_zakonczone, zakonczyl_prace=yesterday
    )
    # Trigger AJ przelicza aktualną jednostkę po WSZYSTKICH AJ autora: aktywne
    # aj_aktywne utrzyma `aktualna_jednostka` = j_aktywne (nie-NULL) niezależnie
    # od kolejności wstawień.
    a.refresh_from_db()
    assert a.aktualna_jednostka_id is not None

    imp = baker.make(ImportPracownikow)
    zbior = set(imp.autorzy_spoza_pliku_set(today=today))
    assert aj_aktywne in zbior
    assert aj_zakonczone not in zbior


@pytest.mark.django_db
def test_wyklucza_obca_jednostke_uczelni(today):
    obca = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor, aktualna_jednostka=obca)
    baker.make(Autor_Jednostka, autor=a, jednostka=obca)
    imp = baker.make(ImportPracownikow)

    class _Uczelnia:
        obca_jednostka_id = obca.pk

    assert list(imp.autorzy_spoza_pliku_set(uczelnia=_Uczelnia(), today=today)) == []
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py -v`
Expected: FAIL — `test_null_autor_jednostka_nie_zeruje_zbioru` (stary
`NOT IN (…, NULL)` → `aj_spoza` poza zbiorem).

- [ ] **Step 3: Przepisz metodę + dodaj import `Q`**

W `src/import_pracownikow/models.py` zmień import kolekcji pól na:

```python
from django.db.models import JSONField, Q
```

Zastąp CAŁĄ metodę `autorzy_spoza_pliku_set` (obecnie ~linie 181–206) tą wersją:

```python
    def autorzy_spoza_pliku_set(self, uczelnia=None, today=None):
        """Powiązania Autor+Jednostka do odpięcia: pary ``(autor, jednostka)``
        OBECNE w bazie, ale NIEOBECNE w tym imporcie.

        Porównanie po parach ``(autor_id, jednostka_id)`` z wierszy (znane
        nawet gdy ``autor_jednostka`` jest NULL — odroczone AJ / statusy
        brak/wielu), z jawnym odfiltrowaniem NULL-i. NIE po pk
        ``Autor_Jednostka``: subquery z NULL-em daje SQL ``NOT IN (…, NULL)``
        → pusty zbiór (regresja §9). Kryteria wykluczeń: jednostka zarządzana
        automatycznie, nie-obca, powiązanie aktywne, autor ma aktualną
        jednostkę.
        """
        if today is None:
            today = timezone.now().date()

        pary_z_pliku = set(
            self.importpracownikowrow_set.filter(
                autor__isnull=False, jednostka__isnull=False
            )
            .values_list("autor_id", "jednostka_id")
            .distinct()
        )

        qry = (
            Autor_Jednostka.objects.exclude(autor__aktualna_jednostka=None)
            .exclude(jednostka__zarzadzaj_automatycznie=False)
            .exclude(zakonczyl_prace__lte=today)
        )

        if uczelnia is not None and uczelnia.obca_jednostka_id is not None:
            qry = qry.exclude(
                autor__aktualna_jednostka_id=uczelnia.obca_jednostka_id
            )

        if pary_z_pliku:
            wyklucz = Q()
            for autor_id, jednostka_id in pary_z_pliku:
                wyklucz |= Q(autor_id=autor_id, jednostka_id=jednostka_id)
            qry = qry.exclude(wyklucz)

        return qry
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py -v`
Expected: PASS (5).

- [ ] **Step 5: Sprawdź linie ≤88 + ruff**

Run: `awk 'length>88{print FILENAME":"NR}' src/import_pracownikow/models.py`
oraz `uv run ruff check src/import_pracownikow/models.py`
Expected: brak wyjścia z `awk`; ruff czysty.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/tests/test_models/test_autorzy_spoza_pliku_set.py
git commit -m "fix(import_pracownikow): autorzy_spoza_pliku_set po parach (autor,jednostka) — regresja NULL (Faza 4 T2)"
```

---

### Task 3: Materializacja odpięć w `analizuj` + kasowanie w `on_restart` + licznik

**Files:**
- Modify: `src/import_pracownikow/pipeline/analyze.py` (funkcja
  `_materializuj_odpiecia` + wywołanie w `analizuj` + licznik `p.result`)
- Modify: `src/import_pracownikow/models.py` (`on_restart` kasuje odpięcia)
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py`

**Interfaces:**
- Consumes: `ImportPracownikow.autorzy_spoza_pliku_set` (T2),
  `ImportPracownikowOdpiecie` (T1),
  `Uczelnia.objects.get_single_uczelnia_or_none`.
- Produces:
  - `_materializuj_odpiecia(parent) -> int` (delete-first + `bulk_create`;
    zwraca liczbę odpięć).
  - `analizuj` wynik `p.result(...)` dostaje klucz `"odpiecia"`.
  - `ImportPracownikow.on_restart()` kasuje też `self.odpiecia`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py`:

```python
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie
from import_pracownikow.pipeline.analyze import analizuj


@pytest.mark.django_db
def test_on_restart_kasuje_odpiecia():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    aj = baker.make(Autor_Jednostka)
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    imp.on_restart()
    assert imp.odpiecia.count() == 0


@pytest.mark.django_db
def test_analiza_materializuje_odpiecia_i_liczy(
    import_pracownikow, autor_spoza_pliku, jednostka_spoza_pliku
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    aj_spoza = autor_spoza_pliku.autor_jednostka_set.get(
        jednostka=jednostka_spoza_pliku
    )

    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    p = MockProgress(import_pracownikow)
    analizuj(import_pracownikow, p)

    assert import_pracownikow.odpiecia.filter(autor_jednostka=aj_spoza).exists()
    assert all(not o.zaznaczone for o in import_pracownikow.odpiecia.all())
    assert p.result_context["odpiecia"] >= 1


@pytest.mark.django_db
def test_reanaliza_nie_duplikuje_odpiec(
    import_pracownikow, autor_spoza_pliku, jednostka_spoza_pliku
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)

    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    analizuj(import_pracownikow, MockProgress(import_pracownikow))
    liczba1 = import_pracownikow.odpiecia.count()
    assert liczba1 >= 1

    # ponowna analiza: cofnięcie do zmapowany kasuje wiersze+odpiecia, potem
    # analiza tworzy je od nowa — bez duplikacji.
    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    import_pracownikow.on_restart()
    analizuj(import_pracownikow, MockProgress(import_pracownikow))
    assert import_pracownikow.odpiecia.count() == liczba1
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py -v`
Expected: FAIL (`on_restart` nie kasuje odpięć; `analizuj` nie materializuje /
brak klucza `"odpiecia"`).

- [ ] **Step 3: Dołóż kasowanie odpięć w `on_restart`**

W `src/import_pracownikow/models.py`, w metodzie `on_restart`, w gałęzi kasującej
wiersze, dodaj kasowanie odpięć:

```python
    def on_restart(self):
        # kasujemy wiersze przy (ponownej) analizie: świeży upload czeka w
        # utworzony (bez wierszy), ponowna analiza cofa do zmapowany.
        if self.stan in (self.STAN_UTWORZONY, self.STAN_ZMAPOWANY):
            self.importpracownikowrow_set.all().delete()
            # Odpięcia (§9) materializuje faza analizy — przy cofnięciu do
            # zmapowany kasujemy je razem z wierszami, żeby ponowna analiza
            # nie zduplikowała zbioru.
            self.odpiecia.all().delete()
```

- [ ] **Step 4: Dodaj materializację odpięć w `analizuj`**

W `src/import_pracownikow/pipeline/analyze.py` rozszerz import z `bpp.models` o
`Uczelnia` oraz import modeli importu o `ImportPracownikowOdpiecie`:

```python
from bpp.models import Autor_Jednostka, Jednostka, Tytul, Uczelnia
```

```python
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    JednostkaForm,
)
```

Dodaj funkcję (np. nad `def analizuj`):

```python
def _materializuj_odpiecia(parent):
    """Tworzy wiersze ``ImportPracownikowOdpiecie`` (zaznaczone=False) dla
    powiązań spoza pliku (§9). Delete-first → idempotentne względem re-analizy
    (``on_restart`` też je kasuje). Uczelnię ustala
    ``get_single_uczelnia_or_none`` (brak requestu w tle) — ``None`` pomija
    wykluczenie obcej jednostki. Zwraca liczbę utworzonych odpięć."""
    uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
    parent.odpiecia.all().delete()
    ImportPracownikowOdpiecie.objects.bulk_create(
        [
            ImportPracownikowOdpiecie(parent=parent, autor_jednostka=aj)
            for aj in parent.autorzy_spoza_pliku_set(uczelnia=uczelnia)
        ]
    )
    return parent.odpiecia.count()
```

W `analizuj`, PO pętli `for elem in p.track(...)`, PRZED ustawieniem
`parent.stan`, dodaj materializację i uwzględnij licznik w `p.result`:

```python
    liczba_odpiec = _materializuj_odpiecia(parent)

    parent.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    parent.save(update_fields=["stan"])

    wiersze = parent.get_details_set()
    p.result(
        {
            "total": wiersze.count(),
            "zmiany_potrzebne": parent.zmiany_potrzebne_set.count(),
            "odpiecia": liczba_odpiec,
            "byl_dry_run": True,
            "stan": parent.stan,
        }
    )
```

- [ ] **Step 5: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py -v`
Expected: PASS (3).

- [ ] **Step 6: Regresja analizy Faz 0–3**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/ -q`
Expected: PASS (materializacja odpięć nie psuje istniejących testów analizy).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/models.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_odpiecia.py
git commit -m "feat(import_pracownikow): materializacja odpięć w analizie + kasowanie w on_restart (Faza 4 T3)"
```

---

### Task 4: Widok toggle `zaznaczone` odpięcia (HTMX) + URL + partial

**Files:**
- Create: `src/import_pracownikow/templates/import_pracownikow/partials/_odpiecie_row.html`
- Modify: `src/import_pracownikow/views.py` — nowy bazowy mixin
  `_ImportPodgladMixin` (wydzielony ze wspólnego `parent_object` +
  `_blad_jesli_nie_podglad`); refaktor istniejącego `_WierszImportuMixin` z Fazy
  3 (dziedziczy po `_ImportPodgladMixin`, dokłada tylko `row`/`_render_wiersz`/
  `partial_template`); nowy `PrzelaczOdpiecieView(_ImportPodgladMixin)`; import
  `ImportPracownikowOdpiecie`
- Modify: `src/import_pracownikow/urls.py` (trasa `przelacz-odpiecie`)
- Test: `src/import_pracownikow/tests/test_views_odpiecie.py`

**Interfaces:**
- Consumes: `ImportPracownikowOdpiecie` (T1), `GROUP_REQUIRED`.
- Produces:
  - `_ImportPodgladMixin(GroupRequiredMixin, View)`: owner/superuser-scoped
    `cached_property parent_object` + `_blad_jesli_nie_podglad` (bramka stanu
    `przeanalizowany`). Bazowy dla `_WierszImportuMixin` (Faza 3) i
    `PrzelaczOdpiecieView` — jedna kopia bramki/scopingu (koniec duplikacji).
  - `_WierszImportuMixin(_ImportPodgladMixin)`: bez zmian w zachowaniu — nadal
    wystawia `row`/`parent_object`/`_blad_jesli_nie_podglad`/`_render_wiersz`
    (te dwa ostatnie via bazę), więc T7 (`PrzelaczUtworzNowegoView`) działa bez
    zmian.
  - `PrzelaczOdpiecieView(_ImportPodgladMixin)` (POST HTMX): dokłada `odpiecie`
    + `post`, ustawia `odp.zaznaczone` z obecności pola `zaznaczone` w POST,
    zwraca partial `_odpiecie_row.html`.
  - URL name `import_pracownikow:przelacz-odpiecie` (kwargs `pk`, `odp_pk`).

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_views_odpiecie.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie


def _odpiecie(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    imp = baker.make(ImportPracownikow, owner=owner, stan=stan)
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Testowski")
    odp = ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    return imp, odp


@pytest.mark.django_db
def test_zaznaczenie_odpiecia_ustawia_flage(admin_client, admin_user):
    imp, odp = _odpiecie(admin_user)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = admin_client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 200
    assert b"Testowski" in resp.content
    odp.refresh_from_db()
    assert odp.zaznaczone is True

    resp = admin_client.post(url, {})
    odp.refresh_from_db()
    assert odp.zaznaczone is False


@pytest.mark.django_db
def test_odpiecie_blokada_poza_podgladem(admin_client, admin_user):
    imp, odp = _odpiecie(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = admin_client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 400
    odp.refresh_from_db()
    assert odp.zaznaczone is False


@pytest.mark.django_db
def test_odpiecie_cudzy_import_404(client, django_user_model, admin_user):
    imp, odp = _odpiecie(admin_user)
    obcy = django_user_model.objects.create_user(
        username="obcy", password="x", is_superuser=False
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    obcy.groups.add(grupa)
    client.force_login(obcy)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_odpiecie.py -v`
Expected: FAIL (`NoReverseMatch: 'przelacz-odpiecie'`).

- [ ] **Step 3: Utwórz partial `_odpiecie_row.html`**

Utwórz
`src/import_pracownikow/templates/import_pracownikow/partials/_odpiecie_row.html`:

```django
{# Partial pojedynczego odpięcia autora spoza pliku (materializowane §9). #}
{# Zwracany po przełączeniu checkboxa (HTMX) oraz include w liście podglądu. #}
<tr id="odpiecie-{{ odp.pk }}">
    <td>{{ odp.autor_jednostka.autor }}</td>
    <td>{{ odp.autor_jednostka.jednostka }}</td>
    <td>
        {% if parent_object.stan == "przeanalizowany" %}
            {# checkbox domyślnie ODZNACZONY; zmiana → POST toggluje zaznaczone #}
            <form method="post"
                  hx-post="{% url "import_pracownikow:przelacz-odpiecie" pk=parent_object.pk odp_pk=odp.pk %}"
                  hx-target="#odpiecie-{{ odp.pk }}"
                  hx-swap="outerHTML"
                  hx-trigger="change">
                {% csrf_token %}
                <label>
                    <input type="checkbox" name="zaznaczone"
                           {% if odp.zaznaczone %}checked{% endif %}>
                    <i class="fi-x"></i> odepnij
                </label>
            </form>
        {% elif odp.wykonane %}
            <span class="label success"><i class="fi-check"></i> odpięto</span>
        {% endif %}
    </td>
</tr>
```

- [ ] **Step 4: Wydziel `_ImportPodgladMixin`, zrefaktoruj `_WierszImportuMixin`, dodaj `PrzelaczOdpiecieView`**

W `src/import_pracownikow/views.py` rozszerz import modeli importu o
`ImportPracownikowOdpiecie`:

```python
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ProfilMapowania,
)
```

**F3 (koniec duplikacji):** `PrzelaczOdpiecieView` potrzebuje tego samego
owner/superuser-scoped `parent_object` i tej samej bramki stanu co
`_WierszImportuMixin` (Faza 3). Zamiast kopiować je 1:1 (mina utrzymaniowa —
poprawka scopingu/bramki w 2 miejscach), wydzielamy bazowy `_ImportPodgladMixin`
i przepinamy istniejący `_WierszImportuMixin` na dziedziczenie po nim. **To
DOTYKA kodu Fazy 3** — `_WierszImportuMixin` (obecnie ~linie 185–227) traci
własne `parent_object`/`_blad_jesli_nie_podglad` (przechodzą do bazy) i zostawia
tylko `partial_template`/`row`/`_render_wiersz`. Zachowanie bez zmian: bazowy
`parent_object` jest superuser-aware (jak dotychczasowy), więc superuser dalej
widzi cudze importy, a nie-właściciel-nie-superuser dostaje 404.

ZASTĄP istniejącą klasę `_WierszImportuMixin` (od `class _WierszImportuMixin` do
końca metody `_render_wiersz`) tym blokiem — bazowy mixin + odchudzony
`_WierszImportuMixin`:

```python
class _ImportPodgladMixin(GroupRequiredMixin, View):
    """Wspólna bramka podglądu importu (owner/superuser scoping + stan
    ``przeanalizowany``) dla widoków HTMX modyfikujących decyzje wiersza/odpięcia
    (Faza 3/4). Wydzielona, żeby scoping i bramka żyły w JEDNYM miejscu —
    dziedziczą po niej ``_WierszImportuMixin`` (dokłada ``row``/``_render_wiersz``)
    i ``PrzelaczOdpiecieView`` (dokłada ``odpiecie``)."""

    group_required = GROUP_REQUIRED

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if (
            obj.owner_id != self.request.user.pk
            and not self.request.user.is_superuser
        ):
            raise Http404
        return obj

    def _blad_jesli_nie_podglad(self):
        """G3: modyfikacje decyzji (wybór/edycja/odpięcie/utwórz-nowego)
        dozwolone WYŁĄCZNIE dla importu w podglądzie (``przeanalizowany``). Bez
        tej bramki bezpośredni POST (retry HTMX, back-button, wyścig z Zatwierdź)
        na imporcie już `zintegrowanym` nadpisałby audyt ``log_zmian`` po
        commicie / zmienił decyzję odpięcia po jej wykonaniu. Analog
        `_STANY_MAPOWALNE` — zintegrowany wykluczony. Zwraca
        ``HttpResponseBadRequest`` (blokada) albo ``None`` (OK)."""
        if self.parent_object.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Wiersz można edytować tylko dla importu w podglądzie."
            )
        return None


class _WierszImportuMixin(_ImportPodgladMixin):
    """Wspólny fetch wiersza importu (dokłada ``row`` do bazowej bramki
    ``_ImportPodgladMixin``). Render partiala do odpowiedzi HTMX."""

    partial_template = "import_pracownikow/partials/_wiersz_preview.html"

    @cached_property
    def row(self):
        return get_object_or_404(
            ImportPracownikowRow, pk=self.kwargs["row_pk"], parent=self.parent_object
        )

    def _render_wiersz(self):
        # Re-pobierz wiersz przez get_details_set(), żeby partial miał adnotacje
        # nr_arkusza/nr_wiersza (RawSQL) — inaczej te komórki byłyby puste po
        # swapie HTMX. Odzwierciedla zapisane właśnie zmiany.
        row = self.parent_object.get_details_set().get(pk=self.row.pk)
        return render(
            self.request,
            self.partial_template,
            {"row": row, "parent_object": self.parent_object},
        )
```

Dodaj widok (np. po `EdytujWierszView`):

```python
class PrzelaczOdpiecieView(_ImportPodgladMixin):
    """POST (HTMX): ustaw ``zaznaczone`` odpięcia (§9) z obecności pola
    ``zaznaczone`` w POST. Owner/superuser-scoped + bramka stanu
    ``przeanalizowany`` — via ``_ImportPodgladMixin``. Zwraca partial
    ``_odpiecie_row.html``."""

    partial_template = "import_pracownikow/partials/_odpiecie_row.html"

    @cached_property
    def odpiecie(self):
        return get_object_or_404(
            ImportPracownikowOdpiecie,
            pk=self.kwargs["odp_pk"],
            parent=self.parent_object,
        )

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        odp = self.odpiecie
        odp.zaznaczone = request.POST.get("zaznaczone") is not None
        odp.save(update_fields=["zaznaczone"])
        return render(
            request,
            self.partial_template,
            {"odp": odp, "parent_object": self.parent_object},
        )
```

- [ ] **Step 5: Dodaj trasę do `urls.py`**

W `src/import_pracownikow/urls.py`, dodaj do `urlpatterns`:

```python
    path(
        "<uuid:pk>/odpiecie/<int:odp_pk>/przelacz/",
        views.PrzelaczOdpiecieView.as_view(),
        name="przelacz-odpiecie",
    ),
```

- [ ] **Step 6: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_odpiecie.py -v`
Expected: PASS (3).

- [ ] **Step 7: Regresja Fazy 3 (refaktor `_WierszImportuMixin`)**

Refaktor F3 przepiął `_WierszImportuMixin` na dziedziczenie po
`_ImportPodgladMixin` — potwierdź, że widoki wiersza z Fazy 3 dalej działają
(scoping owner/superuser + bramka stanu bez zmian):

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py -v`
Expected: PASS (bez zmian względem Fazy 3 — `parent_object`/
`_blad_jesli_nie_podglad` przeniesione do bazy zachowują zachowanie).

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/templates/import_pracownikow/partials/_odpiecie_row.html \
  src/import_pracownikow/tests/test_views_odpiecie.py
git commit -m "feat(import_pracownikow): widok toggle odpięcia + partial, wydziel _ImportPodgladMixin (Faza 4 T4)"
```

---

### Task 5: Commit odpięć w `integruj` (re-check + zakończenie zatrudnienia)

**Files:**
- Modify: `src/import_pracownikow/pipeline/integrate.py` (`_wykonaj_odpiecia` +
  wywołanie w `integruj` + licznik `odpieto`; importy `timedelta`, `timezone`)
- Test: `src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py`

**Interfaces:**
- Consumes: `ImportPracownikowOdpiecie` (T1).
- Produces:
  - `_wykonaj_odpiecia(parent) -> int` (iteruje `zaznaczone=True, wykonane=False`,
    świeży re-check, kończy zatrudnienie, ustawia `wykonane=True`; zwraca liczbę
    faktycznie odpiętych).
  - `integruj` wynik `p.result(...)` dostaje klucz `"odpieto"`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py`:

```python
from datetime import timedelta

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_wykonuje_zaznaczone_odpiecie(yesterday):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka, podstawowe_miejsce_pracy=True)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == yesterday
    assert aj.podstawowe_miejsce_pracy is False
    assert odp.wykonane is True
    assert p.result_context["odpieto"] == 1


@pytest.mark.django_db
def test_commit_pomija_niezaznaczone_odpiecie():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=False
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace is None
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0


@pytest.mark.django_db
def test_commit_pomija_juz_zakonczone_recznie(today):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    wczesniej = today - timedelta(days=3)
    aj = baker.make(Autor_Jednostka, zakonczyl_prace=wczesniej)
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace == wczesniej
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0


@pytest.mark.django_db
def test_commit_pomija_odpiecie_pary_z_pliku():
    """G1: odpięcie zmaterializowane w analizie (gdy wiersz miał autor=None),
    ale user rozstrzygnął potem wiersz na TĘ parę (autor_id, jednostka_id) —
    para jest teraz W PLIKU, więc re-check MUSI pominąć odpięcie: AJ NIETKNIĘTE
    (``zakonczyl_prace`` nadal None, ``podstawowe`` niezmienione),
    ``wykonane=False``, licznik ``odpieto=0``."""
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    aj = baker.make(Autor_Jednostka, podstawowe_miejsce_pracy=True)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=aj.autor,
        jednostka=aj.jednostka,
        zmiany_potrzebne=False,
    )
    odp = ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, zaznaczone=True
    )
    p = MockProgress(imp)
    integruj(imp, p)

    aj.refresh_from_db()
    odp.refresh_from_db()
    assert aj.zakonczyl_prace is None
    assert aj.podstawowe_miejsce_pracy is True
    assert odp.wykonane is False
    assert p.result_context["odpieto"] == 0
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py -v`
Expected: FAIL (`KeyError: 'odpieto'` / brak wykonania odpięć).

- [ ] **Step 3: Dodaj `_wykonaj_odpiecia` + wpięcie w `integruj`**

W `src/import_pracownikow/pipeline/integrate.py` dodaj importy u góry:

```python
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
```

(`from django.db import transaction` już istnieje — nie duplikuj; dopisz tylko
`timedelta` i `timezone`.)

Dodaj funkcję (np. nad `def integruj`):

```python
def _wykonaj_odpiecia(parent):
    """Kończy zatrudnienie dla zaznaczonych, jeszcze niewykonanych odpięć (§9).

    Świeży re-check ma DWA warunki pomijające (oba: NIE wykonuj, NIE licz,
    ``wykonane`` zostaje False):

    1. **Para stała się parą Z PLIKU (G1).** Odpięcia materializują się w
       analizie, gdy wiersze ``wielu``/``brak`` mają ``autor=None`` — więc AJ
       PRAWDZIWEGO autora z pliku trafia na listę „spoza pliku". Gdy user potem
       rozstrzygnie wiersz (``WybierzKandydataView``/``EdytujWierszView`` ustawia
       ``row.autor``), zmaterializowane odpięcie ZOSTAJE. Gdyby je wykonać,
       zakończylibyśmy zatrudnienie pracownika, który JEST w pliku (korupcja).
       Dlatego przed wykonaniem sprawdzamy, czy para ``(autor_id, jednostka_id)``
       AJ jest teraz obecna w wierszach importu — jeśli tak, POMIJAMY (spójne z
       definicją „spoza pliku" §9 i duchem świeżego re-checku).
    2. **AJ zakończone ręcznie od czasu podglądu (drift bazy).** ``zakonczyl_prace
       is not None and <= today`` → pomijamy (NIE nadpisujemy daty).

    Wykonane: ``zakonczyl_prace = wczoraj``, ``podstawowe_miejsce_pracy =
    False``, ``wykonane = True``. Zwraca liczbę faktycznie odpiętych."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    odpieto = 0
    for odp in parent.odpiecia.filter(zaznaczone=True, wykonane=False):
        with transaction.atomic():
            aj = odp.autor_jednostka
            aj.refresh_from_db()
            # G1: para AJ trafiła do pliku po rozstrzygnięciu wiersza — to już
            # pracownik Z PLIKU, NIE odpinamy (wykonane zostaje False).
            if parent.importpracownikowrow_set.filter(
                autor_id=aj.autor_id, jednostka_id=aj.jednostka_id
            ).exists():
                continue
            if aj.zakonczyl_prace is not None and aj.zakonczyl_prace <= today:
                # zakończone ręcznie — pomijamy, nie nadpisujemy daty.
                continue
            aj.zakonczyl_prace = yesterday
            aj.podstawowe_miejsce_pracy = False
            aj.save()
            odp.wykonane = True
            odp.save(update_fields=["wykonane"])
            odpieto += 1
    return odpieto
```

W `integruj`, PO pętli `for row in p.track(...)` a PRZED ustawieniem
`parent.stan`, wykonaj odpięcia i dodaj licznik do `p.result`:

```python
    odpieto = _wykonaj_odpiecia(parent)

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])
```

W finalnym `p.result({...})` dodaj klucz `"odpieto": odpieto` (obok
istniejących `zintegrowano`/`pominieto_nieaktualne`/`pominieto_niedopasowane`/
`wymaga_uwagi`/`stan`).

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/tests/test_pipeline/test_integrate_odpiecia.py
git commit -m "feat(import_pracownikow): commit odpięć z re-checkiem w integracji (Faza 4 T5)"
```

---

### Task 6: Usunięcie Faza-0 stopgap (odepnij / ResetujView / url) + ich testów

Decyzja A (wariant „a"): czyste usunięcie natychmiastowego odpięcia z przycisku —
zastępuje je materializowany przepływ (T3–T5).

**Files:**
- Modify: `src/import_pracownikow/models.py` (usuń `odepnij_autorow_spoza_pliku`)
- Modify: `src/import_pracownikow/views.py` (usuń `ImportPracownikowResetuj
  PodstawoweMiejscePracyView` i metodę `autorzy_spoza_pliku()`; uprość
  `get_context_data`; usuń nieużywany import `Uczelnia`)
- Modify: `src/import_pracownikow/urls.py` (usuń trasę
  `resetuj-podstawowe-miejsce-pracy`)
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  (usuń starą sekcję `autorzy_spoza_pliku` z przyciskiem)
- Delete: `src/import_pracownikow/tests/test_views.py`
- Delete: `src/import_pracownikow/tests/test_models/test_odepnij_autorow_spoza_pliku.py`

**Interfaces:**
- Removes: `ImportPracownikow.odepnij_autorow_spoza_pliku`,
  `ImportPracownikowResetujPodstawoweMiejscePracyView`,
  `ImportPracownikowResultsView.autorzy_spoza_pliku`, url name
  `importpracownikow-resetuj-podstawowe-miejsce-pracy`.
- Keeps: `autorzy_spoza_pliku_set` (T2), materializowany przepływ (T3–T5).

- [ ] **Step 1: Usuń metodę modelu**

W `src/import_pracownikow/models.py` USUŃ całą metodę
`odepnij_autorow_spoza_pliku` (dekorator `@transaction.atomic` + ciało, obecnie
~linie 208–221). NIE ruszaj `autorzy_spoza_pliku_set` (T2) ani importu
`transaction` (używa go `ImportPracownikowRow.integrate`).

**G2 (osierocony import `timedelta`):** `odepnij_autorow_spoza_pliku` (linia
~214) był JEDYNYM użytkownikiem `timedelta` w `models.py`. Po jego usunięciu
zmień import (linia 2) z:

```python
from datetime import date, timedelta
```

na:

```python
from datetime import date
```

(`date` ZOSTAJE — używa go `_normalizuj_daty` ~linie 284/286.) Zweryfikuj, że
`timedelta` nie występuje nigdzie indziej w pliku:
`grep -n "timedelta" src/import_pracownikow/models.py` → brak wyników. Inaczej
`uv run ruff check` (T10 Step 5) padnie na F401.

- [ ] **Step 2: Usuń widok Resetuj + metodę kontekstu + uprość `get_context_data`**

W `src/import_pracownikow/views.py`:

- USUŃ całą klasę `ImportPracownikowResetujPodstawoweMiejscePracyView`.
- W `ImportPracownikowResultsView` USUŃ metodę `autorzy_spoza_pliku`.
- Zastąp `get_context_data` w `ImportPracownikowResultsView` tą wersją (bez
  dynamicznego zbioru — materializowane odpięcia doda T9):

```python
    def get_context_data(self, **kwargs):
        return super().get_context_data(
            parent_object=self.parent_object,
            **kwargs,
        )
```

- Zmień import `from bpp.models import Tytul, Uczelnia` na `from bpp.models
  import Tytul` (Uczelnia była używana tylko w usuwanych miejscach).

- [ ] **Step 3: Usuń trasę URL**

W `src/import_pracownikow/urls.py` USUŃ blok `path(...
"resetuj-podstawowe-miejsce-pracy"...)` (name
`importpracownikow-resetuj-podstawowe-miejsce-pracy`).

- [ ] **Step 4: Usuń starą sekcję z szablonu listy**

W
`src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
USUŃ cały blok od `{% if autorzy_spoza_pliku.exists %}` do jego `{% endif %}`
(razem z linkiem `<a href="../resetuj-podstawowe-miejsce-pracy/">` i gałęzią
`{% else %}` „Zawartość tego pliku nie powoduje..."). Zostaw resztę bloku
`content` (nagłówek audytu + tabela wierszy) nietkniętą. Materializowana sekcja
odpięć wejdzie w T9.

- [ ] **Step 5: Usuń obsolete testy**

```bash
git rm src/import_pracownikow/tests/test_views.py \
  src/import_pracownikow/tests/test_models/test_odepnij_autorow_spoza_pliku.py
```

- [ ] **Step 6: Uruchom — regresja przepływu**

Run: `uv run pytest src/import_pracownikow/ -q`
Expected: PASS (żaden pozostały test nie odwołuje się do usuniętego
url/metody/widoku; `test_views_liveops.py` dalej znajduje nagłówek audytu „Lista
modyfikacji" — usunęliśmy tylko sekcję odpięć). Podaj liczbę passed.

- [ ] **Step 7: Commit**

```bash
git add -A src/import_pracownikow/
git commit -m "refactor(import_pracownikow): usuń Faza-0 stopgap odpięć (przycisk/url/metoda) na rzecz przepływu analiza→commit (Faza 4 T6)"
```

---

### Task 7: Pole+widok toggle `utworz_nowego` dla wierszy `brak` (HTMX)

**Files:**
- Modify: `src/import_pracownikow/views.py` (`PrzelaczUtworzNowegoView`; import
  `STATUS_BRAK`)
- Modify: `src/import_pracownikow/urls.py` (trasa `utworz-nowego`)
- Test: `src/import_pracownikow/tests/test_views_utworz_nowego.py`

**Interfaces:**
- Consumes: `_WierszImportuMixin` (Fazy 3 — `row`, `parent_object`,
  `_blad_jesli_nie_podglad`, `_render_wiersz`), `pewnosc.STATUS_BRAK`.
- Produces:
  - `PrzelaczUtworzNowegoView` (POST HTMX): tylko dla wierszy
    `confidence == brak`, ustawia `row.utworz_nowego` z obecności pola
    `utworz_nowego` w POST, zwraca partial wiersza.
  - URL name `import_pracownikow:utworz-nowego` (kwargs `pk`, `row_pk`).

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_views_utworz_nowego.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY


def _wiersz(owner, confidence=STATUS_BRAK,
            stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    imp = baker.make(ImportPracownikow, owner=owner, stan=stan)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        confidence=confidence,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
    )
    return imp, row


@pytest.mark.django_db
def test_toggle_utworz_nowego_ustawia_flage(admin_client, admin_user):
    imp, row = _wiersz(admin_user)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.utworz_nowego is True

    resp = admin_client.post(url, {})
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_toggle_odrzuca_wiersz_nie_brak(admin_client, admin_user):
    imp, row = _wiersz(admin_user, confidence=STATUS_TWARDY)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_toggle_blokada_poza_podgladem(admin_client, admin_user):
    imp, row = _wiersz(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_utworz_nowego.py -v`
Expected: FAIL (`NoReverseMatch: 'utworz-nowego'`).

- [ ] **Step 3: Dodaj widok do `views.py`**

W `src/import_pracownikow/views.py` rozszerz import z `pewnosc` o `STATUS_BRAK`:

```python
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    oblicz_status_pewnosci,
    odtworz_autor_jednostka,
    wybierz_autora_z_kandydatow,
)
```

Dodaj widok (np. po `EdytujWierszView`, przed `ImportPracownikowResultsView`):

```python
class PrzelaczUtworzNowegoView(_WierszImportuMixin):
    """POST (HTMX): przełącz flagę ``utworz_nowego`` dla wiersza ``brak``
    (D2). Tworzenie nowego autora nastąpi dopiero w fazie commit (integracja) —
    dry-run nic nie tworzy. Wzorzec jak ``WybierzKandydataView``: owner-scoped,
    bramka stanu ``przeanalizowany``. Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        if row.confidence != STATUS_BRAK:
            return HttpResponseBadRequest(
                "„Utwórz nowego” dotyczy tylko wierszy bez dopasowania."
            )
        row.utworz_nowego = request.POST.get("utworz_nowego") is not None
        row.save(update_fields=["utworz_nowego"])
        return self._render_wiersz()
```

- [ ] **Step 4: Dodaj trasę do `urls.py`**

W `src/import_pracownikow/urls.py`, dodaj do `urlpatterns`:

```python
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/utworz-nowego/",
        views.PrzelaczUtworzNowegoView.as_view(),
        name="utworz-nowego",
    ),
```

- [ ] **Step 5: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_utworz_nowego.py -v`
Expected: PASS (3).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/tests/test_views_utworz_nowego.py
git commit -m "feat(import_pracownikow): widok toggle utworz_nowego dla wierszy brak (Faza 4 T7)"
```

---

### Task 8: Integracja D2 — tworzenie nowego `Autor` przy `utworz_nowego`

**Files:**
- Modify: `src/import_pracownikow/pipeline/integrate.py`
  (`_przygotuj_nowego_autora`, pre-pass w `integruj`, `_opisz_utworzone` o
  `nowy_autor`, licznik `utworzono_nowych_autorow`; importy `Autor`,
  `odtworz_autor_jednostka`)
- Test: `src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py`

**Interfaces:**
- Consumes: `bpp.models.Autor`, `pewnosc.odtworz_autor_jednostka`,
  `pewnosc.STATUS_BRAK`, istniejące `_integruj_wiersz`/`_materializuj_diff`/
  `_opisz_utworzone`.
- Produces:
  - `_przygotuj_nowego_autora(row, cache) -> bool` (tworzy LUB reużywa `Autor`
    — G4 dedup po `(nazwisko, imiona, tytul_id)`, ustawia `row.autor`,
    `odtworz_autor_jednostka`, marker `diff_do_utworzenia["nowy_autor"]` tylko
    przy realnym create; NIE integruje — robi to główna pętla; owinięte w
    `transaction.atomic` — F4; zwraca `False` bez tworzenia gdy `imię` puste
    (F5) albo gdy autor zreużyty z cache — `True` tylko przy realnym create).
  - `integruj` pre-pass po wierszach `confidence=brak, utworz_nowego=True,
    autor is None`; wynik `p.result(...)` dostaje klucz
    `"utworzono_nowych_autorow"`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py`:

```python
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK
from import_pracownikow.pipeline.integrate import integruj


def _wiersz_brak(jednostka, utworz_nowego):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka,
        confidence=STATUS_BRAK,
        utworz_nowego=utworz_nowego,
        dane_znormalizowane={"nazwisko": "Nowakowski", "imię": "Grzegorz"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    return imp, row


@pytest.mark.django_db
def test_commit_tworzy_nowego_autora(autor_jednostka_fixture):
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=True)
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.nazwisko == "Nowakowski"
    assert row.autor.imiona == "Grzegorz"
    assert Autor_Jednostka.objects.filter(
        autor=row.autor, jednostka=jednostka
    ).exists()
    assert p.result_context["utworzono_nowych_autorow"] == 1
    assert any("nowy autor" in x for x in row.log_zmian.get("utworzono", []))


@pytest.mark.django_db
def test_commit_pomija_brak_bez_utworz_nowego(autor_jednostka_fixture):
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=False)
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is None
    assert Autor.objects.count() == liczba_przed
    assert p.result_context["utworzono_nowych_autorow"] == 0
    assert p.result_context["pominieto_niedopasowane"] == 1


@pytest.mark.django_db
def test_commit_nie_tworzy_autora_z_pustym_imieniem(autor_jednostka_fixture):
    """F5: wiersz ``brak`` z ``utworz_nowego=True`` ale pustym ``imię`` (korekta
    na samo nazwisko przez EdytujWierszView, który NIE waliduje imienia) → autor
    NIE powstaje, wiersz zostaje autor=None i liczy się jako niedopasowany."""
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=True)
    row.dane_znormalizowane = {"nazwisko": "Bezimienny", "imię": ""}
    row.save(update_fields=["dane_znormalizowane"])
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is None
    assert Autor.objects.count() == liczba_przed
    assert p.result_context["utworzono_nowych_autorow"] == 0
    assert p.result_context["pominieto_niedopasowane"] == 1


@pytest.mark.django_db
def test_commit_dedup_tej_samej_osoby_multietat(autor_jednostka_fixture):
    """G4: dwa wiersze ``brak`` tej SAMEJ osoby (identyczne nazwisko/imiona/
    tytuł) w RÓŻNYCH jednostkach, oba ``utworz_nowego=True`` → pre-pass tworzy
    JEDEN ``Autor`` i DWA ``Autor_Jednostka`` (multi-etat), licznik = 1.
    Bez dedupu powstaliby dwaj autorzy-duplikaci."""
    _, jednostka1 = autor_jednostka_fixture
    jednostka2 = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    dane = {"nazwisko": "Multietatowy", "imię": "Roman"}
    row1 = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka1,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    row2 = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka2,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row1.refresh_from_db()
    row2.refresh_from_db()
    assert row1.autor is not None
    assert row1.autor == row2.autor
    assert Autor.objects.count() == liczba_przed + 1
    assert (
        Autor_Jednostka.objects.filter(autor=row1.autor).count() == 2
    )
    assert p.result_context["utworzono_nowych_autorow"] == 1
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py -v`
Expected: FAIL (`KeyError: 'utworzono_nowych_autorow'` / autor nie powstaje).

- [ ] **Step 3: Rozszerz `integrate.py`**

W `src/import_pracownikow/pipeline/integrate.py` rozszerz importy:

```python
from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Wymiar_Etatu,
)
```

```python
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_WIELU,
    odtworz_autor_jednostka,
)
```

W `_opisz_utworzone`, na POCZĄTKU budowania listy `opisy`, dodaj obsługę
markera `nowy_autor`:

```python
def _opisz_utworzone(diff):
    """Krótkie opisy obiektów utworzonych z ``diff_do_utworzenia`` — do
    ``log_zmian["utworzono"]``, żeby audyt widział realną pracę wykonaną
    przez materializację nawet gdy świeży recheck nie wykrył driftu."""
    opisy = []
    if "nowy_autor" in diff:
        opisy.append(f"nowy autor: {diff['nowy_autor']}")
    if "funkcja_autora" in diff:
        opisy.append(f"funkcja: {diff['funkcja_autora']}")
    if "grupa_pracownicza" in diff:
        opisy.append(f"grupa pracownicza: {diff['grupa_pracownicza']}")
    if "wymiar_etatu" in diff:
        opisy.append(f"wymiar etatu: {diff['wymiar_etatu']}")
    if "autor_jednostka" in diff:
        opisy.append("powiązanie autor-jednostka")
    return opisy
```

Dodaj funkcję (np. nad `def integruj`):

(`from django.db import transaction` już istnieje w `integrate.py` — nie
duplikuj; T5 też z niego korzysta.)

```python
def _przygotuj_nowego_autora(row, cache):
    """D2: dla wiersza ``brak`` z ``utworz_nowego=True`` tworzy (albo REUŻYWA —
    G4) ``bpp.Autor`` (nazwisko/imiona z ``dane_znormalizowane``, tytuł z FK
    ``row.tytul`` z analizy), podpina go do wiersza i odtwarza powiązanie
    ``Autor_Jednostka`` (wspólny ``odtworz_autor_jednostka`` — odkłada AJ do
    ``diff_do_utworzenia`` i ustawia ``zmiany_potrzebne=True``). NIE integruje:
    właściwą integrację (materializacja AJ + ``integrate()``) robi główna pętla
    ``zmiany_potrzebne_set`` w ``integruj`` (bez podwójnego przetwarzania). Ślad
    utworzenia autora idzie w ``diff_do_utworzenia['nowy_autor']`` → trafia do
    ``log_zmian['utworzono']`` przez ``_opisz_utworzone``. ``imię`` to klucz
    ``AutorForm`` mapowany na ``Autor.imiona``.

    G4 (dedup multi-etat): ``cache`` to słownik ``{(nazwisko, imiona, tytul_id):
    Autor}`` współdzielony w obrębie JEDNEGO ``integruj``. Dwa wiersze tej samej
    osoby (identyczna trójka) w RÓŻNYCH jednostkach — oba ``utworz_nowego=True``
    — dają JEDEN ``Autor`` i DWA ``Autor_Jednostka`` (multi-etat), zamiast dwóch
    autorów-duplikatów. Pierwszy wiersz trójki tworzy autora (wpis do cache),
    kolejne REUŻYWAJĄ go i wołają ``odtworz_autor_jednostka`` dla swojej
    jednostki (osobne AJ). Marker ``nowy_autor`` (i inkrement licznika w
    ``integruj``) tylko przy realnym create.

    F5: ``EdytujWierszView`` waliduje TYLKO ``nazwisko`` (nie ``imię``), więc
    korekta na samo nazwisko może zejść do ``brak`` z pustym ``imię``. Autora
    bez imienia NIE tworzymy (``AutorForm`` wymaga obu) — wiersz zostaje
    ``autor=None`` i wpada w istniejący licznik ``pominieto_niedopasowane``.

    F4: create autora + ``odtworz_autor_jednostka`` + ``row.save`` w JEDNEJ
    ``transaction.atomic`` (per-wiersz). Bez tego, gdy ``row.save`` padnie, autor
    już istnieje a ``row.autor`` zostaje NULL → restart integracji (stan
    zatwierdzony + RestartView) znów trafi w ``autor__isnull=True`` i utworzy
    DRUGIEGO autora. Atomic cofa też ``Autor.create`` przy rollbacku.

    Zwraca ``True`` TYLKO gdy autor faktycznie POWSTAŁ (→ inkrement licznika).
    ``False`` gdy: (a) puste ``imię`` — pominięto, ``autor=None``; albo (b) autor
    zREUŻYTY z cache — wiersz dostaje ``autor`` i zintegruje się (nowe AJ), ale
    NIE liczy się jako nowy autor.
    """
    dane = row.dane_znormalizowane or {}
    nazwisko = (dane.get("nazwisko") or "").strip()
    imiona = (dane.get("imię") or "").strip()
    if not imiona:
        return False
    klucz = (nazwisko, imiona, row.tytul_id)
    with transaction.atomic():
        autor = cache.get(klucz)
        utworzono = autor is None
        if utworzono:
            autor = Autor.objects.create(
                nazwisko=nazwisko,
                imiona=imiona,
                tytul=row.tytul,
            )
            cache[klucz] = autor
        row.autor = autor
        odtworz_autor_jednostka(row, autor)
        if utworzono:
            row.diff_do_utworzenia["nowy_autor"] = str(autor)
        row.save(
            update_fields=[
                "autor",
                "autor_jednostka",
                "diff_do_utworzenia",
                "zmiany_potrzebne",
            ]
        )
    return utworzono
```

W `integruj`, na POCZĄTKU (przed `qs = parent.zmiany_potrzebne_set.all()`),
dodaj pre-pass i licznik; `qs` ewaluujemy PO pre-pass (nowe wiersze mają już
`zmiany_potrzebne=True`). Licznik rośnie TYLKO dla faktycznie utworzonych
autorów — wiersze pominięte (puste imię) zostają `autor=None`:

```python
def integruj(parent, p):
    utworzono_nowych = 0
    # G4: cache dedupujący nowych autorów po (nazwisko, imiona, tytul_id) w
    # obrębie tego commitu — multi-etat (ta sama osoba, wiele jednostek) daje
    # jednego Autora + wiele Autor_Jednostka.
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

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])
```

W finalnym `p.result({...})` dodaj `"utworzono_nowych_autorow": utworzono_nowych`
(obok kluczy z T5 `odpieto` i istniejących).

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py -v`
Expected: PASS (4).

- [ ] **Step 5: Regresja integracji Faz 0–3**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate.py src/import_pracownikow/tests/test_pipeline/test_integrate_status.py -q`
Expected: PASS (pre-pass i odpięcia nie psują istniejących liczników).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/tests/test_pipeline/test_integrate_nowy_autor.py
git commit -m "feat(import_pracownikow): tworzenie nowego autora w commicie dla brak+utworz_nowego (Faza 4 T8)"
```

---

### Task 9: Podgląd — checkbox „utwórz nowego" (brak) + sekcja odpięć z checkboxami

**Files:**
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
  (checkbox „utwórz nowego" dla wierszy `brak`)
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  (materializowana sekcja odpięć z checkboxami)
- Modify: `src/import_pracownikow/views.py`
  (`ImportPracownikowResultsView.get_context_data` dostaje `odpiecia`)
- Test: `src/import_pracownikow/tests/test_views_faza4_render.py`

**Interfaces:**
- Consumes: `PrzelaczUtworzNowegoView`/`utworz-nowego` (T7),
  `PrzelaczOdpiecieView`/`przelacz-odpiecie` + partial `_odpiecie_row.html` (T4),
  `parent.odpiecia` (T1).
- Produces: podgląd renderuje checkbox „utwórz nowego" (wiersze `brak`) i sekcję
  odpięć (domyślnie odznaczone, HTMX toggle).

- [ ] **Step 1: Napisz failing testy renderu**

Utwórz `src/import_pracownikow/tests/test_views_faza4_render.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)
from import_pracownikow.pewnosc import STATUS_BRAK


def _results_url(imp):
    return reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )


@pytest.mark.django_db
def test_render_checkbox_utworz_nowego_dla_brak(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
    )
    resp = admin_client.get(_results_url(imp))
    tresc = resp.content.decode("utf-8")
    assert 'name="utworz_nowego"' in tresc
    assert "utwórz nowego" in tresc


@pytest.mark.django_db
def test_render_sekcja_odpiec_z_checkboxem(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Odpinalski")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    resp = admin_client.get(_results_url(imp))
    tresc = resp.content.decode("utf-8")
    assert "Odpinalski" in tresc
    assert 'name="zaznaczone"' in tresc
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_faza4_render.py -v`
Expected: FAIL (brak checkboxa `utworz_nowego`; brak sekcji odpięć).

- [ ] **Step 3: Dodaj checkbox „utwórz nowego" do partiala wiersza**

W
`src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`,
WEWNĄTRZ bloku `{% if parent_object.stan == "przeanalizowany" %}`, PO formularzu
korekty (edytuj-wiersz) a PRZED `{% else %}`, dodaj:

```django
            {% if row.confidence == "brak" %}
                {# D2: checkbox „utwórz nowego autora" — zmiana → POST toggle #}
                <form method="post"
                      hx-post="{% url "import_pracownikow:utworz-nowego" pk=parent_object.pk row_pk=row.pk %}"
                      hx-target="#wiersz-{{ row.pk }}"
                      hx-swap="outerHTML"
                      hx-trigger="change">
                    {% csrf_token %}
                    <label>
                        <input type="checkbox" name="utworz_nowego"
                               {% if row.utworz_nowego %}checked{% endif %}>
                        <i class="fi-plus"></i> utwórz nowego autora
                    </label>
                </form>
            {% endif %}
```

- [ ] **Step 4: Dodaj kontekst `odpiecia` do widoku wyników**

W `src/import_pracownikow/views.py`, w `ImportPracownikowResultsView`, zastąp
`get_context_data` (z T6) wersją dokładającą materializowane odpięcia:

```python
    def get_context_data(self, **kwargs):
        odpiecia = self.parent_object.odpiecia.select_related(
            "autor_jednostka__autor",
            "autor_jednostka__autor__tytul",
            "autor_jednostka__jednostka",
        )
        return super().get_context_data(
            parent_object=self.parent_object,
            odpiecia=odpiecia,
            **kwargs,
        )
```

- [ ] **Step 5: Dodaj materializowaną sekcję odpięć do szablonu listy**

W
`src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`,
w miejscu usuniętej starej sekcji (T6), PRZED końcowym `{% endblock %}`, dodaj:

```django
    {% if odpiecia %}
        <h4>Powiązania autor+jednostka spoza tego pliku (odpięcia)</h4>
        {# Domyślnie ODZNACZONE (§9 D3); zaznacz, by odpiąć przy zapisie. #}
        {# Wykonanie następuje dopiero w fazie zapisu do bazy. #}
        <table>
            <thead>
                <tr>
                    <th>Autor</th>
                    <th>Jednostka</th>
                    <th>Odepnij?</th>
                </tr>
            </thead>
            <tbody>
                {% for odp in odpiecia %}
                    {% include "import_pracownikow/partials/_odpiecie_row.html" %}
                {% endfor %}
            </tbody>
        </table>
    {% endif %}
```

- [ ] **Step 6: Uruchom — zielone (+ regresja renderu Faz 0–3)**

Run: `uv run pytest src/import_pracownikow/tests/test_views_faza4_render.py src/import_pracownikow/tests/test_views_preview_render.py src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: PASS (nowe checkboxy/sekcja + istniejący render podglądu i audytu
„Lista modyfikacji" nietknięte).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html \
  src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html \
  src/import_pracownikow/views.py \
  src/import_pracownikow/tests/test_views_faza4_render.py
git commit -m "feat(import_pracownikow): podgląd — checkbox utwórz nowego + sekcja odpięć (Faza 4 T9)"
```

---

### Task 10: E2E + newsfragment

Pełny przepływ Fazy 4 przez ekran: upload (autor `brak` + autor-spoza-pliku) →
mapowanie → analiza (eager) → zaznacz „utwórz nowego" + zaznacz odpięcie →
zatwierdź → integracja (eager) → nowy Autor + AJ powstają, zatrudnienie odpiętego
zakończone.

**Files:**
- Create: `src/import_pracownikow/tests/test_pipeline/test_faza4_e2e.py`
- Create: `src/bpp/newsfragments/import-pracownikow-nowy-autor-odpiecia.feature.rst`

**Interfaces:**
- Consumes: cały przepływ Fazy 4 (mapowanie osoba_sklejona → analiza → toggle
  utworz_nowego/odpiecie → integracja).

- [ ] **Step 1: Napisz test e2e**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_faza4_e2e.py`:

```python
"""E2E Fazy 4: nowy autor (brak) + odpięcie autora spoza pliku.
LIVEOPS.RUNNER='eager' (settings/test.py) → enqueue() wykonuje run()
synchronicznie w ramach POST-a."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import STATUS_BRAK


@pytest.mark.django_db
def test_e2e_nowy_autor_i_odpiecie(admin_client, admin_user, yesterday):
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")

    # autor spoza pliku: jednostka zarządzana automatycznie + aktualna jednostka
    j_spoza = baker.make(
        Jednostka, nazwa="Katedra Spoza", skrot="Kat. Spoza",
        zarzadzaj_automatycznie=True,
    )
    a_spoza = baker.make(Autor, nazwisko="Odpinalski", imiona="Marek")
    a_spoza.dodaj_jednostke(j_spoza)
    aj_spoza = a_spoza.autor_jednostka_set.get(jednostka=j_spoza)

    csv = (
        "Osoba;Nazwa jednostki\n"
        f"Grzegorz Nowakowski;{jednostka.nazwa}\n"
    ).encode("utf-8")
    imp = ImportPracownikow(
        owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    # mapowanie: Osoba → osoba_sklejona; analiza rusza eager w POST-cie
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url_map,
        {
            "kol__osoba": "osoba_sklejona",
            "kol__nazwa_jednostki": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY

    row = imp.importpracownikowrow_set.get()
    assert row.confidence == STATUS_BRAK
    assert row.autor is None

    odp = imp.odpiecia.get(autor_jednostka=aj_spoza)
    assert odp.zaznaczone is False

    # user zaznacza „utwórz nowego" dla wiersza brak
    url_un = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    assert admin_client.post(url_un, {"utworz_nowego": "on"}).status_code == 200

    # user zaznacza odpięcie
    url_odp = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    assert admin_client.post(url_odp, {"zaznaczone": "on"}).status_code == 200

    # zatwierdź → integracja (eager)
    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    resp = admin_client.post(url_zatw)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # nowy autor + jego AJ powstały
    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.nazwisko == "Nowakowski"
    assert Autor_Jednostka.objects.filter(
        autor=row.autor, jednostka=jednostka
    ).exists()

    # zatrudnienie odpiętego zakończone (wczoraj) + odpięcie wykonane
    aj_spoza.refresh_from_db()
    odp.refresh_from_db()
    assert aj_spoza.zakonczyl_prace == yesterday
    assert aj_spoza.podstawowe_miejsce_pracy is False
    assert odp.wykonane is True
```

- [ ] **Step 2: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_faza4_e2e.py -v`
Expected: PASS. (Jeśli pierwszy przebieg CSV-źródła jest wolny — ponów.)

- [ ] **Step 3: Newsfragment**

Utwórz `src/bpp/newsfragments/import-pracownikow-nowy-autor-odpiecia.feature.rst`:

```rst
Import pracowników potrafi teraz w podglądzie utworzyć nowego autora dla wierszy
bez dopasowania (checkbox „utwórz nowego autora" — tworzenie następuje dopiero
przy zapisie do bazy). Odpięcia autorów spoza pliku pokazywane są jako lista
per-autor z checkboxami (domyślnie odznaczone); zakończenie zatrudnienia
wykonuje się tylko dla zaznaczonych, dopiero w fazie zapisu, ze świeżą weryfikacją
stanu bazy.
```

- [ ] **Step 4: Pełna regresja Faz 0–4**

Run: `uv run pytest src/import_pracownikow/ src/import_common/ -q`
Expected: PASS wszystko. Podaj liczbę passed/failed.

- [ ] **Step 5: Ruff + linie ≤88 + pinned format**

Run: `uv run ruff check src/import_pracownikow/`
oraz `awk 'length>88{print FILENAME":"NR}' src/import_pracownikow/models.py src/import_pracownikow/views.py src/import_pracownikow/pipeline/analyze.py src/import_pracownikow/pipeline/integrate.py`
oraz `uv run pre-commit run ruff-format --files $(git diff --name-only $(git merge-base dev HEAD) | tr '\n' ' ')`
Expected: ruff czysty; brak wyjścia z `awk`; format czysty (dołącz zmiany
formatera do commita).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_faza4_e2e.py \
  src/bpp/newsfragments/import-pracownikow-nowy-autor-odpiecia.feature.rst
git commit -m "test(import_pracownikow): e2e Fazy 4 + newsfragment (Faza 4 T10)"
```

---

## Nota o baseline (przy MERGE, nie na tym branchu)

Migracja `0014_utworz_nowego_odpiecie` zmienia schemat (`ImportPracownikowRow` +
nowy model `ImportPracownikowOdpiecie`). Odświeżenie baseline
(`make baseline-update`) robimy **dopiero przy scalaniu** gałęzi do `dev` — NIE na
feature-branchu (reguła CLAUDE.md: równoległe branch'e nie mogą kolidować na
jednym pliku `baseline.sql`). Commituj wtedy oba:
`baseline-sql/baseline.sql` + `baseline-sql/baseline.meta.json`.

---

## Self-Review (autor planu)

**Spec coverage §9 (odpięcia D3):**
- Przepisanie zapytania na pary `(autor_id, jednostka_id)` + odfiltrowanie NULL,
  zachowane kryteria wykluczeń → T2 (test regresji NULL + 4 kryteria) ✅
- Nowy model `ImportPracownikowOdpiecie(parent, autor_jednostka, zaznaczone,
  wykonane)` z Meta/ordering → T1 ✅
- Materializacja w analizie PO pętli, idempotentna, `on_restart` kasuje, licznik
  w wyniku → T3 ✅
- Preview: sekcja z checkboxami per-autor, domyślnie ODZNACZONE → T9 (render) +
  T4 (partial) ✅
- Widok toggle `zaznaczone` (HTMX, owner-scoped, bramka `przeanalizowany`,
  URL `<uuid:pk>/odpiecie/<int:odp_pk>/przelacz/`) → T4 ✅
- Commit iteruje `zaznaczone=True`, świeży re-check (pomija zakończone ręcznie),
  kończy zatrudnienie (`zakonczyl_prace=wczoraj`, `podstawowe_miejsce_pracy=
  False`), `wykonane=True`, licznik → T5 ✅
- Los starego `odepnij`/ResetujView/url (decyzja A wariant „a": usuń) + testy +
  link w templatce → T6 ✅

**Spec coverage D2 („utwórz nowego"):**
- Pole `utworz_nowego = BooleanField(default=False)` (migracja Faza 4) → T1 ✅
- UI checkbox dla `confidence==brak`, widok toggle (HTMX, owner-scoped, bramka
  `przeanalizowany`, współdzieli `_WierszImportuMixin`, URL
  `<uuid:pk>/wiersz/<int:row_pk>/utworz-nowego/`) → T7 (widok) + T9 (checkbox) ✅
- Integracja: `brak` + `utworz_nowego=True` → utwórz `bpp.Autor`
  (nazwisko/imiona z `dane_znormalizowane`, tytuł z `row.tytul`), `row.autor`,
  `odtworz_autor_jednostka`, `_materializuj_diff` + `row.integrate()`; tworzenie
  w commicie, NIE w analizie → T8 ✅
- `brak` + `utworz_nowego=False` → NADAL pomijany → T8
  (`test_commit_pomija_brak_bez_utworz_nowego`) ✅
- `brak` + `utworz_nowego=True` ale puste `imię` (korekta samego nazwiska) →
  autor NIE powstaje, wiersz → `pominieto_niedopasowane` → T8
  (`test_commit_nie_tworzy_autora_z_pustym_imieniem`, F5); tworzenie owinięte w
  `transaction.atomic` (F4) ✅
- Licznik „utworzono nowych autorów" + ślad `log_zmian["utworzono"]` → T8 ✅
- Granica: przepięcie prac (§10) = Faza 5, NIE implementowane → sekcja „Poza
  zakresem" ✅

**Placeholder scan:** brak TBD/TODO/„similar to Task N"/kroków bez kodu. Każdy
krok ma pełny test + implementację. Wszystkie typy/funkcje/URL-e nazwane i
zdefiniowane w konkretnym tasku.

**Type/signature consistency:**
- `ImportPracownikowOdpiecie(parent, autor_jednostka, zaznaczone, wykonane)` +
  `related_name="odpiecia"` — T1 definiuje; T3/T5 (`parent.odpiecia`), T4
  (`get_object_or_404`), T9 (kontekst) czytają spójnie. ✅
- `autorzy_spoza_pliku_set(uczelnia=None, today=None)` — sygnatura BEZ zmian
  (T2 tylko ciało); T3 woła z `uczelnia=...`. ✅
- `_materializuj_odpiecia(parent) -> int` (T3), `_wykonaj_odpiecia(parent) ->
  int` (T5, re-check: skip pary z pliku — G1 — oraz AJ zakończonego ręcznie),
  `_przygotuj_nowego_autora(row, cache) -> bool` (T8, `transaction.atomic` +
  skip pustego imienia — F4/F5 — + dedup po `(nazwisko, imiona, tytul_id)` —
  G4) — nazwy/sygnatury spójne, nie kolidują. ✅
- `odtworz_autor_jednostka(row, autor)` — re-użyte z Fazy 3 w T8 (jak w
  `WybierzKandydataView`); wymaga `row.autor = autor` przed wywołaniem —
  spełnione. ✅
- Klucze wyniku: analiza `p.result` +`"odpiecia"` (T3); integracja `p.result`
  +`"odpieto"` (T5) +`"utworzono_nowych_autorow"` (T8) — dodawane, nie zmieniają
  istniejących (`zintegrowano`/`pominieto_*`/`wymaga_uwagi`/`stan`). ✅
- URL names `przelacz-odpiecie` (T4), `utworz-nowego` (T7) + partiale
  `_odpiecie_row.html` (T4) / checkbox w `_wiersz_preview.html` (T9) — spójne
  T4/T7/T9/T10. ✅
- `STATUS_BRAK`/`STATUS_WIELU` z `pewnosc.py` — import w integrate (T5/T8),
  views (T7), spójny z Fazą 3. ✅

**Backward compat:** `utworz_nowego` default False; model odpięcia nowy (brak
wpływu na stare rekordy). Materializacja odpięć nie zmienia pętli wierszy analizy
(T3 Step 6 regresja). Pre-pass i odpięcia w integracji nie ruszają istniejących
liczników `zintegrowano`/`pominieto_*` (T8 Step 5 regresja). Usunięcie stopgap
(T6) wymienia obsolete testy; `test_views_liveops.py` (audyt „Lista modyfikacji")
zachowany. Jedna nowa migracja `0014`; baseline przy merge.
