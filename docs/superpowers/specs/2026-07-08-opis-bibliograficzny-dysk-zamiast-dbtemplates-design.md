# Opis bibliograficzny z dysku zamiast z dbtemplates

Data: 2026-07-08
Ticket: Freshdesk #329 ("wyd. zwarte - problem")
Kontynuacja: PR #409 (`fix(#329)`) — warstwa 1 (render rodzica z PBN) + doraźny
`drop_dbtemplate`. Ten spec robi warstwę 2 „na serio".

## Kontekst

Zgłoszenie #329 (Biblioteka Naukowa IHiT): rozdział książki z wydawnictwem
nadrzędnym pobranym z PBN nie pokazuje rodzica w opisie bibliograficznym.

PR #409 naprawił **render** (szablon `opis_bibliograficzny.html` czyta rodzica
z surowego JSON-a PBN `object.book` przez akcesor `book_title`), ale poprawka
jest niewidoczna w istniejących instalacjach, bo wiersz dbtemplates
`opis_bibliograficzny.html` w bazie **zasłania** plik z dysku (loader
dbtemplates stoi pierwszy w łańcuchu). PR #409 dołożył doraźną komendę
`drop_dbtemplate` — ale to operacja, którą trzeba ręcznie odpalić u każdego
klienta.

Dodatkowo wyszły dwa problemy strukturalne:

1. **`compare_dbtemplates` kłamie.** Komenda ma porównywać wiersz dbtemplates z
   plikiem na dysku, ale czyta „dysk" przez `get_template()`, który idzie
   łańcuchem loaderów — a loader dbtemplates stoi **pierwszy**. Więc dostaje
   treść z **bazy** i porównuje DB-vs-DB → zawsze „All templates match".
   Dokładnie w scenariuszu, dla którego powstała (wykrycie driftu), wprowadza
   w błąd. Potwierdzone w kodzie: `compare_dbtemplates.py:322-332`
   (`get_filesystem_template_content` → `get_template(name)` → `.template.source`
   = treść z DB).
2. **`opis_bibliograficzny.html` nie musi być w dbtemplates.** Render i tak
   ładuje po nazwie (`util.opis_bibliograficzny()` → `get_template(name)`), a
   samo trzymanie kopii dysku w bazie generuje drift, shadowing i potrzebę
   `drop_dbtemplate`.

## Architektura wyjściowa (jak jest dziś)

- `SzablonDlaOpisuBibliograficznego` (`src/bpp/models/szablondlaopisubibliograficznego.py`):
  - `model` — OneToOne do `ContentType` (jeden z 5 modeli publikacji lub NULL =
    domyślny dla wszystkich),
  - `template` — **FK do `dbtemplates.Template`** (`on_delete=PROTECT`),
  - `render(praca)` i manager `get_for_model()` używają FK **wyłącznie** po to,
    by wyciągnąć `.template.name`; faktyczny render to `get_template(name)`.
- `AbstractModel.opis_bibliograficzny()` (`src/bpp/models/util.py:91`):
  `template_name = get_for_model(self)` (fallback `"opis_bibliograficzny.html"`)
  → `get_template(template_name)` → render.
- Migracja `src/bpp/migrations/0295_instaluj_szablony.py` zasiewa do dbtemplates
  `opis_bibliograficzny.html` **oraz** `browse/praca_tabela.html`, i tworzy
  wpis `SzablonDlaOpisu` (model=NULL) wskazujący na `opis_bibliograficzny.html`.
- Loader dbtemplates **nie tworzy** wierszy przy renderze (`loader.py` tylko
  `Template.objects.get(...)`). `DBTEMPLATES_AUTO_POPULATE_CONTENT=True`
  działa **tylko** przy `Template.save()` z pustą treścią (`models.py:63`) i w
  adminie — **nie** przy ładowaniu. Wniosek kluczowy: **skasowany wiersz nie
  wróci** przy renderze. Kasowanie w migracji jest trwałe.

## Decyzja (zatwierdzona)

