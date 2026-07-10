# Import wielu prac naraz z BibTeX-a (`MultipleWorksImport`)

**Data:** 2026-07-09
**Branch:** `feat-bibtex-import-wiele-prac` (worktree, off `dev`)
**Moduł:** `src/importer_publikacji/`

> Wersja 2 — po self-review Fable 5. Sekcje 4–10 uwzględniają: obsługę
> `failed_blocks` (blocker), group-scoping widoków, wzorzec HX-Redirect,
> reużycie istniejącego retry, `is_stalled()` w wyliczaniu statusu,
> batch-aware `CancelView`, `OneToOneField`, oraz `raw_bibtex = entry.raw`.

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
  `templates/.../partials/step_fetch.html`); brak uploadu pliku. Formularz
  jest **HTMX** (`hx-post`, `hx-target="#importer-wizard"`), a `FetchView`
  zwraca nawigację przez nagłówek **`HX-Redirect`** (`wizard.py:147-151`,
  `171-175`) — nie zwykły `redirect()`.
- Po imporcie user ląduje na stronie jednej pracy (`DoneView`,
  `partials/step_done.html`) z linkiem „Importuj kolejną publikację"; wersja
  anulowana (`CancelView`, `wizard.py:820-837`) wraca na indeks importera.

Efekt: przy wklejeniu 10 prac 9 z nich znika bez śladu.

## 2. Cel

