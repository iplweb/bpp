# Plan migracji `import_list_if` na django-liveops 0.4

Status: PLAN (do wykonania). Ten dokument NIE zmienia kodu — opisuje
uporządkowaną, TDD-ową ścieżkę przeniesienia aplikacji `import_list_if`
z legacy stacku `long_running` na `django-liveops` 0.4, wzorowaną 1:1 na
już-scalonym, najbliższym kształtem `import_punktacji_zrodel`.

Worktree: `~/Programowanie/bpp-import-list-if-liveops`
(gałąź `worktree-import-list-if-liveops`, od `dev`).

> **Zmiany po recenzji (execute-with-fixes).** Decyzje architektoniczne
> (RETIRE `ImportOperation`, zostaw `ImportRowMixin`, delta `0005`, cutover)
> — potwierdzone poprawne. Uściślenia po adversarialnej recenzji, każde
> zweryfikowane w kodzie:
> - **PRIMARY reference = `import_punktacji_zrodel`** (nie `import_pracownikow`).
>   Ta apka jest **już na liveops 0.4** (`models.py:9`
>   `ImportPunktacjiZrodel(LiveOperation)`) i to najbliższy 1:1 kształt
>   `import_list_if`: jeden XLS → `index`/`new`/`results`, `run(self,p)`,
>   `on_restart`, `ResultsView(GroupRequiredMixin, ListView)` z `paginate_by=25`
>   i `object=self.parent_object` (`views.py:45-86`), auto-nazwane szablony
>   (`import_punktacji_zrodel_result.html`). `import_pracownikow` pozostaje
>   referencją dla wrappera `hx-headers` i group-gated restart mixinu.
> - **Bramka grupy = 302 redirect_to_login, NIE 403** (braces
>   `AccessMixin.raise_exception=False` domyślnie, `_access.py:27,81` →
>   `redirect_to_login`). Testy asertują side-effect (stan/utworzenie), nie
>   status. (Uwaga: 403 z CSRF to co innego i zostaje.)
> - **Post-Faza-1 nie jest deployowalny** (aplikacja runtime-broken do Fazy 2);
>   Faza 0 kończy RED (merge z Fazą 1 lub `xfail`). Doprecyzowane niżej.
> - **Atomic ↔ cancel:** owinięcie `run()` w `transaction.atomic()` sprawia,
>   że `OperationCancelled` cofa wiersze → test anulowania asertuje
>   `pytest.raises(OperationCancelled)` + **0 wierszy**. `WebProgress.result/error`
>   i tak defer push przez `transaction.on_commit` (`progress.py:263-289`), więc
>   owinięcie jest oficjalnie wspierane. Świadome odejście od wzorca punktacji
>   (ta NIE owija — pisze przyrostowo); owijamy dla parytetu z legacy
>   `task_perform`.
> - **App-level restart URL (`regen/`) — DROP** (precedens punktacji: brak
>   `regen` w urls; „Ponów" idzie na centralny `liveops:restart`).
> - Poprawione line-refy, literał grupy → `bpp.const.GR_WPROWADZANIE_DANYCH`
>   (`const.py:20`), martwy `{% load render_table %}` do usunięcia, zanotowany
>   (już naprawiony na dev, commit 7eed62a2a) latentny bug CSRF.

---

## 1. Streszczenie

`import_list_if` to najprostszy z importerów BPP: jeden upload XLS
(`plik_xls` + `rok`), synchroniczne przetworzenie wierszy (dopasowanie
źródła + zapis `Punktacja_Zrodla.impact_factor` dla danego roku), lista
importów i tabela wyników. Dziś operacja dziedziczy po abstrakcyjnym
`import_common.models.ImportOperation` (`ASGINotificationMixin, Operation`
z `long_running`), a widoki to rodzina `LongRunning*View`.

Migracja: `ImportListIf` ma dziedziczyć **wprost po
`liveops.models.LiveOperation`**, a logika `ImportOperation` (pole
`plik_xls`, `get_xls_import_file`, `validation_form_class` /
`get_validation_form_class`, pętla `perform`) zostaje **wchłonięta do
`ImportListIf`** i przepisana na `run(self, p)`. Abstrakcyjny
`ImportOperation` **znika** (jedyny użytkownik). `ImportRowMixin` z tego
samego pliku **zostaje** — używa go też `import_pracownikow`.

Skala zmiany jest mała (model ~75 linii, 6 widoków, 4 szablony, 1 nowa
migracja delta). Rekomendacja: **cutover model+widoki w jednym kroku**
(bez mostka kompatybilności z §Fazy) — aplikacja jest jednofazowa, nie ma
osobnego etapu „emisja progresu" do zainscenizowania.

Referencje (źródła prawdy, już na 0.4):
- **PRIMARY — `src/import_punktacji_zrodel/`** (najbliższy 1:1 kształt):
  `models.py:9` `ImportPunktacjiZrodel(LiveOperation)`, `run(self,p)`
  (`:29`), `on_restart` (`:52`), `get_details_set`; `views.py:45-86`
  `ResultsView(GroupRequiredMixin, ListView)` z `paginate_by=25` +
  `object=self.parent_object`; `urls.py` (index/new/results/zatwierdz, brak
  routera/detali/regen); `import_punktacji_zrodel_result.html`.
- **SECONDARY — `src/import_pracownikow/`** (dla dwóch wzorców):
  `templates/import_pracownikow/import_pracownikow.html:27` wrapper
  `hx-headers` (CSRF), `views.py:1386` group-gated `_PkOwnerRestartMixin`.
  Reszta (`models.py:72`, `migrations/0010_liveops.py`) — pomocniczo.

---

## 2. Stan obecny (legacy wiring)

### Model — dziedziczenie abstrakcyjne (kluczowy fakt strukturalny)

- `src/import_list_if/models.py:23` — `class ImportListIf(ImportOperation)`;
  dokłada `rok`, `try_names`, `banned_names`, `min_points`,
  `validation_form_class = ImportListRowValidationForm`,
  `import_single_row()`, `on_reset()`, `get_details_set()`.
- `src/import_common/models.py:11` — `class ImportOperation(
  ASGINotificationMixin, Operation)`, `class Meta: abstract = True`.
  Dostarcza: `plik_xls = FileField(upload_to="protected/import_common/")`,
  `get_validation_form_class()`, `get_xls_import_file()` (buduje
  `XLSImportFile`), `perform()` (pętla po wierszach XLS z walidacją formularza
  i `self.send_progress(...)` co 2%), `ignore_bad_rows = False`.
- `src/import_common/models.py:60` — `class ImportRowMixin` (`nr_arkusza`,
  `nr_wiersza`) — **współdzielony**: `import_pracownikow/models.py:720`
  (`ImportPracownikowRow(ImportRowMixin, models.Model)`).
- `src/long_running/models.py:17` — `Operation(NullNotificationMixin,
  models.Model)`: `id` UUID, `owner` FK (bez `related_name`), `created_on`,
  `last_updated_on` (auto_now), `started_on`, `finished_on`,
  `finished_successfully`, `traceback`; `Meta.ordering = ["-last_updated_on"]`;
  `task_perform()` (`long_running/models.py:99`) owija `perform()` w
  `transaction.atomic()` (`:108`).

**POTWIERDZONE (grep repo-wide):** `ImportOperation` importuje/dziedziczy
**wyłącznie** `import_list_if` (`grep -rn ImportOperation src` → tylko
`import_common/models.py` definicja + `import_list_if/models.py:13,23`).
Pozostałe importery na legacy stacku (`import_list_ministerialnych`,
`import_polon`, `importer_autorow_pbn`, `raport_slotow`) używają `long_running`
**bezpośrednio**, nie przez `ImportOperation`. Dlatego retire `ImportOperation`
jest czysty. Natomiast `long_running` jako aplikacja **zostaje** (7+ innych
użytkowników — `grep -rln long_running src`).

**UWAGA (korekta po recenzji):** `import_punktacji_zrodel` **NIE jest** już na
`long_running` — jest **już zmigrowany na liveops 0.4**
(`src/import_punktacji_zrodel/models.py:9` `ImportPunktacjiZrodel(LiveOperation)`;
`urls.py` bez routera/detali; auto-nazwane szablony). To najbliższy 1:1
kształt `import_list_if` i **główna referencja** tego planu (patrz §3, §nota
u góry). `import_pracownikow` to referencja dla wrappera `hx-headers` i
group-gated restart mixinu.

### Widoki (`src/import_list_if/views.py`)

Wszystkie w `BaseImportListIfMixin(GroupRequiredMixin)`,
`group_required = "wprowadzanie danych"`, `model = ImportListIf`:

- `ListaImportowView(LongRunningOperationsView)` — owner-scoped ListView.
- `NowyImportView(CreateLongRunningOperationView)`, `form_class =
  NowyImportForm`.
- `ImportListIfRouterView(LongRunningRouterView)`, `redirect_prefix =
  "import_list_if:import_list_if"` — routuje po stanie na `-details`/`-results`.
- `ImportListIfDetailsView(LongRunningDetailsView)` — strona z paskiem postępu.
- `ImportListIfResultsView(LongRunningResultsView)` — `paginate_by = 25`
  (dziedziczone z `long_running/views.py:89`).
- `RestartImportView(RestartLongRunningOperationView)` — restart, group-gated
  przez mixin.

### URL-e (`src/import_list_if/urls.py`)

`index`, `new`, `importlistif-router` (`<uuid:pk>/`), `importlistif-details`,
`importlistif-results`, `restart` (`<uuid:pk>/regen/`). Wszystkie `<uuid:pk>`.

### Szablony (`src/import_list_if/templates/import_list_if/`)

- `importlistif_list.html` — lista; link `import_list_if:importlistif-router
  object.pk`; **UWAGA: breadcrumb i nagłówek błędnie linkują
  `import_pracownikow:index`** („import list IF") — bug do naprawienia przy
  okazji.
- `importlistif_form.html` — formularz (`CreateView` default:
  `<app>/<model>_form.html`).
- `importlistif_detail.html` — `{% include "long_running/operation_details.html" %}`.
- `importlistifrow_list.html` — tabela wyników; `{% include "pagination.html" %}`
  + iteruje `object_list`; używa `object.plik_xls.name`, `object.pk`
  (kontekst `object` = rodzic!), `{% include "long_running/operation_details.html" %}`.

### Testy

- `tests/test_models.py` — `test_ImportListIF_perform` woła
  `import_list_if.perform()` i sprawdza 4 wiersze + `impact_factor==70.67`;
  `test_ImportListIF_on_reset`, `test_ImportListIF_get_details_set`.
- `tests/test_views.py` — webtest: `index`/`new` GET + klik „pobierz plik
  wzorcowy".

### Odniesienia zewnętrzne (muszą przeżyć)

- `src/django_bpp/templates/top_bar.html:190` → `{% url "import_list_if:index" %}`.
- `src/bpp/templates/browse/uczelnia.html:706` → `link: "/import_list_if/"`.
- `src/django_bpp/urls.py:183` mount `^import_list_if/`.
- `src/django_bpp/urls.py:286` — centralny `path("live/", include("liveops.urls"))`
  już zamontowany.
- `admin.py` pusty (brak rejestracji ModelAdmin — zero pracy).

---

## 3. Docelowy stan (liveops)

### Model `ImportListIf(LiveOperation)`

Pola liveops (`.venv/.../liveops/models.py:27`): `id` UUID, `owner`
(`related_name="+"`), `created_on`, `started_on`, `finished_on`,
`finished_successfully`, `cancel_requested`, `cancelled`, `traceback`,
`result_context`, `language`, `status_text`, `percent`, `log`, `log_seq`,
`current_stage`, `stage_states`; `Meta.abstract`, `ordering = ["-created_on"]`.
Wchłonięte z `ImportOperation`: `plik_xls`, `try_names`/`banned_names`/
`min_points`, `validation_form_class` + `get_validation_form_class()`,
`get_xls_import_file()`, `ignore_bad_rows`.

Kontrakt liveops, który realizujemy:

- `run(self, p)` — logika operacji (dawne `perform()`), progres/anulowanie
  przez obiekt `p` (`liveops.progress.Progress`: `p.percent(int)`,
  `p.track(iterable)`, `p.log(str)`, `p.stage(name)` [ctx-manager],
  `p.check_cancelled()`, `p.result(ctx)`, `p.error(msg)`).
- `on_restart(self)` — hook `RestartView` (kasuje wiersze; dawne `on_reset`).
- `get_absolute_url()` — z bazy: reverse `liveops:live`
  (`op_type=<app>.<model>`, pk). Zastępuje router+details.
- template naming (auto, `liveops/naming.py`): `class_to_snake("ImportListIf")
  = "import_list_if"` → host `import_list_if/import_list_if.html`,
  wynik `import_list_if/import_list_if_result.html`. **ZWERYFIKOWANO**
  uruchamiając `class_to_snake`.

### Widoki (mapowanie legacy → liveops)

| legacy `LongRunning*View` | zamiennik liveops |
|---|---|
| `LongRunningOperationsView` (lista) | zwykły owner-scoped `ListView` (wzór `import_punktacji_zrodel/views.py:14`), własny `template_name`, `order_by("-created_on")` |
| `CreateLongRunningOperationView` | `liveops.views.CreateLiveOperationView` (`liveops/views.py:98`) — ustawia owner, `save()`, `enqueue()`, redirect na `get_absolute_url()`; group-gate przez braces (wzór `import_punktacji_zrodel/views.py:31`) |
| `LongRunningRouterView` | **usunięty** — `get_absolute_url()` → `liveops:live` robi to samo |
| `LongRunningDetailsView` | **usunięty** — strona live (`LiveOperationView`, centralny URL) renderuje host template `import_list_if.html` |
| `LongRunningResultsView` | app-specific owner-scoped `ListView` **near-copy-paste z `import_punktacji_zrodel/views.py:45-86`** — `parent_object` (cached_property, owner→`Http404`), `get_details_set()`, `paginate_by=25`, `object=self.parent_object` w kontekście |
| `RestartLongRunningOperationView` | **usunięty jako app-level URL** (patrz §URL-e docelowe). „Ponów" na stronie live idzie na centralny `liveops:restart` (owner-scoped). Gdyby jednak zostawić app-level restart: `_PkOwnerRestartMixin`-style (braces `GroupRequiredMixin + liveops.views.RestartView`, wzór `import_pracownikow/views.py:1386`) |

Bramka grupy: `liveops.BaseLiveOperationMixin` gejtuje tylko gdy
`LIVEOPS["REQUIRED_GROUP"]` ustawione — w BPP `LIVEOPS`
(`settings/base.py:1049`) tego **nie ma**, więc dokładamy braces
`GroupRequiredMixin` (jak `import_pracownikow`) na Create/List/Results/Restart,
inaczej dowolny zalogowany user odpaliłby import.

### URL-e docelowe

`index` (`""`), `new` (`new/`), `importlistif-results`
(`<uuid:pk>/rezultaty/`). **Usuwamy** `importlistif-router`,
`importlistif-details` **oraz `restart` (`<uuid:pk>/regen/`)**. Strona live
idzie przez centralny `liveops:live` (`live/<op_type>/<uuid:pk>/`).

**Decyzja o app-level restart (`regen/`) — DROP.** Po usunięciu include
`operation_details.html` nic już nie linkuje `<uuid:pk>/regen/`. Przycisk
„Ponów" na stronie live POST-uje na centralny `liveops:restart`
(owner-scoped, ale **NIE** group-gated — liveops gejtuje tylko przy
`REQUIRED_GROUP`, którego BPP nie ustawia). Ekspozycja ~zerowa: user bez
grupy „wprowadzanie danych" i tak nie stworzy importu (create jest
group-gated), więc nie ma własnej operacji do restartu. To dokładnie
precedens `import_punktacji_zrodel` (jego `urls.py` nie ma `regen`) i
`import_pracownikow`. Jeśli w trakcie realizacji okaże się, że potrzebny jest
jawny app-level restart (np. z listy importów), przywróć go jako
`_PkOwnerRestartMixin` (group-gated) — ale domyślnie NIE dodajemy.

### Szablony docelowe

- **Nowy** `import_list_if/import_list_if.html` (host live) — `extends
  base.html`, `{% load static liveops %}`, wrapper `hx-headers` z CSRF (patrz
  §Gotchas) wokół `{% live_operation object %}`, plus 3 skrypty (`htmx.min.js`,
  `channels_broadcast/js/notifications.js`, `liveops/liveops.js`) — kopia
  `import_pracownikow/import_pracownikow.html`.
- **Nowy** `import_list_if/import_list_if_result.html` (fragment wyniku) —
  panel „import zakończony" + link do `importlistif-results`, kontekst z
  `result_context` (np. `total`, `zintegrowano`, ...). Wzór:
  `import_punktacji_zrodel/import_punktacji_zrodel_result.html` (near-copy-paste).
- `importlistif_list.html` — link zamień na `object.get_absolute_url`
  (liveops:live); **napraw** breadcrumb `import_pracownikow:index` →
  `import_list_if:index`; usuń auto-redirect JS jak przeszkadza.
- `importlistifrow_list.html` — usuń `{% include "long_running/
  operation_details.html" %}`; reszta działa, o ile results view poda
  `object=parent_object` i `paginate_by` (patrz §Gotchas).
- **Usuń** `importlistif_detail.html` (zastąpiony host template).
- `importlistif_form.html` — bez zmian (`CreateView` nadal go szuka jako
  `import_list_if/importlistif_form.html`).

---

## 4. Decyzja o `ImportOperation`: RETIRE (uzasadnienie)

**Decyzja: skasować abstrakcyjny `ImportOperation`, a jego zawartość
wchłonąć do `ImportListIf(LiveOperation)`.** NIE migrujemy bazy
abstrakcyjnej na `LiveOperation`.

Uzasadnienie:

1. **Jedyny użytkownik.** `grep -rn ImportOperation src` = definicja +
   `import_list_if`. Utrzymywanie warstwy abstrakcji dla jednej podklasy to
   martwy koszt; po migracji `import_pracownikow` (który nigdy nie dziedziczył
   po `ImportOperation`) baza ta straciła rację bytu.
2. **`LiveOperation` już jest bazą abstrakcyjną.** Wstawienie pośredniego
   `ImportOperation(LiveOperation)` dodałoby drugi poziom MRO bez żadnego
   drugiego konsumenta — antywzorzec „abstrakcja spekulacyjna".
3. **Zawartość jest trywialna do inline'u** (~30 linii: `plik_xls`,
   `get_xls_import_file`, `get_validation_form_class`, pętla walidacji).
   `import_pracownikow` sam trzyma swój `plik_xls` i logikę — spójność
   ze wzorcem referencyjnym.
