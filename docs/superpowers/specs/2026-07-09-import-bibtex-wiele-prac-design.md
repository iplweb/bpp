# Import wielu prac naraz z BibTeX-a (`MultipleWorksImport`)

**Data:** 2026-07-09
**Branch:** `feat-bibtex-import-wiele-prac` (worktree, off `dev`)
**Moduł:** `src/importer_publikacji/`

## 1. Problem

Provider BibTeX w importerze publikacji przyjmuje wklejony tekst, ale gdy
zawiera on wiele wpisów (`@article{...}`, `@book{...}`, …), **po cichu
importuje tylko pierwszy i wyrzuca resztę**.

Potwierdzone w kodzie:

- `providers/bibtex.py:96` — `entry = library.entries[0]`; wpisy 2..N są
  sparsowane przez `bibtexparser` i porzucone. Bez ostrzeżenia, bez logu,
  bez śladu w `raw_data`/`normalized_data`.
- Jedyna informacja to statyczny `input_help_text`
  (`providers/bibtex.py:60-66`): *„Jeśli podasz wiele wpisów, zostanie użyty
  pierwszy."*
- `tests/test_bibtex_provider.py` — `test_fetch_multiple_entries_takes_first`
  wprost blokuje to zachowanie.
- Model `ImportSession` (`models.py:15-270`) jest **1 sesja = 1 docelowa
  publikacja**; brak jakiegokolwiek pojęcia „paczki"/„pliku" w schemacie.
- Kontrakt `DataProvider.fetch(identifier) -> FetchedPublication | None`
  (`providers/__init__.py`) jest z założenia **jedno-rekordowy** — pozostałe
  providery (CrossRef/DOI, PBN, DSpace, WWW) są naturalnie jedno-rekordowe.
  BibTeX to jedyny format, którego *surowy input* jest pojemnikiem na N
  rekordów.
- Wejście = **tylko wklejenie do textarea** (`forms.py:36-91`,
  `templates/.../partials/step_fetch.html`); brak uploadu pliku.
- Po imporcie user ląduje na stronie jednej pracy (`DoneView`,
  `partials/step_done.html`) z linkiem „Importuj kolejną publikację" — czyli
  obecny workaround to „wróć i wklej następną ręcznie".

Efekt: przy wklejeniu 10 prac 9 z nich znika bez śladu.

## 2. Cel