Gdy user wklei ≥2 wpisy BibTeX, system tworzy **nadrzędny rekord-stager**
(`MultipleWorksImport`) trzymający wszystkie wpisy jako listę, pokazuje je,
i pozwala importować **po jednym** (leniwie — „drip"), odhaczając które są
zrobione, z możliwością pominięcia i ponowienia. **Uszkodzone wpisy też są
pokazane** (nic nie znika po cichu).

Zakres: **tylko provider BibTeX**, **tylko wklejanie** (bez uploadu pliku —
to osobny temat). Pozostałe providery i kontrakt `fetch()` — bez zmian.

## 3. Decyzje projektowe (zatwierdzone)

1. **Leniwy drip** — rodzic trzyma sparsowane wpisy; `ImportSession` powstaje
   *dopiero* gdy user kliknie „Importuj" na wierszu. Globalna lista sesji nie
   zapełnia się porzuconymi „oczekującymi" wizardami.
2. **Próg paczki: ≥2 rekordy** (wpisy + uszkodzone bloki łącznie). 1 poprawny
   wpis → dziś-znana ścieżka pojedynczego wizardu, zero zmian. ≥2 →
   `MultipleWorksImport`.
3. **Stany wpisu: oczekuje / ✓ zaimportowany / błąd / pominięty / uszkodzony**,
   z paskiem postępu „X z N zaimportowanych (+Y pominiętych)". Paczka „gotowa",
   gdy każdy wpis jest ✓ lub pominięty.
4. **Model dzieci zamiast JSON-bloba** — wpisy jako osobne wiersze
   (odpytywalne, mogą trzymać FK do sesji).
5. **Status wpisu WYLICZANY, nie przechowywany** — jedno źródło prawdy
   (`ImportSession.status` + `skipped` + `parse_error`), zero synchronizacji.
6. **Fan-out w warstwie wejścia, nie w `fetch()`** — kontrakt providera
   jedno-rekordowy zostaje nietknięty; wielo-rekordowość zamknięta w jednej
   nadpisywalnej metodzie `split_input()`.

## 4. Model danych

Nowe modele w `src/importer_publikacji/models.py`. Rejestracja w
`admin.py` (oba modele; `Entry` jako `TabularInline` na rodzicu — podgląd/debug).

### `MultipleWorksImport` (rodzic / stager)

| Pole | Typ | Uwagi |
|------|-----|-------|
| `created_by` | FK `settings.AUTH_USER_MODEL`, `on_delete=CASCADE` | kto wkleił (nazwa spójna z resztą modułu) |
| `provider_name` | `CharField(max_length=50)` | na teraz zawsze `"BibTeX"` |
| `raw_input` | `TextField` | cały wklejony tekst (audyt / debug) |
| `created` | `DateTimeField(auto_now_add=True)` | |
| `modified` | `DateTimeField(auto_now=True)` | |

**Postęp** — property `progress` liczone jednym zapytaniem:
`self.entries.select_related("session")` → policz statusy w Pythonie (N małe),
zwróć `{"imported": X, "skipped": Y, "total": N, "done": bool}`.
`done == all(status in {IMPORTED, SKIPPED})`.

### `MultipleWorksImportEntry` (jeden rekord = jeden wiersz listy)

| Pole | Typ | Uwagi |
|------|-----|-------|
| `parent` | FK `MultipleWorksImport`, `related_name="entries"`, CASCADE | |
| `order` | `PositiveIntegerField` | kolejność z wejścia |
| `raw_bibtex` | `TextField` | **pojedynczy** wpis, `entry.raw` (verbatim) lub raw uszkodzonego bloku |
| `title` | `TextField(blank=True)` | cache do wyświetlenia (BibTeX titles bywają >255 zn.) |
| `parse_error` | `TextField(blank=True)` | niepuste = blok się nie sparsował (`failed_block`) |
| `skipped` | `BooleanField(default=False)` | user świadomie odrzucił |
| `session` | `OneToOneField` `ImportSession`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name="batch_entry"` | podpięta po „Importuj"; `OneToOne` → reverse `session.batch_entry` jest pojedyncze |

`Meta.ordering = ["order"]`.

### Wyliczany status wpisu — property `status` (enum `EntryStatus`)

Precedencja (pierwszy pasujący wygrywa):

```
1. session and session.status == COMPLETED          -> IMPORTED   (✓)
2. skipped                                           -> SKIPPED    (pominięty)
3. parse_error                                       -> MALFORMED  (uszkodzony)
4. session is None                                   -> PENDING    (oczekuje)
5. session.status == IMPORT_FAILED or session.is_stalled()  -> FAILED  (błąd)
6. session.status == CANCELLED                       -> PENDING    (re-importowalny)
7. wpp.                                               -> IN_PROGRESS (w toku)
```

Uwagi:
- **COMPLETED sprawdzane jako pierwsze** — chroni odhaczoną pracę przed
  przypadkowym „odskipowaniem" (belt-and-suspenders razem z guardem skipu, §6.4).
- **`is_stalled()`** (`models.py:230-270`, martwy worker w FETCHING/CREATING
  > `IMPORTER_STALL_TIMEOUT`) mapuje na **błąd** — inaczej wpis wisiałby „w toku"
  wiecznie i paczka nigdy nie byłaby „gotowa".
- **CANCELLED → PENDING** — anulowanie wizardu to świadoma rezygnacja, nie błąd;
  wpis wraca do „oczekuje" i można go zaimportować od nowa (nowa sesja
  nadpisze `entry.session`; anulowana sesja zostaje osierocona, nieszkodliwie).

`ImportSession` **nie jest modyfikowany**. Powiązanie trzyma wpis; strony
wizardu (Done/Cancel) trafiają do paczki przez `session.batch_entry`.

## 5. Warstwa providera — `split_input`

Do bazowej klasy `DataProvider` (`providers/__init__.py`) dochodzi metoda
zwracająca **strukturę** (nie gołe stringi — musimy odróżnić poprawny wpis od
uszkodzonego bloku oraz nieść tytuł):

```python
@dataclass
class SplitRecord:
    raw: str                 # surowy tekst tego rekordu (verbatim)
    ok: bool = True          # False => nie sparsował się
    title: str = ""          # do wyświetlenia na liście
    error: str = ""          # komunikat, gdy ok is False

def split_input(self, text: str) -> list[SplitRecord]:
    """Rozbij surowe wejście na pojedyncze rekordy.

    Domyślnie provider jest jedno-rekordowy i zwraca wejście bez zmian.
    Providery wielo-rekordowe (BibTeX) nadpisują tę metodę.
    """
    return [SplitRecord(raw=text)]
```

`BibTeXProvider.split_input` (`providers/bibtex.py`):

1. `library = bibtexparser.parse_string(text)`.
2. Dla **każdego** `entry in library.entries`: `SplitRecord(raw=entry.raw,
   ok=True, title=<peek_title(entry)>)`. `entry.raw` (verbatim) preferowane
   nad re-serializacją — zachowuje dokładny input i omija kwirki
   `write_string`. Każdy `entry.raw` re-parsuje się do dokładnie 1 wpisu,
   więc istniejące `fetch()` (`entries[0]`) działa bez zmian.
3. Dla **każdego** `block in library.failed_blocks` (**blocker z review** —
   inaczej uszkodzone wpisy znikają jak dziś): `SplitRecord(raw=block.raw,
   ok=False, error=<opis błędu bloku>)`.
4. Zwróć rekordy w kolejności wejścia — iterując po `library.blocks`
   (zawiera i `Entry`, i `ParsingFailedBlock` w kolejności źródłowej), więc
   wpisy i błędy przeplatają się poprawnie bez ręcznego sortowania.

`peek_title(entry)` — helper providera: `entry.fields_dict["title"].value`
(v2 zwraca obiekt `Field`, trzeba `.value`, por. `_get_field`
`bibtex.py:150-155`), przepuszczone przez istniejące `_clean_latex`; brak
tytułu → `""`.

`fetch()` i `validate_identifier()` — **bez zmian**. Istniejący
`test_fetch_multiple_entries_takes_first` zostaje zielony (dowód, że warstwa
`fetch()` się nie zmieniła).

## 6. Przepływ

### 6.1. Wejście — modyfikacja `FetchView.post` (`views/wizard.py:98-176`)

Po walidacji formularza i wyborze `raw_input` (tryb `TEXT`):

```
records = provider.split_input(raw_input)
if len(records) >= 2:
    batch = MultipleWorksImport.objects.create(
        created_by=request.user, provider_name=provider.name, raw_input=raw_input)
    for i, rec in enumerate(records):
        MultipleWorksImportEntry.objects.create(
            parent=batch, order=i, raw_bibtex=rec.raw,
            title=rec.title, parse_error=("" if rec.ok else rec.error))
    return hx_redirect("importer_publikacji:batch-detail", batch_id=batch.pk)
# len == 1 (lub provider jedno-rekordowy): ścieżka jak dziś, bez zmian
```

`hx_redirect` = ten sam wzorzec `HX-Redirect` co istniejący `FetchView`
(`wizard.py:147-151`) — bo form jest HTMX i zwykły `redirect()` wpadłby do
diva wizardu zamiast nawigować.

Idempotencja: istniejący double-click guard `(created_by, provider_name,
identifier)` (`wizard.py:129-151`) dotyczy pojedynczej sesji i zostaje
nietknięty. Ochrona przed dwukrotnym wklejeniem tej samej **paczki** — poza
zakresem MVP.

### 6.2. Strona paczki — `MultipleWorksImportDetailView`

`DetailView` po `batch_id`, **group-scoped** przez istniejący
`ImporterPermissionMixin` (`permissions.py:6-12`, `GR_WPROWADZANIE_DANYCH`) —
**tak jak reszta widoków importera** (nie owner-scoped; sesje wizardu są
group-scoped, więc owner-scoping paczki byłby asymetryczny).

Przed renderem: **sweep `mark_stalled()`** po wpisach z sesją in-flight
(FETCHING/CREATING), żeby zombie od martwego workera pokazały „błąd", nie
„w toku". Query: `batch.entries.select_related("session")` (bez N+1).

Szablon `partials/batch_detail.html` w stylu istniejącego
`session_list.html` (Foundation). Kolumny: `#`, tytuł, status (etykieta
tekstowa `status_label`), akcja:

