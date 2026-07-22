# Opis bibliograficzny z dysku zamiast z dbtemplates

Data: 2026-07-08
Ticket: Freshdesk #329 ("wyd. zwarte - problem")
Kontynuacja: PR #409 (`fix(#329)`) — warstwa 1 (render rodzica z PBN) + doraźny
`drop_dbtemplate`. Ten spec robi warstwę 2 „na serio".
Recenzja: adversarialny self-review (Fable) — ustalenia P1–P9 wchłonięte niżej.

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
   Potwierdzone: `compare_dbtemplates.py:322-332`. Fallback z `find_template`
   (linia 335) jest **martwy** — nieosiągalny (obiekt z `get_template()` zawsze
   ma `.template.source`) i dodatkowo `from django.template.loader import
   find_template` rzuca **ImportError** w Django 5.2 (funkcja usunięta).
2. **`opis_bibliograficzny.html` nie musi być w dbtemplates.** Render i tak
   ładuje po nazwie (`util.opis_bibliograficzny()` → `get_template(name)`), a
   samo trzymanie kopii dysku w bazie generuje drift, shadowing i potrzebę
   `drop_dbtemplate`.

## Architektura wyjściowa (jak jest dziś)

- `SzablonDlaOpisuBibliograficznego` (`src/bpp/models/szablondlaopisubibliograficznego.py`):
  - `model` — OneToOne do `ContentType` (jeden z 5 modeli publikacji lub NULL =
    domyślny dla wszystkich),
  - `template` — **FK do `dbtemplates.Template`** (`on_delete=PROTECT`),
  - `render(praca)` i manager `get_for_model()` używają FK **wyłącznie** by
    wyciągnąć `.template.name`; faktyczny render to `get_template(name)`.
- `AbstractModel.opis_bibliograficzny()` (`src/bpp/models/util.py:91`):
  `template_name = get_for_model(self)` (fallback `"opis_bibliograficzny.html"`)
  → `get_template(template_name)` → render.
- **Opis na stronach idzie z denormu, nie z live-renderu.** `opis_bibliograficzny`
  jest `@denormalized` polem (`wydawnictwo_zwarte.py:310` itd.), a
  `cache.Rekord.opis_bibliograficzny_cache` (`models/cache/rekord.py:245`)
  kopiuje gotowy string. Sama zmiana szablonu/skasowanie wiersza **nie**
  odświeża zapisanych stringów — denorm przelicza tylko instancje oznaczone
  jako „dirty" (`DirtyInstance`), realny flush robi async kolejka `denorm`
  (`denorm.tasks.flush_single`, `base.py:739`). Dlatego `drop_dbtemplate`
  jawnie robi `wyczysc_cache_dbtemplate` + `rebuild_instances_of_models` +
  `denorms.flush()` (`drop_dbtemplate.py`).
- Migracja `0295_instaluj_szablony.py` zasiewa do dbtemplates
  `opis_bibliograficzny.html` **oraz** `browse/praca_tabela.html`, ale wpis
  `SzablonDlaOpisu` (model=NULL) tworzy **tylko** dla `opis_bibliograficzny.html`.
  `praca_tabela` nie jest mapowany.
- **Loader dbtemplates nie tworzy wierszy przy renderze** (`loader.py` tylko
  `Template.objects.get(...)`). `DBTEMPLATES_AUTO_POPULATE_CONTENT=True` działa
  **tylko** przy `Template.save()` z pustą treścią (`models.py:63`) i w adminie.
  Żaden sygnał (`post_save`/`pre_delete`/`post_delete` na `Template`) nie
  odtwarza wierszy. Wniosek kluczowy: **skasowany wiersz nie wróci** przy
  renderze — kasowanie w migracji jest trwałe.
- **Cache dbtemplates (Redis).** Loader trzyma treść pod kluczem per-site
  (`bpp.dbtemplates_sync.wyczysc_cache_dbtemplate`), plus zbiór known-names.
  Delete przez model historyczny w migracji **nie odpali** sygnałów czyszczących
  → cache trzeba wyczyścić jawnie (patrz §4).

## Decyzja (zatwierdzona)

**Kierunek A + zakres B + naprawa compare (A) + rebuild denorma 1(a) +
kasowanie bezwarunkowe 2(A).** Dysk staje się jedynym źródłem prawdy dla
`opis_bibliograficzny`; mapowanie per-model przeżywa, ale wskazuje **nazwę
szablonu**, nie wiersz DB. `browse/praca_tabela.html` i reszta dbtemplates
**poza zakresem**.