Gdy user wklei ≥2 wpisy BibTeX, system tworzy **nadrzędny rekord-stager**
(`MultipleWorksImport`) trzymający wszystkie wpisy jako listę, pokazuje je,
i pozwala importować **po jednym** (leniwie — „drip"), odhaczając które są
zrobione, z możliwością pominięcia i ponowienia.

Zakres: **tylko provider BibTeX**, **tylko wklejanie** (bez uploadu pliku —
to osobny temat). Pozostałe providery i kontrakt `fetch()` — bez zmian.

## 3. Decyzje projektowe (zatwierdzone)

1. **Leniwy drip** — rodzic trzyma sparsowane wpisy; `ImportSession` powstaje
   *dopiero* gdy user kliknie „Importuj" na wierszu. Globalna lista sesji nie
   zapełnia się porzuconymi „oczekującymi" wizardami.
2. **Próg paczki: ≥2 wpisy.** 1 wpis → dziś-znana ścieżka pojedynczego
   wizardu, zero zmian. ≥2 → `MultipleWorksImport`.
3. **Stany wpisu: oczekuje / ✓ zaimportowany / błąd / pominięty**, z paskiem
   postępu „X z N zaimportowanych (+Y pominiętych)". Paczka „gotowa", gdy
   każdy wpis jest ✓ lub pominięty.
4. **Model dzieci zamiast JSON-bloba** — wpisy jako osobne wiersze
   (odpytywalne, mogą trzymać FK do sesji).
5. **Status wpisu WYLICZANY, nie przechowywany** — jedno źródło prawdy
   (`ImportSession.status` + flaga `skipped`), zero synchronizacji.
6. **Fan-out w warstwie wejścia, nie w `fetch()`** — kontrakt providera
   jedno-rekordowy zostaje nietknięty; wielo-rekordowość zamknięta w jednej
   nadpisywalnej metodzie `split_input()`.

## 4. Model danych

Nowe modele w `src/importer_publikacji/models.py`.

### `MultipleWorksImport` (rodzic / stager)

| Pole | Typ | Uwagi |
|------|-----|-------|
| `owner` | FK `settings.AUTH_USER_MODEL`, `on_delete=CASCADE` | kto wkleił |
| `provider_name` | `CharField` | na teraz zawsze `"BibTeX"` |
| `raw_input` | `TextField` | cały wklejony tekst (audyt / debug) |
| `created` | `DateTimeField(auto_now_add=True)` | |
| `modified` | `DateTimeField(auto_now=True)` | |

Postęp (X z N, Y pominiętych) liczony z dzieci — property, nie kolumna.

### `MultipleWorksImportEntry` (jeden wpis = jeden wiersz listy)

| Pole | Typ | Uwagi |
|------|-----|-------|
| `parent` | FK `MultipleWorksImport`, `related_name="entries"`, CASCADE | |
| `order` | `PositiveIntegerField` | kolejność z pliku |
| `raw_bibtex` | `TextField` | **pojedynczy** wpis, zserializowany z powrotem |
| `title` | `CharField(blank=True)` | cache do wyświetlenia na liście |
| `skipped` | `BooleanField(default=False)` | user świadomie odrzucił |
| `session` | FK `ImportSession`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name="batch_entry"` | podpięta po kliknięciu „Importuj" |

`Meta.ordering = ["order"]`.

### Wyliczany status wpisu

Property `MultipleWorksImportEntry.status` (enum `EntryStatus`):

```
skipped == True                                   -> SKIPPED   (pominięty)
session is None                                    -> PENDING   (oczekuje)
session.status == ImportSession.Status.COMPLETED   -> IMPORTED  (✓)
session.status in {IMPORT_FAILED, CANCELLED}       -> FAILED    (błąd)
w pozostałych przypadkach                          -> IN_PROGRESS (w toku)
```

`ImportSession` **nie jest modyfikowany**. Powiązanie trzyma wpis; Done-page
trafia do paczki przez odwrotność FK (`session.batch_entry`).

## 5. Warstwa providera — `split_input`

Do bazowej klasy `DataProvider` (`providers/__init__.py`) dochodzi metoda:

```python
def split_input(self, text: str) -> list[str]:
    """Rozbij surowe wejście na pojedyncze rekordy.

    Domyślnie provider jest jedno-rekordowy i zwraca wejście bez zmian.
    Providery wielo-rekordowe (BibTeX) nadpisują tę metodę.
    """
    return [text]
```

`BibTeXProvider.split_input` (`providers/bibtex.py`): parsuje
`bibtexparser.parse_string`, serializuje **każdy** `entry` z powrotem do
osobnego stringa BibTeX (`bibtexparser.write_string` na jedno-wpisowej
`Library`), zwraca listę N stringów. Kolejność zachowana.

`fetch()` i `validate_identifier()` — **bez zmian** (`entries[0]` jest teraz
zawsze poprawne, bo każdy kawałek to dokładnie jeden wpis). Istniejący
`test_fetch_multiple_entries_takes_first` zostaje zielony.

## 6. Przepływ

### 6.1. Wejście — modyfikacja `FetchView.post` (`views/wizard.py:98-176`)

Po walidacji formularza i wyborze `raw_input` (tryb `TEXT`):

```
pieces = provider.split_input(raw_input)
if len(pieces) >= 2:
    batch = MultipleWorksImport.objects.create(owner=..., provider_name=..., raw_input=...)
    for i, piece in enumerate(pieces):
        MultipleWorksImportEntry.objects.create(
            parent=batch, order=i, raw_bibtex=piece,
            title=<wyciągnięty tytuł lub "">,
        )
    return redirect("importer_publikacji:batch-detail", pk=batch.pk)
# len == 1 (lub provider jedno-rekordowy): ścieżka jak dziś, bez zmian
```

Idempotencja: istniejący guard działa per `(provider, identifier)`; dla paczki
`identifier` się nie tworzy, więc guard pojedynczej sesji zostaje nietknięty.
(Ochrona przed podwójnym wklejeniem tej samej paczki — poza zakresem MVP.)

Tytuł do cache: z `entry.fields_dict["title"]` jeśli jest; inaczej `""`.
Ekstrakcję tytułu z pojedynczego `raw_bibtex` robi helper providera
(np. `BibTeXProvider.peek_title(piece)`), żeby widok nie znał BibTeX-a.

### 6.2. Strona paczki — `MultipleWorksImportDetailView`

`DetailView` po `pk`, scoped do `owner=request.user` (jak istniejące widoki
sesji). Szablon `partials/batch_detail.html` w stylu istniejącego
`session_list.html` (Foundation). Kolumny: `#`, tytuł, status (badge),
akcja.

Akcje per wiersz zależne od statusu:

| Status | Badge | Akcja |
|--------|-------|-------|
| oczekuje | „oczekuje" | **[Importuj]** |
| w toku | „w toku" | **[Kontynuuj]** (→ `session.get_continue_url()`) |
| ✓ zaimportowany | „zaimportowano" | **[Zobacz pracę]** (link do utworzonego rekordu) |
| błąd | „błąd" | **[Ponów]** |
| pominięty | „pominięty" | **[Przywróć]** |

Nagłówek: pasek postępu „X z N zaimportowanych (+Y pominiętych)".

### 6.3. Import wpisu — `BatchEntryImportView` (POST)

1. Scoped: wpis należy do paczki należącej do `request.user`.
2. Tworzy **jedną** `ImportSession` z `identifier = entry.raw_bibtex`
   (przez wspólny helper wydzielony z `FetchView.post`, żeby nie duplikować
   logiki tworzenia sesji + enqueue `fetch_session_task`).
3. `entry.session = session; entry.save()`.
4. Redirect w istniejący wizard (`task-status`) — dalej wszystko jak dziś.
5. „Ponów" (dla statusu błąd): to samo, nadpisuje `entry.session` nową sesją.

### 6.4. Pomiń / Przywróć — `BatchEntrySkipView` (POST, toggle)

Toggle `entry.skipped`; redirect z powrotem na stronę paczki.

### 6.5. Powrót z wizardu — modyfikacja `DoneView` (`views/wizard.py:804-817`)

Jeśli `session.batch_entry.exists()` (sesja należy do wpisu paczki):
szablon `step_done.html` pokazuje przycisk **„Wróć do paczki (X z N)"**
(link do `batch-detail`) zamiast/obok generycznego „Importuj kolejną
publikację". Wpis automatycznie pokaże się jako ✓ (status wyliczany).

### 6.6. URL-e (`urls.py`)

```
batch/<int:pk>/                 -> batch-detail
batch/entry/<int:pk>/import/    -> batch-entry-import   (POST)
batch/entry/<int:pk>/skip/      -> batch-entry-skip     (POST)
```

(Opcjonalnie, poza MVP: lista paczek usera na stronie indeksu importera.)

## 7. Architektura — granice odpowiedzialności

- **Provider** (`bibtex.py`): jedyne miejsce znające format BibTeX
  (`split_input`, `peek_title`, istniejące `fetch`/`validate_identifier`).
- **Model** (`MultipleWorksImport*`): staging + wyliczanie statusu; nie zna
  Celery ani widoków.
- **Widoki** (`wizard.py`/nowe): orkiestracja — split → utwórz paczkę →
  drip pojedynczych sesji przez wspólny helper.
- **`ImportSession`**: nietknięty; wciąż 1 sesja = 1 praca.

## 8. Testy (TDD — test przed implementacją)

`tests/`:

1. `split_input`: BibTeX z N wpisów → lista N stringów, każdy parsuje się do
   1 wpisu, kolejność zachowana; provider jedno-rekordowy → `[text]`.
2. `peek_title`: wyciąga tytuł z pojedynczego wpisu; brak tytułu → `""`.
3. `FetchView`: paste ≥2 → tworzy `MultipleWorksImport` + N `Entry`,
   redirect na `batch-detail`; paste 1 → dokładnie jak dziś (jedna sesja,
   brak paczki).
4. `MultipleWorksImportEntry.status`: każdy z 5 przypadków (skipped / brak
   session / COMPLETED / IMPORT_FAILED / CANCELLED / stan pośredni).
5. `BatchEntryImportView`: tworzy sesję z poprawnym pojedynczym `raw_bibtex`,
   podpina `entry.session`, redirect w wizard; „Ponów" nadpisuje sesję.
6. `BatchEntrySkipView`: toggluje `skipped`.
7. `DoneView`: gdy sesja należy do paczki → kontekst zawiera link powrotny
   i licznik X z N.
8. Charakteryzacyjny (regresja): `test_fetch_multiple_entries_takes_first`
   **zostaje zielony** — dowód, że warstwa providera `fetch()` się nie
   zmieniła.

Konwencje: pytest (funkcje, bez klas), `@pytest.mark.django_db`,
`model_bakery.baker.make`, fixtures w `conftest.py`.

## 9. Migracje

- Jedna migracja `makemigrations importer_publikacji` (dwa nowe modele +
  FK `Entry.session → ImportSession`).
- **Baseline `baseline-sql/baseline.sql` NIE odświeżany na tym branchu**
  (per CLAUDE.md: konflikty na wielkim pliku w równoległych branchach;
  refresh dopiero przy scalaniu do `dev`).
- `makemigrations --check` musi przechodzić (brak driftu).

## 10. Poza zakresem (YAGNI)

- Upload pliku `.bib` (osobny temat — dziś tylko wklejanie).
- Wielo-rekordowość dla innych providerów (RIS itd.) — `split_input`
  domyślnie `[text]` zostawia to otwarte na przyszłość bez pracy teraz.
- Deduplikacja/wykrywanie duplikatów wpisów względem BPP na etapie listy
  (matching dzieje się w istniejącym wizardzie per wpis).
- Ochrona przed dwukrotnym wklejeniem tej samej paczki.
- Lista wszystkich paczek usera (opcjonalny link, nie MVP).