| Status | Badge | Akcja |
|--------|-------|-------|
| oczekuje | „oczekuje" | **[Importuj]** (POST) |
| w toku | „w toku" | **[Kontynuuj]** (→ `session.get_continue_url()`) |
| ✓ zaimportowany | „zaimportowano" | **[Zobacz pracę]** (link do utworzonego rekordu) |
| błąd | „błąd" | **[Ponów]** (POST) + **[Pomiń]** |
| uszkodzony | „uszkodzony" | **[Pomiń]** (brak importu — pokazany `parse_error` + raw) |
| pominięty | „pominięty" | **[Przywróć]** (POST) |

Nagłówek: callout z licznikiem „X z N zaimportowanych (+Y pominiętych)" z
`progress` (tekst, nie graficzny pasek).

### 6.3. Import wpisu — `BatchEntryImportView` (POST, `entry_id`)

1. Group-scoped (jak §6.2). Odrzuć, jeśli `entry.parse_error` (uszkodzony —
   nie ma czego importować).
2. **Guard in-flight**: jeśli `entry.session` istnieje i nie jest
   `COMPLETED`/`IMPORT_FAILED`/`CANCELLED`/stalled → redirect na
   `entry.session.get_continue_url()` (nie twórz drugiej sesji — chroni przed
   double-click, tak jak C2 w `FetchView`).