4. **`ImportRowMixin` NIE jest częścią tej decyzji** — to osobna klasa w tym
   samym pliku, współdzielona z `import_pracownikow/models.py:720`. **Zostaje
   w `import_common/models.py`.** Kasujemy z tego pliku **tylko** klasę
   `ImportOperation` oraz nieużywane po niej importy (`ceil`,
   `XLSParseError`, `XLSImportFile`, `Operation`, `ASGINotificationMixin`) —
   o ile `ImportRowMixin` ich nie potrzebuje (nie potrzebuje).

Konsekwencja czyszcząca: po przeniesieniu `import_common/models.py` zostaje
praktycznie z samym `ImportRowMixin`. To OK — plik pozostaje (import ścieżki
`from import_common.models import ImportRowMixin` używany przez
`import_pracownikow`).

---

## 5. Migracja modelu (nowa migracja delta)

Nowa migracja `src/import_list_if/migrations/0005_liveops.py`, mirror
`import_pracownikow/migrations/0010_liveops.py`, **bez** `stan` i **bez**
`RunPython` (import_list_if nie ma pól `performed`/`integrated` do
przemapowania).

- `dependencies`: `("import_list_if", "0004_alter_importlistif_plik_xls")`
  + `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`.
- `operations`:
  - `AlterModelOptions("importlistif", options={"ordering": ["-created_on"]})`
    (dziś `options={}` po `0002`; nowa baza wnosi `-created_on`).
  - `RemoveField("importlistif", "last_updated_on")`.
  - `AddField` ×10 (identyczne definicje jak w 0010): `cancel_requested`
    `BooleanField(default=False)`, `cancelled` `BooleanField(default=False)`,
    `current_stage` `IntegerField(default=-1)`, `language`
    `CharField(blank=True, default="", max_length=20)`, `log`
    `JSONField(default=list)`, `log_seq` `PositiveIntegerField(default=0)`,
    `percent` `PositiveSmallIntegerField(default=0)`, `result_context`
    `JSONField(blank=True, null=True)`, `stage_states` `JSONField(default=dict)`,
    `status_text` `CharField(blank=True, default="", max_length=255)`.
  - `AlterField("importlistif", "owner", ForeignKey(on_delete=CASCADE,
    related_name="+", to=AUTH_USER_MODEL))`.