**Kierunek A + zakres B + naprawa compare (A).** Dysk staje się jedynym
źródłem prawdy dla `opis_bibliograficzny`; mapowanie per-model przeżywa, ale
wskazuje **nazwę szablonu**, nie wiersz DB. `browse/praca_tabela.html` i reszta
dbtemplates **poza zakresem**.

Konsekwencja edytowalności (świadomie zaakceptowana): opisu **nie** edytuje się
już z admina dbtemplates — zmiana treści opisu = zmiana pliku w kodzie +
wydanie. W zamian znika drift, shadowing i `drop_dbtemplate` dla opisu, a #329
**naprawia się samo** przy podbiciu wydania (migracja kasuje wiersz).

## Zakres zmian

### 1. Model `SzablonDlaOpisuBibliograficznego`

- Usuń `template = FK(dbtemplates.Template, PROTECT)`.
- Dodaj `nazwa_szablonu = models.CharField(max_length=255)` — nazwa dla loadera
  Django (loader-relative, np. `"opis_bibliograficzny.html"`), **nie** ścieżka
  pliku. Stąd `nazwa_szablonu`, nie `nazwa_pliku`.
- `get_for_model()` zwraca `.nazwa_szablonu` (fallback bez zmian w `util.py`).
- `get_models_for_template(template)` → `get_models_for_szablon(nazwa_szablonu)`
  (filtr `SzablonDlaOpisu.filter(nazwa_szablonu=…)`).
- `render()` / `__str__` / `get_models_for_this_szablon()` przełączone na
  `nazwa_szablonu`.
- **`clean()`**: waliduje, że `nazwa_szablonu` rozwiązuje się na dysku (przez
  helper z §2). Literówka w adminie → błąd walidacji, nie `TemplateDoesNotExist`
  przy renderze rekordu.
- Admin: pole `nazwa_szablonu` jako **wolny tekst + walidacja `clean()`**
  (YAGNI; `Select` z wykrytymi szablonami odrzucony jako przekombinowany —
  enumeracja szablonów jest rozmyta). `help_text` z domyślną nazwą.

### 2. Helper: źródło szablonu z dysku (bez loadera dbtemplates)

Nowa, izolowana jednostka (np. `src/bpp/util/dbtemplates_disk.py` albo dołożone
do istniejącego util). Module-level `Engine` z **tylko** loaderami
`filesystem` + `app_directories` (bez dbtemplates), zbudowany z
`TEMPLATES['DIRS']` + `app_dirs=True`. Publiczne API:

```python
def disk_template_source(name: str) -> str | None:
    """Źródło szablonu `name` z DYSKU, z pominięciem loadera dbtemplates.
    None, gdy pliku nie ma na dysku."""
```

Reużywane przez: §1 (`clean()`) i §3 (naprawa compare). Jedno miejsce zna
prawdę „co jest na dysku".

Kontrakt: co robi (zwraca źródło z dysku), jak używać (`disk_template_source`),
od czego zależy (settings TEMPLATES). Testowalny w izolacji.

### 3. Naprawa `compare_dbtemplates` (punkt JEDEN)