3. Inaczej: utwórz **jedną** `ImportSession` z `identifier = entry.raw_bibtex`
   przez **wspólny helper** wydzielony z `FetchView.post` (tworzenie sesji +
   `fetch_session_task.delay`). **Helper NIE zawiera** guardu double-click
   po `identifier` — dwa identyczne wpisy w jednej paczce (duplikaty w
   eksportach .bib są częste, a `raw_bibtex` bywa bajt-w-bajt identyczny) nie
   mogą się skrzyżować w jedną sesję; izolację daje guard z pkt 2 po
   `entry.session`.
4. `entry.session = session; entry.save()` (`OneToOne` — nadpisanie przy
   re-imporcie porzuca starą sesję, co jest OK).
5. `hx_redirect` w istniejący wizard (`task-status`).
6. **[Ponów]** (status błąd): **deleguje do istniejącego `ImportTaskRetryView`**
   (`urls.py:130-134`), który wznawia **tę samą** `entry.session` od
   `last_failed_stage` — nie tworzymy nowej sesji, nie osieracamy starej.

### 6.4. Pomiń / Przywróć — `BatchEntrySkipView` (POST toggle, `entry_id`)

Toggle `entry.skipped`. **Guard**: nie pozwól skipować wpisu w statusie
IMPORTED (ochrona arytmetyki postępu). Redirect z powrotem na stronę paczki.

### 6.5. Powrót z wizardu — `DoneView` + `CancelView`

**`DoneView`** (`wizard.py:804-817`): jeśli `hasattr(session, "batch_entry")`
→ wstrzyknij do kontekstu `batch` i `batch.progress`; szablon `step_done.html`
pokazuje **„Wróć do paczki (X z N)"** (link do `batch-detail`) obok/zamiast
„Importuj kolejną publikację". Kontekst liczony **w widoku** (nie trawersacją
managera w szablonie).

**`CancelView`** (`wizard.py:820-837`): analogicznie — jeśli sesja należy do
paczki, wróć na `batch-detail` zamiast na indeks importera. Wpis wróci do
„oczekuje" (status wyliczany, CANCELLED → PENDING).

### 6.6. URL-e (`urls.py`)

```
batch/<int:batch_id>/                 -> batch-detail
batch/entry/<int:entry_id>/import/    -> batch-entry-import   (POST)
batch/entry/<int:entry_id>/skip/      -> batch-entry-skip     (POST)
```

([Ponów] używa istniejącego route retry, nie nowego.) Opcjonalnie, poza MVP:
lista paczek usera na indeksie importera.

## 7. Architektura — granice odpowiedzialności

- **Provider** (`bibtex.py`): jedyne miejsce znające format BibTeX
  (`split_input`, `peek_title`, istniejące `fetch`/`validate_identifier`).
  `SplitRecord` — kontrakt wyjścia, agnostyczny wobec formatu.