Pola niezmienne (już kolumny w tabeli po spłaszczeniu dziedziczenia): `id`,
`created_on`, `started_on`, `finished_on`, `finished_successfully`,
`traceback`, `plik_xls`, `rok` — **redeklaracja z bazy `LiveOperation` nie
generuje operacji**. Zmiana `bases` w `CreateModel` NIE jest emitowana przez
`makemigrations` (bases nie wpływają na schemat) — nie potrzeba `AlterModelBases`.

### PK / FK / related_name

- **PK zostaje UUID** — `LiveOperation.id = UUIDField(default=uuid4)` jest
  identyczne z obecnym `Operation.id`; URL-e `<uuid:pk>` bez zmian.
- `ImportListIfRow.parent` (FK do `ImportListIf`, `models.py:68`) —
  **bez zmian** (nadal wskazuje ten sam model, `on_delete=CASCADE`,
  `related_name` domyślny `importlistifrow_set`). Brak migracji na `Row`.
- `owner` → `related_name="+"` (jak liveops) — pojedyncza `AlterField`.

### Data concerns

- Brak migracji danych. Istniejące ukończone importy: `finished_on` +
  `finished_successfully` → `LiveOperation.get_state()` daje `FINISHED_OK`
  poprawnie; `cancelled=False` (default). Utrata `last_updated_on` (sortowanie)
  nieistotna — sortujemy po `-created_on`.