`get_filesystem_template_content()` przestaje wołać `get_template()` — używa
`disk_template_source(name)`. Teraz porównanie to realne DB-vs-dysk.
Repro-test (red-first): zasiej wiersz dbtemplates różny od pliku na dysku →
komenda **musi** pokazać diff (dziś kłamie „match").

### 4. Migracja (nowy plik — starych nie ruszamy)

W aplikacji `bpp`, po `0295` i po migracjach z #409:

1. Schema: dodaj `nazwa_szablonu` (CharField, tymczasowo nullable/z defaultem).
2. Data (forward): dla każdego wiersza `SzablonDlaOpisu` ustaw
   `nazwa_szablonu = template.name`. Sprawdź dysk helperem z §2:
   - jest na dysku → OK, wiersz dbtemplates do skasowania w kroku 4,
   - **brak na dysku** (DB-only custom) → głośne ostrzeżenie (`stderr`/print) i
     **nie** kasuj tego wiersza dbtemplates (postawa A: nie psuj po cichu).
3. Schema: usuń FK `template`; ustaw `nazwa_szablonu` NOT NULL.
4. Data: skasuj wiersze `dbtemplates.Template` **mapowane przez `SzablonDlaOpisu`
   i mające odpowiednik na dysku** (standardowo: `opis_bibliograficzny.html`).
   `browse/praca_tabela.html` i wszystko niezmapowane — **nietknięte**.
- Reverse: best-effort dla dev (odtwórz FK + wiersz z treści dysku).
- Po merge (raz, przy scalaniu): `make baseline-update` — reguła CLAUDE;
  migracja waliduje się przy tym na czystym kontenerze.

### 5. `drop_dbtemplate` — wymuszone odsprzęgnięcie

`drop_dbtemplate` (`src/bpp/management/commands/drop_dbtemplate.py`) dziś
importuje `SzablonDlaOpisuBibliograficznego` i filtruje `filter(template=…)`
(bo FK był `PROTECT`, więc trzeba było najpierw usunąć powiązania). Po usunięciu
FK ten filtr **przestanie się kompilować** — komendę trzeba odsprzęgnąć od
`SzablonDlaOpisu`. Zostaje ogólnym narzędziem do kasowania dbtemplates
(np. `browse/praca_tabela.html`). To wymuszona część zakresu, nie opcja.

### 6. Ścieżka renderu (świadoma decyzja: bez zmian)

`util.opis_bibliograficzny()` **zostaje na `get_template()`**. Po skasowaniu
wiersza dysk i tak wygrywa; to hot-path (~150 szablonów/stronę), więc nie
forsujemy tam disk-only — mniejsze ryzyko, zero zmiany zachowania. Disk-only
żyje tylko w compare (§3) i walidacji (§1).

## Testy

- **Repro compare** (red-first): wiersz DB ≠ dysk → komenda pokazuje diff.
- **Migracja**: backfill `nazwa_szablonu`; skasowanie wiersza
  `opis_bibliograficzny.html`; ścieżka ostrzeżenia dla szablonu bez pliku na
  dysku (nie kasuje, ostrzega).
- **`clean()`**: zła nazwa odrzucona; poprawna przechodzi.
- **Render opisu**: renderuje się z dysku bez wiersza DB; rodzic z PBN
  `object.book` dalej widoczny (reuse testów #329 — teraz bez wiersza DB).
- **`get_for_model`**: zwraca `nazwa_szablonu`.

## Poza zakresem

- `browse/praca_tabela.html` i inne dbtemplates — zostają.
- Usunięcie aplikacji dbtemplates — nie.
- Logika PBN `object.book` w szablonie — bez zmian (już w #409).
- Weryfikacja/wgranie u klienta (IHiT) i zamknięcie zgłoszenia — osobno
  (to „skill #2"); tu dostarczamy tylko kod + migrację, która samoczynnie
  naprawia po podbiciu wydania.

## Ryzyka i pułapki

- **Auto-populate**: zweryfikowane, że loader NIE odtwarza wierszy — kasowanie
  jest trwałe. Gdyby ktoś w przyszłości włączył odtwarzanie w loaderze, założenie
  pada.
- **DB-only custom** (wiersz `SzablonDlaOpisu` → szablon bez pliku na dysku):
  obsłużone postawą A (ostrzeżenie, brak kasowania). Kierunek A zakłada, że nie
  występuje; migracja nie psuje po cichu, gdyby jednak wystąpił.
- **Stary wiersz dbtemplates po deployu**: znika w migracji; nie wróci przy
  renderze. Jedyny sposób, by wrócił, to ręczne utworzenie w adminie.
- **Nie modyfikować istniejących migracji** — nowy plik migracji (reguła CLAUDE).
- **Baseline**: odświeżyć `make baseline-update` przy scalaniu, nie w gałęzi
  równoległej.