- **Model** (`MultipleWorksImport*`): staging + wyliczanie statusu + postęp;
  nie zna Celery ani widoków.
- **Widoki** (`wizard.py`/nowe): orkiestracja — split → utwórz paczkę →
  drip pojedynczych sesji przez wspólny helper; reużycie retry.
- **`ImportSession`**: nietknięty; wciąż 1 sesja = 1 praca.

## 8. Testy (TDD — test przed implementacją)

`tests/`:

1. `split_input` (BibTeX): N poprawnych wpisów → N `SplitRecord(ok=True)`,
   każdy `raw` re-parsuje się do 1 wpisu, kolejność zachowana; provider
   jedno-rekordowy → 1 `SplitRecord`.
2. `split_input` z **uszkodzonym środkowym wpisem** (3 wpisy, 2 poprawne,
   1 zły) → 3 rekordy, środkowy `ok=False` z `error` (regresja blockera:
   nic nie znika).
3. `peek_title`: wyciąga tytuł (unwrap `.value` + `_clean_latex`); brak → `""`.
4. `FetchView`: paste ≥2 → `MultipleWorksImport` + N `Entry` (w tym MALFORMED
   dla złych), zwraca **`HX-Redirect`** na `batch-detail`; paste 1 poprawny →
   dokładnie jak dziś (jedna sesja, brak paczki).
5. `MultipleWorksImportEntry.status`: **6 przypadków** — IMPORTED (COMPLETED),
   SKIPPED, MALFORMED (parse_error), PENDING (brak sesji), FAILED
   (IMPORT_FAILED **oraz** `is_stalled()`), PENDING (CANCELLED), IN_PROGRESS.
6. `BatchEntryImportView`: tworzy sesję z poprawnym pojedynczym `raw_bibtex`,
   podpina `entry.session`, `HX-Redirect` w wizard; **guard in-flight**
   (drugi POST → redirect na continue, brak drugiej sesji); MALFORMED →
   odrzucone.
7. `[Ponów]`: używa `ImportTaskRetryView` na **tej samej** sesji (brak nowej).
8. `BatchEntrySkipView`: toggluje `skipped`; guard — nie skipuje IMPORTED.
9. `DoneView`/`CancelView`: gdy sesja należy do paczki → kontekst z linkiem
   powrotnym i „X z N"; Cancel wraca na `batch-detail`.
10. Charakteryzacyjny (regresja): `test_fetch_multiple_entries_takes_first`
    **zostaje zielony**.

Konwencje: pytest (funkcje, bez klas), `@pytest.mark.django_db`,
`model_bakery.baker.make`, fixtures w `conftest.py`.

## 9. Migracje

- Jedna migracja `makemigrations importer_publikacji` (dwa nowe modele +
  `OneToOneField Entry.session → ImportSession`).
- **Baseline `baseline-sql/baseline.sql` NIE odświeżany na tym branchu**
  (per CLAUDE.md: konflikty na wielkim pliku w równoległych branchach;
  refresh dopiero przy scalaniu do `dev`).
- `makemigrations --check` musi przechodzić (brak driftu).

## 10. Poza zakresem (YAGNI)

- Upload pliku `.bib` (osobny temat — dziś tylko wklejanie).
- Wielo-rekordowość dla innych providerów (RIS itd.) — `split_input`
  domyślnie 1 `SplitRecord` zostawia to otwarte bez pracy teraz.
- Deduplikacja duplikatów wpisów względem BPP na etapie listy (matching
  dzieje się w istniejącym wizardzie per wpis).
- Ochrona przed dwukrotnym wklejeniem tej samej paczki.
- Lista wszystkich paczek usera (opcjonalny link, nie MVP).
- **Bloki `@string`/`@preamble`** z wklejonego BibTeX-a są tracone przy
  rozbiciu per-wpis. W praktyce nieistotne: v2 `fetch()` i tak ich nie
  interpoluje, a w pastowanych eksportach występują rzadko.