- **Baseline:** migracja zmienia schemat → przy scalaniu do `dev` trzeba
  `make baseline-update` (delta). **NIE** robić w tym worktree/branchu
  (reguła: baseline raz, przy merge; równoległe branche = nierozwiązywalny
  konflikt na jednym pliku). Odnotować w PR.
- `makemigrations --check --dry-run` musi być czysty po napisaniu migracji
  (walidacja zgodności model↔migracja).

---

## 6. Fazy (uporządkowane, każda niezależnie zielona, TDD)

Rekomendacja: **cutover w jednej gałęzi, ale w 3 commitach-fazach**. Bez
mostka kompatybilności — aplikacja jednofazowa, split emisji nic nie daje.
(Mostek — patrz §Gotchas — trzymamy jako awaryjny fallback, gdyby ktoś chciał
pośredni zielony stan między modelem a widokami; wtedy MUSI to być lokalny
`Progress` forwardujący do legacy `send_progress`/`send_notification` z
`check_cancelled` = no-op, NIGDY `TextProgress` na legacy modelu.)

### Faza 0 — testy charakteryzujące (kończy RED — commituj RAZEM z Fazą 1)

**WAŻNE:** Faza 0 z definicji kończy się **czerwono** (produkcja jeszcze nie
ma `run()`). Nie jest to „niezależnie zielona" faza — albo **scal jej commit
z Fazą 1** (jeden zielony commit model+testy), albo oznacz nowe testy
`@pytest.mark.xfail(reason="run() dopiero w Fazie 1", strict=True)` i zdejmij
xfail w Fazie 1. Nie zostawiaj czerwonego commitu jako osobnego kroku.