Konsekwencja edytowalności (świadomie zaakceptowana): opisu **nie** edytuje się
już z admina dbtemplates — zmiana treści opisu = zmiana pliku w kodzie +
wydanie. W zamian znika drift, shadowing i `drop_dbtemplate` dla opisu, a #329
**naprawia się samo** przy podbiciu wydania: migracja kasuje wiersz, czyści
cache i oznacza rekordy jako dirty, a async kolejka `denorm` odświeża opisy w
tle.

## Zakres zmian

### 1. Model `SzablonDlaOpisuBibliograficznego`

- Usuń `template = FK(dbtemplates.Template, PROTECT)`.
- Dodaj `nazwa_szablonu = models.CharField(max_length=255)` — nazwa dla loadera
  Django (loader-relative, np. `"opis_bibliograficzny.html"`), **nie** ścieżka
  pliku. Stąd `nazwa_szablonu`, nie `nazwa_pliku`.
- `get_for_model()` zwraca `.nazwa_szablonu` (fallback w `util.py` bez zmian).
- `get_models_for_template(template)` → `get_models_for_szablon(nazwa_szablonu)`
  (filtr `SzablonDlaOpisu.filter(nazwa_szablonu=…)`).
- `render()` / `__str__` / `get_models_for_this_szablon()` na `nazwa_szablonu`.
- **`clean()`**: waliduje, że `nazwa_szablonu` **rozwiązuje się przez
  `get_template`** (dysk lub — teoretycznie — dbtemplates). Decyzja 2(A):
  walidacja przez `get_template`, NIE „istnieje na dysku" — dzięki temu brak
  sprzeczności z ewentualnym przeżywającym wierszem DB (P5), a literówka i tak
  jest łapana (nazwa, która nie rozwiązuje się nigdzie → błąd). Odpala się z
  admina (`ModelAdmin` → `full_clean`); nie odpala się przy `create`/bakery/
  migracji — i dobrze.

### 2. Helper: źródło szablonu z dysku (bez loadera dbtemplates)

Nowa, izolowana jednostka (np. `src/bpp/util/dbtemplates_disk.py`). Module-level
`Engine` **z domyślnymi loaderami** filesystem + app_directories, zbudowany tak:

```python
from django.template import Engine
_disk_engine = Engine(dirs=list(TEMPLATES_DIRS), app_dirs=True)
# UWAGA: NIE 'loaders=[...] + app_dirs=True' — to ImproperlyConfigured w Dj5.2.
# Domyślne loadery Engine to dokładnie filesystem + app_directories (bez
# dbtemplates), owinięte w cached.Loader. Cached zamraża źródło w procesie —
# dla compare (one-shot) i clean() bez znaczenia.

def disk_template_source(name: str) -> str | None:
    """Źródło szablonu `name` z DYSKU, z pominięciem loadera dbtemplates.
    None, gdy pliku nie ma na dysku."""
```

Reużywane przez §3 (naprawa compare). (`clean()` z §1 celowo używa `get_template`,
nie tego helpera — patrz decyzja 2(A)/P5.)

### 3. Naprawa `compare_dbtemplates` (punkt JEDEN)