## 11. Erata — zgodność z implementacją (po final review + self-review Fable 5)

Ten rozdział prostuje rozjazdy między wcześniejszymi sekcjami a kodem, który
faktycznie trafił do PR #511. Kod jest źródłem prawdy; sekcje 1–10 to zapis
projektowy.

- **§6.3 — guard na wpis już zaimportowany (dodany w final review).** Kod
  `BatchEntryImportView` na starcie odrzuca re-import: `if entry.status ==
  EntryStatus.IMPORTED: return redirect(session.get_continue_url())`. Zapobiega
  **duplikacji publikacji** przy nieświeżym formularzu (druga karta) lub
  powtórzonym POST. Sekcja §6.3 pierwotnie wpuszczała status COMPLETED w
  ścieżkę „utwórz sesję" — to było błędne; obowiązuje guard.
- **§6.2 / §6.3 pkt 5 — przekierowania batcha.** Formularze na stronie paczki
  (Importuj/Pomiń/Przywróć) to zwykły `method="post"`, a widoki zwracają
  zwykłe `HttpResponseRedirect` (302), NIE `HX-Redirect`. `HX-Redirect`
  pojawia się **warunkowo** (tylko gdy jest nagłówek `HX-Request`) w fan-oucie
  `FetchView` i w batch-aware `CancelView` — bo to odpowiedzi na żądania HTMX
  z wizardu; bez `HX-Request` oba i tak zwracają zwykłe 302.
- **§6.2 — wiersz „uszkodzony".** Szablon pokazuje `parse_error` (komunikat);
  surowy tekst bloku jest przechowywany w `raw_bibtex`, ale nie renderowany.
  `error` w `SplitRecord` to statyczny komunikat — szczegółowy błąd parsera
  bibtexparsera nie jest przenoszony (świadome uproszczenie).
- **§6.2 — [Pomiń] dla wpisów „oczekuje".** Dodane po review Fable 5: wpis
  oczekujący ma obok [Importuj] także [Pomiń] — inaczej `progress.done`
  („każdy wpis ✓ lub pominięty", §3.3) był nieosiągalny dla paczek, z których
  część prac użytkownik świadomie odrzuca.
- **§1/§2 — `input_help_text` zaktualizowany.** Stary tekst („zostanie użyty
  pierwszy") był teraz nieprawdą; kod zwraca opis trybu paczki.
- **§6.1 — znany edge case (nie naprawiony w tym PR).** `FetchView` woła
  `validate_identifier()` PRZED `split_input`; walidator BibTeX odrzuca wsad
  bez ani jednego poprawnego wpisu. Skutek: paste złożony **wyłącznie** z
  uszkodzonych bloków (0 poprawnych) nie tworzy paczki — user dostaje ogólny
  błąd formularza. Rzadki przypadek; potencjalny follow-up (przenieść bramkę
  walidacji za split lub uwzględnić `failed_blocks` w progu).
- **§8 — luki testowe (follow-up).** Brak testu delegacji [Ponów] do
  `ImportTaskRetryView` na tej samej sesji (dziś tylko wiring w szablonie);
  fan-outowy test używa wpisów poprawnych (brak przypadku MALFORMED na poziomie
  `FetchView`). Ścieżki te są pokryte pośrednio (`split_input` z uszkodzonym
  blokiem, `task-retry` istnieje), ale nie end-to-end w kontekście paczki.
- **§5 / §8 — `peek_title` czyści LaTeX (naprawione).** Po 2. self-review
  Fable 5: `peek_title` przepuszcza tytuł przez `_clean_latex`, więc podgląd na
  liście nie pokazuje klamer/komend LaTeX; §5 i test w §8 są teraz zgodne z
  kodem (`test_bibtex_peek_title_strips_latex_braces`).
- **Drobne follow-upy (nieblokujące):** N+1 na `created_record` (GenericFK)
  przy wielu ukończonych wpisach; reużycie `_hx_or_redirect` w batch-branchu
  `CancelView`.