- Przepisz `test_models.py`: zamiast `import_list_if.perform()` wołaj
  `import_list_if.run(p)` z `liveops.testing.MockProgress(import_list_if)`
  (`.venv/.../liveops/testing.py:43` klasa, `__init__` z `cancel_after` na `:46`;
  docstring `test_my_import_run` na :27). Asercje bez zmian (4 wiersze,
  `impact_factor == Decimal("70.67")`). `on_reset`→`on_restart`,
  `get_details_set` — analogicznie.
- Test anulowania **musi być zgodny z decyzją o atomicity** (patrz §9 ryzyko 1):
  jeśli `run()` owinięte w `transaction.atomic()`, `p.check_cancelled()` rzuca
  `liveops.progress.OperationCancelled`, które **cofa** zapisane wiersze →
  asercja: `with pytest.raises(OperationCancelled): op.run(MockProgress(op,
  cancel_after=1))` **oraz** `op.importlistifrow_set.count() == 0`. (Bez atomic
  byłby 1 zapisany wiersz — nie tego chcemy.) `MockProgress.check_cancelled`
  rzuca `OperationCancelled` po `cancel_after` wywołaniach.

### Faza 1 — model + migracja (zielona po sobie)

1. `import_list_if/models.py`: `class ImportListIf(LiveOperation)`; wchłoń
   `plik_xls`, `get_xls_import_file`, `get_validation_form_class`,
   `ignore_bad_rows`; przepisz `perform()` → `run(self, p)` (owinięte w
   `transaction.atomic()` dla parytetu z legacy `task_perform` — patrz §9):
   ```
   def run(self, p):
       from django.db import transaction
       with transaction.atomic():
           x = self.get_xls_import_file()
           total = x.count()
           form_class = self.get_validation_form_class()
           for no, elem in enumerate(x.data()):
               p.check_cancelled()  # OperationCancelled → rollback wierszy
               cleaned = None
               if form_class:
                   form = form_class(elem)
                   if not form.is_valid():
                       if self.ignore_bad_rows:
                           continue
                       raise XLSParseError(
                           elem, form, "wstępna weryfikacja danych"
                       )
                   cleaned = form.cleaned_data
               self.import_single_row(xls_data=elem, cleaned_data=cleaned)
               if total:
                   p.percent(int((no + 1) * 100 / total))
       p.result({"total": total})  # WebProgress.result deferuje push on_commit
   ```
   (importy przenieś do `import_list_if/models.py`: `ceil` niepotrzebny;
   `XLSParseError` z `import_common.exceptions`, `XLSImportFile` z
   `import_common.util`.) `on_reset`→`on_restart` (kasuje
   `get_details_set().delete()`). `p.result(...)` **poza** blokiem atomic
   (i tak defer przez `on_commit` — `progress.py:263-289`).
