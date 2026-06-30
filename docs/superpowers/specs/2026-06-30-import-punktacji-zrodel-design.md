# Import punktacji źródeł z pliku JCR (Journal Citation Reports) — projekt

- **Zgłoszenie:** Freshdesk FD#388 (Biblioteka Naukowa IHiT)
- **Gałąź / worktree:** `fix-fd388-import-punktacji-zrodel`
- **Data:** 2026-06-30
- **Nowa aplikacja:** `src/import_punktacji_zrodel/`

> Uwaga nazewnicza: nazwy handlowe ("JCR", "Web of Science", "impact
> factor") **nie pojawiają się w etykietach UI**. W dokumencie technicznym
> używamy ich dla precyzji (to faktyczny format pliku Clarivate). W UI:
> „import punktacji źródeł", „wskaźnik IF" / „punktacja", „kwartyl".

## 1. Cel

Bibliotekarz wgrywa plik eksportu z Clarivate (Journal Citation Reports) —
`.xlsx` **lub** `.csv` — a system:

1. parsuje plik (wartość IF za dany rok + kwartyl per kategoria),
2. dopasowuje czasopisma do `Zrodlo` (po ISSN / e-ISSN / tytule),
3. pokazuje **raport podglądu**: które źródła są bez zmian, które wymagają
   aktualizacji (IF i/lub kwartyl), których nie dopasowano,
4. po **potwierdzeniu** zapisuje wartości do `Punktacja_Zrodla(zrodlo, rok)`:
   `impact_factor` oraz `kwartyl_w_wos`,
5. linkuje do istniejącego modułu **rozbieżności punktacji** (`if`,
   `kw_wos`), żeby — opcjonalnie — przenieść wartości na prace (publikacje).

Poziom **prac/publikacji** (porównanie i bulk-set) realizuje już istniejąca
aplikacja `rozbieznosci`. Nowa aplikacja świadomie **nie duplikuje** tej
logiki — kończy na poziomie źródła i odsyła do `rozbieznosci`.

## 2. Format pliku wejściowego (potwierdzony na załączniku z FD#388)

Eksport JCR „Journal Results". Układ:

- **wiersz 0** — metadane filtra, zawiera m.in. `Selected JCR Year: 2025`,
- **wiersz 1** — pusty,
- **wiersz 2** — nagłówek kolumn:
  `Journal name, JCR Abbreviation, Publisher, ISSN, eISSN, Category,
  Edition, Total Citations, <ROK> JIF, JIF Quartile, <ROK> JCI,
  % of Citable OA`,
- **wiersze 3..N** — dane,
- **stopka** — `Copyright (c) <ROK> Clarivate`, `By exporting the selected
  data; ...` (do **pominięcia**).

Charakterystyka danych (z analizy załącznika: 209 wierszy danych, **136**
unikalnych czasopism — klucz `(issn, e_issn, nazwa)`; z czego 135 ma co
najmniej jedną importowalną wartość, a `eLife` ma same `N/A`):

- **Jedno czasopismo = wiele wierszy** — po jednym na kategorię WoS
  (np. `CANCER CELL` w `CELL BIOLOGY` i `ONCOLOGY`).
- `<ROK> JIF` — wartość IF, ta sama we wszystkich wierszach danego
  czasopisma (np. `109.0`, `84.5`). Może być `N/A`.
- `JIF Quartile` — `Q1..Q4`, **per kategoria**: to samo czasopismo bywa
  Q1 w jednej kategorii i Q2 w innej (częste w pliku). Może być `N/A`.
- `ISSN` może być `N/A` (31 wierszy w załączniku) — wtedy dopasowanie po
  `eISSN`. `eISSN` też bywa `N/A`.
- Niektóre czasopisma mają `N/A` we wszystkim (np. `eLife`) — **parsowane**
  (nie gubimy ich na etapie parsera; jest 136 grup), ale w raporcie
  oznaczane „brak danych (N/A) w pliku" i **nie zapisywane**.

### Kolumny, które importujemy

| Kolumna pliku | Pole BPP | Uwaga |
|---|---|---|
| `Journal name` | (dopasowanie) `Zrodlo.nazwa` | tytuł |
| `ISSN` | (dopasowanie) `Zrodlo.issn` | `N/A` → `None` |
| `eISSN` | (dopasowanie) `Zrodlo.e_issn` | `N/A` → `None` |
| `<ROK> JIF` | `Punktacja_Zrodla.impact_factor` | `Decimal`; `N/A`→nie zapisujemy IF (pole NIE jest nullable, default `0.000`) |
| `JIF Quartile` | `Punktacja_Zrodla.kwartyl_w_wos` | `Q1..Q4`→`1..4` |
| (nagłówek `<ROK> JIF` / metadane) | `Punktacja_Zrodla.rok` | autodetekcja |

Pozostałe kolumny (Publisher, JCI, OA, cytowania) — ignorowane.

## 3. Parser (nowy element — `parser.py`)

Funkcja `wczytaj_plik_jcr(path) -> ParsedJCR`, gdzie `ParsedJCR` zawiera:

- `rok: int | None` — wykryty rok,
- `czasopisma: list[CzasopismoJCR]` — pogrupowane czasopisma.

`CzasopismoJCR` (dataclass): `nazwa, issn, e_issn, impact_factor (Decimal |
None), kwartyl_wos (int | None), kategorie (list[(kategoria, kwartyl)])`.

Logika:

1. **Wybór czytnika po rozszerzeniu:** `.xlsx`/`.xls` → `openpyxl`
   (read_only, data_only); `.csv` → moduł `csv` (`csv.reader`, separator
   `,`, cudzysłów `"`, kodowanie `utf-8`/`utf-8-sig` — plik bez BOM).
   **Bez special-case'owania** śmieciowego `"%,` na końcu wierszy:
   zweryfikowano, że `csv.reader` parsuje wiersz danych na 13 pól (kolumna
   OA → `'25.49%'` + puste pole na końcu), ale **kolumny 0–10 pozostają
   wyrównane** (ISSN=idx3, eISSN=idx4, `<ROK> JIF`=idx8, `JIF
   Quartile`=idx9; `"378,842"` z przecinkiem jest w cudzysłowie, więc OK).
   Zamiast indeksów na sztywno: zbuduj mapę **nagłówek→indeks** i czytaj
   kolumny po nazwie.
2. **Znalezienie nagłówka:** pierwszy wiersz zawierający `Journal name`
   oraz `JIF Quartile` (odporne na wiersz metadanych i pusty).
3. **Wykrycie roku:** regex `^\s*(\d{4})\s+JIF$` z nagłówka kolumny IF;
   fallback: `Selected JCR Year:\s*(\d{4})` z wiersza metadanych.
4. **Pominięcie stopki:** wiersze bez sensownej `Journal name` lub
   zawierające `Clarivate` / `Terms of Use`.
5. **Normalizacja wartości:**
   - ISSN/eISSN: `strip`; `N/A`/`""` → `None`,
   - IF: `N/A`/`""` → `None`; inaczej `Decimal(str(v))`
     (np. `"109.0"`→`109.000`, w granicach `max_digits=6, decimal=3`),
   - kwartyl: `Q1..Q4` → `1..4`; `N/A`/`""` → `None`.
6. **Grupowanie po czasopiśmie** — klucz = `(issn, e_issn, nazwa)`
   (po normalizacji). Scalanie:
   - `impact_factor` — wartość z wierszy (spójna; gdyby różna, bierzemy
     pierwszą niepustą i odnotowujemy),
   - `kwartyl_wos` — **najlepszy** kwartyl = `min(kwartyle)` (Q1 wygrywa),
     zgodnie z decyzją; `kategorie` zachowujemy do raportu/diagnostyki.

Parser jest **czysty** (bez Django ORM) → łatwy do testów jednostkowych na
realnym pliku z FD#388.

## 4. Model danych (`models.py`) — wymaga NOWEJ migracji

Wzorzec: `import_list_ministerialnych` (`long_running.Operation` + dry-run +
wiersze wyników). **Nie ruszamy baseline** (decyzja użytkownika:
`make baseline-update` / rebuild **NIE** wykonujemy w tej gałęzi).

```python
class ImportPunktacjiZrodel(ASGINotificationMixin, Operation):
    rok = YearField(null=True, blank=True)        # autodetekcja z pliku
    plik = models.FileField(upload_to="protected/import_punktacji_zrodel/")
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)   # dry-run gdy False
    importuj_impact_factor = models.BooleanField(default=True)
    importuj_kwartyl_wos = models.BooleanField(default=True)
    ignoruj_zrodla_bez_odpowiednika = models.BooleanField(default=False)
    nie_porownuj_po_tytulach = models.BooleanField(default=False)

    # NIE ustawiamy redirect_prefix — Operation.get_url() używa domyślnego
    # "{app_label}:{model_name_lowercased}", więc nazwy URL muszą być
    # "importpunktacjizrodel-router/-details/-results" (patrz §6).

    def perform(self): ...        # → core.analyze_jcr_file(self.plik.path, self)
    def on_reset(self): self.get_details_set().delete()
    def get_details_set(self): return self.wierszimportupunktacjizrodel_set.all()

class WierszImportuPunktacjiZrodel(models.Model):
    parent = FK(ImportPunktacjiZrodel, CASCADE)
    dane_z_xls = JSONField()        # zgrupowany dict czasopisma
    nr_wiersza = PositiveIntegerField()
    zrodlo = FK(Zrodlo, SET_NULL, null=True, blank=True)
    rezultat = TextField(blank=True, default="")
    wymaga_zmian = BooleanField(default=False)   # do filtra „tylko do aktualizacji"
    is_duplicate = BooleanField(default=False)
    duplicate_of_row = PositiveIntegerField(null=True, blank=True)
    duplicate_reason = CharField(max_length=100, blank=True)
```

## 5. Logika importu (`core.py`)

`analyze_jcr_file(path, parent)`:

1. `parsed = wczytaj_plik_jcr(path)`.
2. **Rok efektywny:** `parent.rok or parsed.rok`. Jeśli oba podane i różne →
   wiersz-ostrzeżenie w raporcie; używamy `parent.rok` (decyzja człowieka).
   Jeśli `parent.rok` puste — zapisujemy wykryty (`parent.rok = parsed.rok;
   parent.save(update_fields=["rok"])`). Brak roku w ogóle → błąd
   (wiersz `rezultat` + `send_notification(msg, level=constants.ERROR)`;
   `constants` z `django.contrib.messages`). Sygnatura mixina:
   `send_notification(self, msg, level=constants.INFO)`,
   `send_progress(self, percent)`. `YearField` (= IntegerField) **nie jest
   nullowalny w `get_or_create`** — dlatego rok efektywny musi być ustalony
   przed pętlą zapisu.
3. `dry_run = not parent.zapisz_zmiany_do_bazy`.
4. **Wykrycie duplikatów** w pliku (ten sam ISSN/eISSN w 2 grupach) — flaga.
5. Dla każdego czasopisma (`send_progress`):
   - `zrodlo = matchuj_zrodlo(nazwa, issn=issn, e_issn=e_issn,
     disable_fuzzy=True, disable_skrot=True,
     disable_title_matching=parent.nie_porownuj_po_tytulach)`,
   - brak źródła → `rezultat="Brak źródła w BPP"`, `wymaga_zmian=False`
     (chyba że `ignoruj_zrodla_bez_odpowiednika=False` — i tak tylko
     raportujemy, nigdy nie tworzymy `Zrodlo`),
   - jest źródło → `pz, _ = Punktacja_Zrodla.objects.get_or_create(
     zrodlo=zrodlo, rok=rok)`; porównaj i (jeśli nie dry-run) ustaw:
     - **IF** (gdy `importuj_impact_factor` i wartość niepusta):
       `pz.impact_factor != if_z_pliku` → `"IF: {stare} → {nowe}"`,
       inaczej `"IF bez zmian"`,
     - **kwartyl** (gdy `importuj_kwartyl_wos` i wartość niepusta):
       `pz.kwartyl_w_wos != q` → `"Kwartyl: {Qstare} → {Qnowe}"`,
       inaczej `"Kwartyl bez zmian"`,
     - `wymaga_zmian = (którekolwiek pole się różni)`,
     - zapis tylko gdy `not dry_run`: `pz.save(update_fields=[...])`
       (tylko realnie zmienione pola),
   - utwórz `WierszImportuPunktacjiZrodel(...)` z `rezultat`, `wymaga_zmian`,
     flagami duplikatu.

Cała operacja idzie w `transaction.atomic` (zapewnia `task_perform`).

### „Bez zmian" vs „do aktualizacji" (semantyka z FD#388)

- **bez zmian** — `Punktacja_Zrodla` za rok ma już te same IF i kwartyl
  → „dobra punktacja, nic nie trzeba",
- **do aktualizacji** — różnica wartości lub brak wpisu → pokazane
  `stare → nowe`; po commicie zapisane.

> Uwaga: `Punktacja_Zrodla.impact_factor` **nie jest nullowalny** (default
> `Decimal("0.000")`). Świeżo `get_or_create`'owany rekord ma więc IF
> `0.000`, co poprawnie raportujemy jako `0.000 → X` („do aktualizacji").
> Wartość `N/A` w pliku oznacza **pominięcie zapisu IF** (nie ustawiamy
> `0.000` na siłę). Kwartyl JEST nullowalny (`None` = „brak").

## 6. Widoki, URL-e, formularz (wzór: `import_list_ministerialnych`)

- `views.py` — klasy oparte o `long_running.views`:
  `ListaImportowView` (LongRunningOperationsView), `NowyImportView`
  (CreateLongRunningOperationView, `form_class=NowyImportForm`),
  `RouterView`, `DetailsView`, `ResultsView` (z filtrowaniem:
  `tylko_do_aktualizacji`, `tylko_niedopasowane`, `tylko_duplikaty`,
  `search_query`), `RestartImportView`, oraz **`ZatwierdzImportView`**
  (patrz §7). Wszystkie: `GroupRequiredMixin`, grupa `"wprowadzanie
  danych"`.
- `urls.py` — `app_name="import_punktacji_zrodel"`. **Nazwy URL muszą
  zgadzać się z kontraktem `long_running`** (`Operation.get_url` reversuje
  `import_punktacji_zrodel:importpunktacjizrodel-<suffix>`):
  - `""` → `index`
  - `"new/"` → `new`
  - `"<uuid:pk>/"` → `importpunktacjizrodel-router`
  - `"<uuid:pk>/detale/"` → `importpunktacjizrodel-details`
  - `"<uuid:pk>/rezultaty/"` → `importpunktacjizrodel-results`
  - `"<uuid:pk>/regen/"` → `restart`
  - `"<uuid:pk>/zatwierdz/"` → `zatwierdz`
  (suffiksy `router`/`details`/`results` są wymuszone przez
  `STATE_TO_SUFFIX_MAP` + `get_absolute_url`; reszta dowolna.)
- `forms.py` — `NowyImportForm(ModelForm)`, crispy+foundation; pola: `plik`,
  `rok` (**niewymagane** — autodetekcja), checkboxy IF/kwartyl/ignoruj/
  nie_porównuj/zapisz. `clean_plik`: dozwolone rozszerzenia
  `.xlsx, .xls, .csv`. (Dodanie `.csv` do `valid_extensions` **wystarcza** —
  w siblingu blok MIME nigdy nie odrzuca samodzielnie; CSV bywa raportowany
  jako `text/csv`/`application/vnd.ms-excel`/`application/octet-stream`.)
- `templates/import_punktacji_zrodel/` — analogiczne do siblinga
  (`*_form.html`, `*_list.html`, `*_detail.html`,
  `wierszimportupunktacjizrodel_list.html`), `{% extends "base.html" %}`,
  Foundation CSS, fi-icons.

## 7. Przepływ „podgląd → potwierdzenie"

1. Formularz domyślnie tworzy import z `zapisz_zmiany_do_bazy=False`
   (dry-run). Po przetworzeniu strona wyników pokazuje, **co by się
   zmieniło** (panel statystyk: bez zmian / do aktualizacji / niedopasowane
   / duplikaty + tabela z filtrami).
2. Gdy import był dry-run, strona wyników pokazuje przycisk **„Zatwierdź i
   zapisz do bazy"** → `ZatwierdzImportView` (POST): ustawia
   `zapisz_zmiany_do_bazy=True`, `mark_reset()` i ponownie uruchamia zadanie
   (jak restart). Plik jest już zapisany w `self.plik` — **bez ponownego
   uploadu**; parser czyta deterministycznie ten sam plik i tym razem
   zapisuje.
3. Po zapisie panel **„Przenieś wartości na prace"** z linkami. `metryka`
   to **slug w ścieżce**, a rok filtruje się **zakresem** `rok_od`/`rok_do`
   (nie ma pojedynczego `rok`); pinujemy oba końce na zaimportowany rok:
   - `reverse("rozbieznosci:index", kwargs={"metryka": "if"}) +
     f"?rok_od={rok}&rok_do={rok}"`,
   - analogicznie `metryka="kw_wos"`.
   To realizuje opcjonalne „ustaw IF/kwartyl dla publikacji po imporcie"
   przez istniejący mechanizm bulk-set w `rozbieznosci`.

## 8. Integracja z projektem

- `INSTALLED_APPS` w `src/django_bpp/settings/base.py` — **jedna** lista
  (`INSTALLED_APPS = [` ~L356, koniec ~L497); dopisać
  `"import_punktacji_zrodel"` obok pozostałych `import_*`
  (`import_list_if` ~L387, `import_list_ministerialnych` ~L477). **Nie ma**
  drugiej listy appów ~L959 (to był błąd w pierwotnym specu).
- `pyproject.toml` — to **`[tool.setuptools.packages.find].include`**
  (~L179–206, lista do budowy wheela/sdist, **nie** Django `INSTALLED_APPS`)
  — dopisać `"import_punktacji_zrodel"` obok innych `import_*`.
- `src/django_bpp/urls.py` — `path("import_punktacji_zrodel/",
  include("import_punktacji_zrodel.urls"))` (obok pozostałych importów).
- **Menu** `src/django_bpp/templates/top_bar.html` — **prawa kolumna**
  (`menu vertical column-2`): po wpisie „deduplikator źródeł" dodać `<hr>`
  (separator), przenieść tam istniejący wpis **„eksport ISSNów"**
  (`bpp:xlsx-issn-chunks`) z lewej kolumny, a pod nim dodać nowy wpis
  **„import punktacji źródeł"** (`import_punktacji_zrodel:index`, fi-icon
  np. `fi-graph-bar`). Po przeniesieniu „eksport ISSNów" usunąć osierocony
  `<hr/>` po lewej. (Etykieta „import punktacji źródeł" — bez nazw
  handlowych; do potwierdzenia w review.)
- **Uprawnienia:** grupa `"wprowadzanie danych"` (jak siblingi).
- **Migracja:** `0001_initial` nowej aplikacji (czysto addytywna, 2 modele,
  zero zmian istniejących tabel). **Baseline NIE jest aktualizowany.**
- **Newsfragment (towncrier):** `src/bpp/newsfragments/+fd388.feature.rst`
  — typ `feature`, rozszerzenie **`.rst`** (fragmenty `.md` NIE są zbierane
  do `HISTORY.md`), prefiks `+` (orphan — brak martwego linku do GH).

## 9. Testy (TDD — pytest, baker)

`src/import_punktacji_zrodel/tests/`:

- **Parser (jednostkowe, bez DB)** na realnym pliku z FD#388 (kopia w
  `tests/testdata/`): wykrycie roku (2025), pominięcie stopki Clarivate,
  `N/A` w ISSN/IF/kwartylu, scalenie wielokategoryjne → **najlepszy**
  kwartyl (np. ISSN `0268-3369`, BONE MARROW TRANSPLANTATION: wiersze
  `Q1,Q2,Q1,Q1` → `min = 1`), poprawny `Decimal` IF,
  **liczność = 136 czasopism** (`eLife` obecny, z `impact_factor=None` i
  `kwartyl=None`), wsparcie **CSV i XLSX** (ten sam wynik).
- **Dopasowanie + zapis (DB)**: `baker.make(Zrodlo, issn=...)`,
  `perform()`:
  - dry-run **nic nie zapisuje** (`Punktacja_Zrodla` bez zmian),
  - commit zapisuje `impact_factor` + `kwartyl_w_wos` za właściwy rok,
  - „bez zmian" gdy wartości równe; „do aktualizacji" gdy różne/brak,
  - niedopasowane źródło → wiersz `rezultat="Brak źródła w BPP"`,
  - toggle `importuj_kwartyl_wos=False` → kwartyl nietknięty.
- **Repro/akceptacyjny FD#388**: pełny przebieg pliku → raport ma niezerowe
  liczby w każdej kategorii; po zatwierdzeniu wybrane źródła mają wartości.

Plik testowy: `tests/test_repro_fd388.py` (+ `test_parser.py`,
`test_import.py`).

## 10. Świadomie poza zakresem (YAGNI / granice)

- Brak własnego porównania i bulk-set na **pracach** — to robi `rozbieznosci`
  (`if`, `kw_wos`); tylko linkujemy.
- Nie tworzymy nowych `Zrodlo` (tylko raport „brak źródła").
- Nie importujemy JCI, OA, cytowań, wydawcy.
- Nie ruszamy istniejącego `import_list_if` (zostaje; nasz app to odrębny
  format JCR + kwartyl + ISSN-matching + podgląd).
- Nie aktualizujemy `baseline-sql/` (decyzja użytkownika).

## 11. Otwarte drobiazgi do potwierdzenia w review

1. Etykieta menu: „import punktacji źródeł" (bez „IF"/„JCR"/„WoS") — OK?
2. Przeniesienie „eksport ISSNów" do prawej kolumny pod nowy separator —
   zgodnie z instrukcją; potwierdzić układ.
3. Domyślne wartości toggli: IF=wł., kwartyl=wł., ignoruj_bez_źródła=wył.
   (pokazuj niedopasowane), nie_porównuj_po_tytułach=wył. (dopasowuj też po
   tytule, gdy brak ISSN).

## 12a. Ryzyka do wczesnej weryfikacji w implementacji

- **Format ISSN przy dopasowaniu.** `matchuj_zrodlo` robi **dokładne**
  `Zrodlo.objects.get(issn=...)` (bez normalizacji w tej ścieżce). Plik JCR
  trzyma ISSN z myślnikiem (`0140-6736`). Dopasowanie po ISSN zadziała
  **tylko** jeśli `Zrodlo.issn` też jest z myślnikiem. Wczesny krok
  implementacji: sprawdzić na realnych danych (na DB devowej z `run-site`
  albo w teście z `baker.make(Zrodlo, issn="0140-6736")`), czy format się
  zgadza. Jeśli nie — znormalizować ISSN po obu stronach przed lookupem
  (jest `normalize_issn` w `import_common`). MVP: przekazujemy ISSN jak w
  pliku (z myślnikiem); gdy match słaby — fallback po tytule i tak działa.
- `eLife` (same `N/A`) musi przejść przez parser jako 1 z 136 grup — test
  na to patrzy (regresja, gdyby ktoś „zoptymalizował" parser by je gubić).