`get_filesystem_template_content()` przestaje wołać `get_template()` — używa
`disk_template_source(name)`. Usuń martwą gałąź `find_template` (nieosiągalną i
niekompilowalną w Dj5.2). Teraz porównanie to realne DB-vs-dysk. Repro-test
(red-first): zasiej wiersz dbtemplates różny od pliku na dysku → komenda **musi**
pokazać diff (dziś kłamie „match").

### 4. Migracja (nowy plik — starych nie ruszamy)

W aplikacji `bpp`, jako nowa migracja na aktualnym head (zależność od migracji
`dbtemplates` Django dołoży sam przy `RemoveField`; **nie** ma migracji z #409 —
#409 nie dodał migracji). Kroki:

1. Schema: dodaj `nazwa_szablonu` (CharField, tymczasowo z defaultem/nullable).
2. Data (forward, `RunPython`): dla każdego wiersza `SzablonDlaOpisu` ustaw
   `nazwa_szablonu = template.name`.
3. Schema: usuń FK `template`; ustaw `nazwa_szablonu` NOT NULL. (`RemoveField`
   nie wymaga wcześniejszego zrywania powiązań — `PROTECT` działa tylko przy
   delete `Template`, a delete jest w kroku 4, już po usunięciu FK.)
4. Data (`RunPython`) — **decyzja 2(A) + 1(a)**, kasowanie z guardem
   dysk-existence + przebudowa denorma:
   - Dla każdej nazwy, którą przed krokiem 3 mapował `SzablonDlaOpisu`:
     **GUARD (naprawa regresji, BLOCKER)** — kasuj wiersz dbtemplates **tylko
     gdy `disk_template_source(name) is not None`** (nazwa ma odpowiednik na
     dysku). Dla `opis_bibliograficzny.html` to zawsze prawda → kasowane
     „bezwarunkowo" w sensie decyzji 2(A) (niezależnie od treści). Dla
     hipotetycznego **DB-only custom bez pliku na dysku** — **NIE kasuj**:
     inaczej `nazwa_szablonu` zostaje dyndająca i `get_template()` →
     `TemplateDoesNotExist` → opis wybucha przy każdym flushu denorma i
     live-renderze (wieczne nieskonwergowane rundy denorma). Zostawienie takiego
     wiersza jest w pełni spójne z `clean()` 2(A) (toleruje nazwy rozwiązywalne
     przez dbtemplates).
   - Przed skasowaniem: **zaloguj pełną treść** wiersza do outputu migracji
     (odzyskiwalność; `DBTEMPLATES_USE_REVERSION` dodatkowo trzyma historię).
   - `wyczysc_cache_dbtemplate(name)` (import z `bpp.dbtemplates_sync`) — wyczyść
     cache dbtemplates (P2: delete przez model historyczny nie odpala sygnałów).
     Wołane **synchronicznie**, jak w `drop_dbtemplate` (proste, testowalne bez
     capture-on-commit). Okno wyścigu „żywy worker re-cache'uje starą treść z
     jeszcze-widocznego wiersza" jest bounded TTL cache (≤300 s) — akceptowalne
     (P2 DROBNY); nie komplikujemy `transaction.on_commit`.
   - `rebuild_instances_of_models(<5 modeli publikacji>)` — **oznacz dirty**
     (INSERT do `DirtyInstance`); **NIE** wołaj synchronicznego `denorms.flush()`
     (decyzja 1(a) — flush robi async kolejka `denorm`; migracja szybka,
     nieblokująca). `rebuild_instances_of` robi tylko `ContentType` +
     `values_list("pk")` + `bulk_create(DirtyInstance, ignore_conflicts=True)`
     — działa identycznie na modelach z `apps.get_model` (kanoniczniejszych dla
     migracji) jak i na konkretnych klasach; wybierz `apps.get_model`.
   - `browse/praca_tabela.html` i wszystko niezmapowane — **nietknięte**.
- **`atomic = False`** na migracji (rozważane): oznaczenie dirty setek tysięcy
  rekordów (5 modeli × cała baza) w jednej transakcji wydłuża `migrate` i trzyma
  locki na `denorm_dirtyinstance`. `bulk_create` batchuje, ale transakcja jedna —
  `atomic=False` + jawne bat`on_commit` bezpieczniejsze na dużych bazach.
- **Reverse: migracja nieodwracalna** (`RunPython.noop` / brak reverse na
  `AddField`). „Best-effort odtwórz FK" jest niewykonalne wprost: odwrócenie
  `RemoveField` = `AddField` kolumny NOT NULL bez defaulta na niepustej tabeli →
  błąd DB, zanim data-reverse zdąży wypełnić FK. Deklarujemy nieodwracalność
  (dev odtwarza z baseline/migrate od zera).
- Po merge (raz, przy scalaniu): `make baseline-update`; migracja waliduje się
  wtedy na czystym kontenerze.
- **Testowalność (brak `django-test-migrations` w repo)**: logikę kroku 4
  (guard + log + `wyczysc_cache_dbtemplate` + rebuild) **wyekstrahuj do funkcji**
  w `bpp.dbtemplates_sync` (parametr: `name` + lista modeli do rebuildu), którą
  woła zarówno migracja, jak i `drop_dbtemplate` (§5). Test jedzie na funkcji,
  nie na krokach migracji. Bonus: DRY z `drop_dbtemplate`.

### 5. `drop_dbtemplate` — wymuszone odsprzęgnięcie (rebuild zostaje)

`drop_dbtemplate.py:61-69` i manager `.filter(template=…)` odwołują się do
usuwanego FK → po `RemoveField` to `FieldError`. Odsprzęgnij komendę od
`SzablonDlaOpisu` (przestaje kasować powiązania — FK już nie ma). **Zachowaj**
`wyczysc_cache_dbtemplate` + rebuild denorma + `denorms.flush()` — to połowa
wartości komendy.
- **Targeting rebuildu po odsprzęgnięciu**: komenda dalej wie, które modele
  przebudować, przez **nowe `get_models_for_szablon(name)`** (mapowanie po
  nazwie przeżywa!) — a nie usunięte `get_models_for_template(Template)`. Dla
  nazw niezmapowanych `get_models_for_szablon` zwraca pustą listę (brak zbędnego
  rebuildu); dla wpisu z model=NULL → wszystkie 5 modeli.
- Współdziel funkcję z migracją (§4, „Testowalność"): `drop_dbtemplate`
  różni się od migracji tylko tym, że robi **synchroniczny** `denorms.flush()`
  (komenda deployowa chce natychmiast), a migracja zostawia flush kolejce.
- Zaktualizuj docstring (nieaktualne „PROTECT FKs").

### 6. Pominięci konsumenci FK / metody (P3, P6) — do zakresu

Zmiana modelu/metody wywala kilku konsumentów, których pierwsza wersja speca
nie wymieniała. Wszystkie do poprawy:

- `src/bpp/admin/templates.py:71` — `template_updated` woła
  `get_models_for_template(obj)` przy zapisie **dowolnego** dbtemplate (także
  `praca_tabela`, który zostaje) → dostosuj do nowej sygnatury/nazwy.
- `src/bpp/admin/szablondlaopisubibliograficznego.py:9` — `list_display =
  ["model", "template"]` → `["model", "nazwa_szablonu"]` (inaczej changelist
  wybucha na usuniętym polu). Pole formularza: `nazwa_szablonu` jako wolny
  tekst + `help_text`; walidacja przez `clean()`.
- Testy/fixtures używające `template=` FK — **migracja istniejących, nie tylko
  nowe testy**:
  - `src/fixtures/conftest.py` (fixture `szablony` → `create(template=…)`) —
    sweep grep pokazał **zero konsumentów** tej fixture w testach → **usuń ją**,
    nie migruj.
  - `src/bpp/tests/test_opis_bibliograficzny.py` (`create(template=…)` ×5 oraz
    helper `_sync_opis_template_z_dysku` — **usuń** go; po zmianie render idzie
    z dysku, helper traci rację bytu, P9),
  - `src/bpp/tests/test_admin/test_templateadmin.py` (`create(template=…)`),
  - `src/bpp/tests/test_management_commands_drop_dbtemplate.py` (testuje
    sprzężenie usuwane w §5 — przepisz pod nową, odsprzęgniętą komendę; sprawdź,
    że rebuild denorma zostaje),
  - `src/bpp/tests/test_management_commands_compare_dbtemplates.py` (założenie
    „protected FKs" w docstringu dezaktualizuje się).

### 7. Ścieżka renderu (świadoma decyzja: bez zmian)

`util.opis_bibliograficzny()` **zostaje na `get_template()`**. Po skasowaniu
wiersza dysk i tak wygrywa; to hot-path (~150 szablonów/stronę), więc nie
forsujemy tam disk-only. Disk-only żyje tylko w compare (§3).

## Testy

- **Repro compare** (red-first): wiersz DB ≠ dysk → komenda pokazuje diff.
- **Funkcja z §4 (wyekstrahowana do `dbtemplates_sync`)**: testuj JĄ, nie kroki
  migracji (brak `django-test-migrations`). Przypadki: nazwa z plikiem na dysku
  → wiersz skasowany, treść zalogowana, `wyczysc_cache_dbtemplate` wywołane,
  rekordy oznaczone dirty; **nazwa BEZ pliku na dysku (guard) → wiersz NIE
  skasowany** (kluczowy test regresji BLOCKER-a).
- **Denorm end-to-end** (kluczowe dla P1): rekord ze starym
  `opis_bibliograficzny_cache` → po skasowaniu wiersza + rebuild +
  `denorms.flush()` opis pokazuje rodzica z PBN `object.book` (dziś nie
  pokazywał). Wzorzec istnieje: `test_management_commands_drop_dbtemplate.py:79-89`
  (rebuild + `denorms.flush()` + `refresh_from_db`). Dowodzi, że „naprawia się
  samo" jest prawdą, a nie tylko skasowaniem wiersza.
- **`clean()`**: zła nazwa (nierozwiązywalna) odrzucona; poprawna przechodzi.
- **`get_for_model`**: zwraca `nazwa_szablonu`.
- **Migracja istniejących testów/fixtures** (§6) — muszą dalej przechodzić;
  `_sync_opis_template_z_dysku` usunięty.
- Reuse testów #329 (`test_publication_book.py`, render `object.book`) — teraz
  bez wiersza DB.

## Poza zakresem

- `browse/praca_tabela.html` i inne dbtemplates — zostają.
- Usunięcie aplikacji dbtemplates — nie.
- Logika PBN `object.book` w szablonie — bez zmian (już w #409).
- Weryfikacja/wgranie u klienta (IHiT) i zamknięcie zgłoszenia — osobno
  („skill #2"). Tu dostarczamy kod + migrację, która po podbiciu wydania
  samoczynnie kasuje wiersz, czyści cache i oznacza rekordy dirty; opisy
  odświeży async kolejka `denorm`.

## Ryzyka i pułapki

- **Denorm (P1)**: samo skasowanie wiersza nie odświeża `opis_bibliograficzny_cache`
  — migracja MUSI oznaczyć rekordy dirty (§4 krok 4). Flush async: INSERT do
  `denorm_dirtyinstance` odpala trigger `notify_django_denorm_queue` → daemon
  `denorm_queue` (osobny kontener) dispatchuje flush; na (re)starcie daemon
  dodatkowo kicka backlog — więc dirty z migracji przy zgaszonym daemonie też
  się sflushują po starcie. Dirty nie zostaną na wieki. (Task `denorm.tasks.
  flush_single` z `base.py:739` to LEGACY; realny mechanizm to NOTIFY→
  `flush_via_queue`/`flush_batch` na domyślnej kolejce `celery`.) Admin może
  wymusić `denorm_flush`.
- **BLOCKER-guard (regresja rewizji)**: kasowanie tylko gdy nazwa ma plik na
  dysku — patrz §4 krok 4. Bez tego DB-only custom bez pliku → dyndająca nazwa →
  `TemplateDoesNotExist` → twarda awaria opisu (gorsze niż drift).
- **Multi-hosted**: klucz cache dbtemplates jest per-`Site`, BPP obsługuje wiele
  Site'ów; `wyczysc_cache_dbtemplate` w migracji wyczyści tylko klucz `SITE_ID` —
  kopie pozostałych Site'ów przeżyją do wygaśnięcia TTL (≤300 s). Akceptowalne.
- **Cache dbtemplates (P2)**: delete przez model historyczny nie odpala sygnałów
  → jawne `wyczysc_cache_dbtemplate(name)` w migracji. `DBTEMPLATES_SKIP_UNKNOWN_NAMES=True`
  chroni przed pytaniem DB o nieznane nazwy po restarcie.
- **Auto-populate**: zweryfikowane — loader NIE odtwarza wierszy; kasowanie
  trwałe. Założenie pada tylko, gdyby ktoś włączył odtwarzanie w loaderze.
- **Kustomizacja treści (P4, decyzja 2(A))**: dla nazw z plikiem na dysku
  (m.in. `opis_bibliograficzny.html`) kasujemy **bez względu na treść**.
  Porównanie treści DB↔dysk NIE odróżnia „stary standard" od „przerobiony" (po
  #409 treść DB u KAŻDEGO klienta różni się od dysku samą poprawką #409), więc
  nie próbujemy go używać. Siatka bezpieczeństwa: pełny log treści w migracji +
  historia `DBTEMPLATES_USE_REVERSION`. Kierunek A zakłada brak kustomizacji
  opisu. (Nazwy BEZ pliku na dysku są chronione guardem — nie kasowane.)
- **Engine (P7)**: `Engine(dirs=…, app_dirs=True)` — NIE `loaders=… + app_dirs=True`
  (ImproperlyConfigured w Dj5.2).
- **Nie modyfikować istniejących migracji** — nowy plik (reguła CLAUDE).
- **Baseline (P9)**: `baseline.sql` trzyma stary wiersz `django_template` (opis
  sprzed #409) + wiersz `SzablonDlaOpisu`. Do czasu `make baseline-update`
  (przy scalaniu) testy renderu na świeżej bazie widzą starą treść — stąd
  istniał `_sync_opis_template_z_dysku`, który po tej zmianie **usuwamy**.