2. `import_common/models.py`: usuń `class ImportOperation` + osierocone
   importy; **zostaw `ImportRowMixin`**.
3. Napisz `0005_liveops.py` (§5).
4. Zielone: `uv run pytest src/import_list_if/tests/test_models.py`
   + `uv run python src/manage.py makemigrations --check --dry-run`
   (brak driftu).

> **Post-Faza-1 NIE jest deployowalny.** Testy modelu są zielone, ale
> aplikacja jest runtime-broken do końca Fazy 2: stare `views.py` nadal
> importuje `LongRunning*View` i woła metody, których model już nie ma
> (`RouterView.get` → `object.get_url()`/`get_state()` int-vs-str;
> create → `task_perform` `AttributeError`; restart → `mark_reset`
> `AttributeError`). To OK w obrębie jednej gałęzi (cutover), ale **nie
> mergować/deployować między Fazą 1 a 2** — dopiero po Fazie 2 apka działa.

### Faza 2 — widoki + URL-e + szablony (domyka cutover — dopiero tu apka działa)

1. `views.py`: przepisz na liveops (tabela §3). `BaseImportListIfMixin`
   (braces `GroupRequiredMixin`, `group_required = GR_WPROWADZANIE_DANYCH`
   z `bpp.const` — **nie literał** `"wprowadzanie danych"`) zostaje jako miks
   na Create/List/Results. Restart app-level: **nie dodajemy** (§3).
2. `urls.py`: usuń `importlistif-router`, `importlistif-details` **oraz
   `restart`**; zostaw `index`, `new`, `importlistif-results`.
3. Szablony: nowy `import_list_if.html` (host, hx-headers + live_operation),
   nowy `import_list_if_result.html`, napraw `importlistif_list.html`
   (link + breadcrumb), oczyść `importlistifrow_list.html`, skasuj
   `importlistif_detail.html`. **Usuń martwy `{% load render_table from
   django_tables2 %}`** z każdego szablonu, który go trzyma bez użycia
   (`importlistif_list.html`, `importlistif_form.html`,
   `importlistifrow_list.html`, `importlistif_detail.html` — ten ostatni i tak
   kasujemy).
4. `test_views.py`: istniejące GET-y `index`/`new` przechodzą; dodaj:
   - create POST → redirect na `liveops:live` (RUNNER=eager w
     `settings/test.py` wykona import synchronicznie); wiersze zapisane;
   - results view renderuje wiersze (owner-scoped; cudzy import → `Http404`);
   - **group-gating (create):** zalogowany user **bez** grupy
     „wprowadzanie danych" → **302 redirect_to_login** (braces
     `raise_exception=False` domyślnie — NIE 403) **i brak side-effectu**
     (import nie powstał). Asertuj po side-effekcie + `status_code == 302` /
     `"/login" in resp.url`, wzorem `import_pracownikow/tests/test_auth_gate.py`
     (który asertuje przez niezmieniony stan operacji). Superuser i user w
     grupie → przechodzą.
5. Zielone: `uv run pytest src/import_list_if/`.

### Faza 3 — sprzątanie + newsfragment

1. `grep -rn "ImportOperation\|long_running" src/import_list_if src/import_common`
   = czysto (poza `ImportRowMixin`). Potwierdź, że `long_running` **nie** jest
   usuwany globalnie (dalej używany przez 7+ apek).
2. Newsfragment `src/bpp/newsfragments/<slug>.feature.rst` (PL, zwięźle) —
   np. „Import list IF przeniesiony na django-liveops (live progress przez
   WebSocket)".
3. Zielone: `make tests-without-playwright` (albo pełne `make tests`).

---

## 7. Zachowanie do utrzymania (+ testy strażnicze)

| Zachowanie | Strażnik |
|---|---|
| Dopasowanie źródła + zapis `Punktacja_Zrodla.impact_factor` per rok; flaga `zintegrowano` | `test_models.py::test_ImportListIF_run` (dawne `_perform`) |
| Reset kasuje wiersze podglądu | `test_ImportListIF_on_restart` (dawne `_on_reset`) |
| `get_details_set()` (select_related zrodlo) | `test_ImportListIF_get_details_set` |
| Anulowanie przerywa pętlę **i cofa wiersze** (atomic) | nowy test `MockProgress(cancel_after=1)` → `pytest.raises(OperationCancelled)` + `count()==0` |
| Owner-scoping list/results (brak wycieku cudzych importów) | nowy test widoku (dwóch userów; cudzy → `Http404`) |
| Group-gating create (`GR_WPROWADZANIE_DANYCH`) | nowy test widoku: user bez grupy → **302 redirect_to_login + brak side-effectu** (NIE 403); superuser/w-grupie → OK |
| Linki „pobierz plik wzorcowy" na index/new | istniejące `test_views.py` (zostają) |
| Paginacja tabeli wyników + kontekst `object`=rodzic | test renderu `importlistif-results` |
| Redirect po create na stronę live | test create POST → `liveops:live` |

---

## 8. Strategia testów

- **Jednostkowe modelu:** `liveops.testing.MockProgress` (nagrywa
  `percent`/`log`/`result`, wspiera `cancel_after`) — bez Redis/WebSocket.
  `@pytest.mark.django_db`, `baker.make`/istniejące fixtury (`zrodlo`, `rok`,
  `admin_user`), plik `testdata1.xlsx`.
- **Widoki:** webtest (`admin_app`) jak dziś + `django_webtest`/`client`
  dla POST-ów. `settings/test.py:73` ma `LIVEOPS = {**LIVEOPS,
  "RUNNER": "eager"}` — create/restart uruchamiają `run()` synchronicznie,
  więc po POST można od razu asertować wiersze i stan `FINISHED_OK`.
- **Bramka grupy:** utwórz usera w grupie `GR_WPROWADZANIE_DANYCH` vs bez;
  user bez grupy → **302 redirect_to_login** (braces `raise_exception=False`),
  asertuj też brak side-effectu. Superuser exempt (semantyka braces).
- **Lokalnie (reguła projektu):** odpal `uv run pytest src/import_list_if/`
  po każdej fazie; przed PR `make tests-without-playwright`. Wymaga Dockera
  (testcontainers PG/Redis) — jeśli brak, powiedz wprost.
- **`makemigrations --check`** jako część CI/lokalnej walidacji Fazy 1.

---

## 9. Ryzyka i pytania otwarte

**Top 3 ryzyka:**

1. **Brak zewnętrznej transakcji wokół `run()`.** Legacy `task_perform`
   (`long_running/models.py:99`) owijał `perform()` w `transaction.atomic()`
   (`:108`); `liveops.runner._task_run` **nie owija** `operation.run(progress)`
   (`runner.py:143`). Częściowy import przy błędzie w połowie pliku zostawiłby
   część wierszy zapisanych + stan `FINISHED_ERROR`. **Mitygacja
   (rekomendowana): owinąć ciało `run()` w `transaction.atomic()`** — przywraca
   dawne all-or-nothing. Jest to **oficjalnie wspierane** przez liveops:
   `WebProgress.result`/`error` deferują push terminalny przez
   `transaction.on_commit` (`progress.py:263-289`, konkretnie `:302`/`:332`),
   więc push nie odpala się dopóki transakcja się nie zacommituje.
   **Świadome odejście od wzorca PRIMARY:** `import_punktacji_zrodel` **NIE**
   owija (pisze wiersze przyrostowo w `analyze_jcr_file`); my owijamy dla
   parytetu z legacy `task_perform` (dawne zachowanie import_list_if było
   atomowe). Konsekwencja dla testu anulowania: `OperationCancelled` cofa
   wiersze → asercja `raises + count()==0` (§Faza 0). Uwaga na `enqueue()`
   gotcha §Gotchas (poza `run()`).
2. **Nazwy szablonów.** Host MUSI być `import_list_if/import_list_if.html`,
   wynik `import_list_if/import_list_if_result.html` (auto z `class_to_snake`).
   Stary `importlistif_detail.html` NIE jest już rozpoznawany przez liveops —
   łatwo zostawić martwy plik i dostać goły `liveops/operation.html`.
3. **CSRF + `hx-headers`.** Bez wrappera `<div hx-headers=...>` przyciski
   Anuluj/Ponów dają 403 (BPP `CSRF_COOKIE_HTTPONLY=True`,
   `settings/base.py:1596`) — patrz §Gotchas.

**Pozostałe ryzyka:** results view bez `paginate_by`/`object` łamie
`importlistifrow_list.html` (§Gotchas); baseline drift jeśli ktoś odświeży
baseline w tym branchu; `run()` importuje `XLSParseError`/`XLSImportFile` —
pilnować, by przeniesione importy nie zostawiły cyklu.

**Pytania otwarte:**

- Czy `import_list_if` potrzebuje własnego `result_context` bogatszego niż
  `{"total": ...}` (liczba zintegrowanych, niedopasowanych źródeł)? Wpływa na
  treść `import_list_if_result.html`. Domyślnie: minimalny panel + link.
- Czy zachować auto-redirect z pustej listy na `./new`
  (`importlistif_list.html:36`)? Można zostawić.
- Restart: app-level `regen/` **zdjęty** (§3) — „Ponów" idzie na centralny
  `liveops:restart`, który `RestartView.post` robi pełny reset stanu sam
  (nie potrzeba `reset_liveops_state` jak w wielofazowym
  `import_pracownikow/models.py:326`). Otwarte tylko: czy UX wymaga jawnego
  restartu z listy importów (wtedy przywróć group-gated `_PkOwnerRestartMixin`).

---

## 10. Czego NIE robić

- **NIE** modyfikować istniejących migracji `import_list_if/migrations/
  0001..0004` — tylko dodać `0005_liveops.py`.
- **NIE** kasować `ImportRowMixin` z `import_common/models.py` (używa
  `import_pracownikow`).
- **NIE** usuwać aplikacji `long_running` ani jej z `INSTALLED_APPS`
  (`settings/base.py:407`) — 7+ innych importerów na niej stoi.
- **NIE** odświeżać baseline (`make baseline-update`/`rebuild-baseline`) w tym
  branchu — robi się to raz, przy scalaniu do `dev`.
- **NIE** montować nowych URL-i live w `import_list_if/urls.py` — centralny
  router `liveops:live` już jest (`django_bpp/urls.py:286`).
- **NIE** używać `TextProgress` na legacy modelu (brak pola `cancel_requested`
  → `check_cancelled().refresh_from_db` wywali) — dotyczy tylko awaryjnego
  mostka §Gotchas.
- **NIE** dodawać `LIVEOPS["REQUIRED_GROUP"]` globalnie zamiast braces
  `GroupRequiredMixin` — reszta liveopsów w BPP polega na braku tej bramki.
- **NIE** wołać `enqueue()` wewnątrz `transaction.atomic()` bez
  `transaction.on_commit` (§Gotchas).

---

## Załącznik — wbudowane gotchas (żeby wykonawca nie odkrywał od nowa)

- **CSRF (`CSRF_COOKIE_HTTPONLY=True`, `settings/base.py:1596`):** host
  template MUSI owinąć `{% live_operation object %}` w
  `<div hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>` — inaczej POST
  Anuluj/Ponów = **403** (to prawdziwe 403 z CSRF, nie mylić z 302 bramki
  grupy). Wzór: `import_pracownikow/import_pracownikow.html:27`. **NIE**
  kopiować z `import_punktacji_zrodel/import_punktacji_zrodel.html:21` —
  ten host template **nie miał** wrappera (latentny bug CSRF; analogicznie
  `deduplikator_zrodel`). **Oba naprawione na `dev` (commit 7eed62a2a)** —
  po rebase na `dev` można wzorować się i na punktacji, ale weź wrapper
  świadomie.
- **Results view:** `importlistifrow_list.html` używa `object.plik_xls.name`/
  `object.pk` i `{% include "pagination.html" %}` → results view MUSI ustawić
  `paginate_by = 25` i podać `object=self.parent_object` w kontekście (oprócz
  `object_list`). Near-copy-paste z `import_punktacji_zrodel/views.py:45-86`
  (`ResultsView.get_context_data` woła `super().get_context_data(
  object=self.parent_object, ...)`).
- **Bramka grupy = 302, nie 403.** Braces `GroupRequiredMixin`
  (`AccessMixin.raise_exception=False`, `_access.py:27,81`) przy braku grupy
  robi `redirect_to_login` → **302**, nie 403. Testy asertują przez
  side-effect (op nie powstał/nie zresetowany), nie po statusie. Chcieć 403
  = ustawić `raise_exception=True` (zmiana zachowania — NIE rekomendowane).
- **Restart NIE jest group-gated** (świadomie). App-level `regen/` zdjęty;
  centralny `liveops:restart` jest owner-scoped, ale liveops gejtuje grupą
  tylko przy `REQUIRED_GROUP` (BPP nie ustawia). Ekspozycja ~zero: create jest
  group-gated, więc user bez grupy nie ma własnego importu do restartu.
  Precedens `import_punktacji_zrodel`/`import_pracownikow`.
- **`enqueue()` → celery `.delay()` bez `on_commit`.** Bezpośredni enqueue
  w create jest OK (brak `ATOMIC_REQUESTS`). Enqueue wewnątrz
  `@transaction.atomic` wymaga `transaction.on_commit(...)`.
- **Nazwy szablonów:** `class_to_snake("ImportListIf") = "import_list_if"`
  (ZWERYFIKOWANO) → host `import_list_if/import_list_if.html`, wynik
  `..._result.html`. Zgadza się z app_label — brak potrzeby jawnych
  `host_template_name`/`result_template_name`.
- **Mostek Fazy 1 (tylko jeśli split emisji ≠ cutover):** lokalny `Progress`
  FORWARDUJĄCY do legacy `send_progress`/`send_notification`, z `check_cancelled`
  nadpisanym na no-op (legacy `Operation` nie ma `cancel_requested` →
  `refresh_from_db` by się wywalił). NIGDY `TextProgress` na legacy modelu.
  Dla `import_list_if` rekomendacja: **pomiń mostek**, rób cutover.
- **Istniejące migracje nietykalne; nie odświeżać baseline (odnotować przy
  merge); newsfragment wymagany.**
