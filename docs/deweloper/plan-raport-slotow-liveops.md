# Plan migracji `raport_slotow` (RaportSlotowUczelnia) na django-liveops 0.4

Dokument planistyczny. NIE zawiera zmian w kodzie — opisuje docelowy stan,
mapowania, fazy TDD, ryzyka i to, czego NIE robić. Referencja (jedyny
zmigrowany, na 0.4): `src/import_pracownikow/` — ale to IMPORTER, nie Report,
więc specyfikę „Report" trzeba wyprowadzić z API liveops + `long_running.models.Report`.

Ścieżka dokumentu:
- `/Users/mpasternak/Programowanie/bpp-raport-slotow-liveops/docs/deweloper/plan-raport-slotow-liveops.md`
- file:///Volumes/mpasternak/Programowanie/bpp-raport-slotow-liveops/docs/deweloper/plan-raport-slotow-liveops.md

---

## 0. Zmiany po recenzji adwersarialnej (2026-07-15)

Werdykt: „execute-with-fixes". Wszystkie file:line refs pierwotnego planu
zweryfikowane jako poprawne; poniższe braki uzupełnione (każdy potwierdzony
w kodzie przed edycją):

- **HIGH — pominięta powierzchnia API v1** (nowy §4.5 + praca w Fazie 2 + szerszy
  grep w Fazie 4 + ryzyko §11.9). `src/api_v1/serializers/raport_slotow_uczelnia.py`
  wymienia `last_updated_on` (:25,38) i enqueue'uje przez
  `perform_generic_long_running_task`→`task_perform()` (:66-76) — OBA pękają
  natychmiast po migracji modelu. `create()` jest `@transaction.atomic`, więc to
  REALNY (nie hipotetyczny) przypadek enqueue-inside-atomic z §7.4.
- **MEDIUM — utracony guard „restart tylko gdy skończone"** (§8.4 + regen w
  Fazie 3 + gotcha §7.9). Legacy resetuje tylko gdy `finished_on is not None`
  (`long_running/views.py:125`); liveops `RestartView` resetuje BEZWARUNKOWO
  (`liveops/views.py:175`). Pod celery regen w połowie runu = `on_restart`
  kasuje wiersze piszące + drugi run. Decyzja: dodać guard (patrz §8.4).
- **LOW — kolizja szablonów tylko HOST** (§7.5, §10 zmiękczone). `result` auto-name
  ma sufiks `_result` i z niczym nie koliduje — `result_template_name` to „plik do
  utworzenia", nie kwestia kolizji. `host_template_name` faktycznie koliduje.
- **LOW — ścieżka API create NIE ustawia `uczelnia`** (§8.1 rozszerzone). To DRUGA
  ścieżka zapisu (obok `form_valid`); świadoma decyzja: zostawić bez scope'u jak
  dziś (test API to dokumentuje) czy dołożyć `uczelnia_dla_odczytu`.
- **COSMETIC — zmiana `ordering`** (§5) `-last_updated_on`→`-created_on`: regenerowany
  raport NIE wskakuje już na górę listy (zmiana UX), nie tylko sucha `AlterModelOptions`.

---

## 1. Streszczenie

`RaportSlotowUczelnia` (`src/raport_slotow/models/uczelnia.py:31`) to jedyna
long-running operacja w aplikacji `raport_slotow`. Dziedziczy po
`long_running.models.Report` (via `ASGINotificationMixin`), który dokłada
`create_report`/`task_create_report` nad `Operation.perform`. Widoki
(`src/raport_slotow/views/uczelnia.py`) używają całej rodziny
`LongRunning*View` (lista / router / details / results / restart) oraz taska
`perform_generic_long_running_task`.

Celem jest przeniesienie tej operacji na `liveops.models.LiveOperation`
(`run(self, p)` + `WebProgress` po WebSocket/HTMX), tak jak zrobiono to dla
`ImportPracownikow`. W odróżnieniu od importera to jest **Report**
(generuje wyjście — wiersze `RaportSlotowUczelniaWiersz` w bazie), więc:
- nie ma dry-run/commit, jest jeden przebieg generujący wiersze;
- „wynik" to strona z wygenerowaną tabelą (`-results`), nie panel podsumowania;
- postęp = pasek `p.percent(...)` w pętli po kombinacjach autor/dyscyplina/jednostka.

**Kluczowe ułatwienie:** model już MA pk typu `UUIDField` (dziedziczony z
`Operation`, `src/long_running/models.py:20`), a URL-e już są `<uuid:pk>`
(`src/raport_slotow/urls.py:45-63`) — **żadna migracja pk nie jest potrzebna**.

**Kluczowa pułapka nazewnictwa:** `class_to_snake("RaportSlotowUczelnia")` =
`raport_slotow_uczelnia`, więc auto host-template = `raport_slotow/raport_slotow_uczelnia.html`
— a to **istniejący plik szablonu wyników** (`src/raport_slotow/views/uczelnia.py:98`).
Kolizja. Trzeba jawnie ustawić `host_template_name` (i `result_template_name`),
NIE polegać na auto-nazwie. Szczegóły w §4 i §10.

---

## 2. Stan obecny (legacy wiring, Report specifics, uczelnia scoping)

### 2.1 Model — `src/raport_slotow/models/uczelnia.py`

- `class RaportSlotowUczelnia(ASGINotificationMixin, Report)` (:31). Pola
  domenowe: `od_roku`, `do_roku`, `akcja`, `slot`, `minimalny_pk`,
  `dziel_na_jednostki_i_wydzialy`, `pokazuj_zerowych` oraz **`uczelnia`**
  (`FK bpp.Uczelnia, null=True, blank=True`, :55-57) — to nośnik scoping'u
  per-uczelnia zapisany przy tworzeniu.
- `clean()` (:76) — walidacja `od_roku<=do_roku` + reguły `akcja/slot`.
- `on_reset()` (:73) — kasuje `raportslotowuczelniawiersz_set` (hook legacy
  `Operation.mark_reset`, `src/long_running/models.py:72-80`).
- **`create_report()`** (:108) — rdzeń generacji. Buduje `kombinacje` z
  `Cache_Punktacja_Autora_Query`, **zawężone `if self.uczelnia_id is not None:
  kombinacje.filter(jednostka__uczelnia_id=self.uczelnia_id)`** (:122-123),
  pętla po kombinacjach woła `zbieraj_sloty(..., uczelnia_id=self.uczelnia_id)`
  (:134-144), tworzy wiersze (:155), a postęp raportuje przez
  `self.send_progress(n*100.0/total)` co 10 iteracji (:164-165). Gałąź
  `pokazuj_zerowych` (:167) woła `autorzy_zerowi(..., uczelnia=self.uczelnia)`.
- `get_details_set()` (:230) — queryset wierszy z `select_related` do tabeli
  wyników.
- Dziedziczone z `Report`/`Operation`: `perform()->create_report()`
  (`src/long_running/models.py:164`), `task_create_report`,
  `mark_started/mark_finished_okay/...`, `get_state()`, `get_url(suffix)`,
  `get_absolute_url()->get_url("router")`.

### 2.2 Base classes — `src/long_running/models.py`

- `Operation` (:17): `id=UUIDField pk`, `owner=FK(AUTH_USER_MODEL, CASCADE)`
  (domyślny related_name), `created_on`, **`last_updated_on` (auto_now)**,
  `started_on`, `finished_on`, `finished_successfully`, `traceback`. Meta
  `ordering=["-last_updated_on"]`.
- `task_perform` (:99) owija `perform()` w **`with transaction.atomic()`**
  (:108) — cały `create_report` jest transakcyjny (all-or-nothing).
- `Report` (:163): `perform=create_report`.
- `ASGINotificationMixin` (`src/long_running/notification_mixins.py`):
  `send_notification`, `send_progress(percent)`, `send_processing_finished`
  — pchają po `channels_broadcast` na kanał `str(self.pk)`. To warstwa
  live-progress legacy, którą liveops zastępuje `WebProgress`.

### 2.3 Widoki — `src/raport_slotow/views/uczelnia.py`

| Klasa (linia) | Baza legacy | Rola |
|---|---|---|
| `ListaRaportSlotowUczelnia` (:35) | `LongRunningOperationsView` | lista raportów usera (owner-scoped, KASUJE stare >10) |
| `UtworzRaportSlotowUczelnia` (:48) | `CreateLongRunningOperationView` | formularz + `form_valid` ustawia `uczelnia = uczelnia_dla_odczytu(request)` (:60-62) |
| `RouterRaportuSlotowUczelnia` (:70) | `LongRunningRouterView` | routing NOT_STARTED→wait / STARTED→details / OK→results |
| `SzczegolyRaportSlotowUczelnia` (:75) | `LongRunningDetailsView` | strona postępu (subskrypcja kanału pk) |
| `WygenerujPonownieRaportSlotowUczelnia` (:83) | `RestartLongRunningOperationView` | **GET** regen: `mark_reset` + re-enqueue |
| `SzczegolyRaportSlotowUczelniaListaRekordow` (:90) | `LongRunningResultsView` | filtrowalna tabela wyników + eksport XLSX |

- Wszystkie (poza Utworz) mają `BaseRaportAuthMixin` (`src/nowe_raporty/views.py:76`)
  = `UczelniaSettingRequiredMixin` + `group_required = GR_RAPORTY_WYSWIETLANIE`
  (`src/bpp/const.py:22`) + `uczelnia_attr="pokazuj_raport_slotow_uczelnia"`.
  To jest **bramka autoryzacji, którą trzeba utrzymać** (patrz §8).
- `LongRunningResultsView` (`src/long_running/views.py:88`): `paginate_by=25`,
  `parent_object` owner-scoped (`o.owner != request.user -> Http404`),
  `get_queryset()->parent_object.get_details_set()`, przekazuje
  `object=parent_object` do kontekstu (:103). **Results-view używa jednak
  django_tables2 (`SingleTableMixin` + `RequestConfig`), więc realną
  paginację robi tabela, nie `ListView.paginate_by`** — ważne przy odtworzeniu.

### 2.4 URL-e — `src/raport_slotow/urls.py`

`lista-…` (:35), `utworz-…/new` (:39), `…-router/<uuid:pk>/` (:44),
`…-details` (:49), `…-regen` (:54), `…-results` (:59). Reverse'y tych nazw
poza aplikacją / w testach:
- `top_bar.html:123` → `lista-raport-slotow-uczelnia`.
- `src/bpp/tests/.../test_uczelnia.py:321,326` → `lista-…`.
- testy `raport_slotow` → `-details`, `-results`, `-regen`, `lista-…`.
- szablony `-list.html:19` → `-router`; breadcrumbs → `lista-…`.

### 2.5 Scoping per-uczelnia — jak nić przechodzi

1. **Zapis (create):** `UtworzRaportSlotowUczelnia.form_valid`
   (`views/uczelnia.py:60`) woła `uczelnia_dla_odczytu(self.request)`
   (`src/raport_slotow/uczelnia_helper.py:10`) → hybryda: uczelnia z requestu
   (host→Site→Uczelnia), a superuser może nadpisać `?uczelnia=<pk>`. Wynik
   ląduje w `form.instance.uczelnia`.
2. **Generacja (run):** `create_report` filtruje kombinacje i przekazuje
   `uczelnia_id`/`uczelnia` do `zbieraj_sloty`/`autorzy_zerowi`
   (`models/uczelnia.py:122-123,143,168-173`).
3. **Odczyt (results/list):** owner-scoping (`owner=request.user`) izoluje
   raporty per-użytkownik; sam raport niesie już zawężone dane (scoping
   „wypalony" przy generacji). List/results nie filtrują ponownie po uczelni —
   ich izolacja to owner + fakt, że wiersze są już per-uczelnia.

Testy strażujące scoping:
- `tests/test_uczelnia_helper.py` — reguły `uczelnia_dla_odczytu`
  (nie-superuser nie nadpisze, superuser tak, złe pk → bazowa).
- `tests/test_views/test_raport_slotow_zerowy_per_uczelnia.py` — zawężenie
  „strony punktowej" do uczelni oglądającego (dotyczy raportu **zerowego**,
  nie uczelnia-report, ale to ten sam mechanizm `uczelnia=` w `core.py`).
- `tests/test_per_uczelnia_uczelnia.py`, `tests/tests_models/test_uczelnia.py`
  — do przejrzenia pod kątem regresji generacji.

---

## 3. Docelowy stan (liveops 0.4)

- `class RaportSlotowUczelnia(LiveOperation)` (`liveops.models.LiveOperation`,
  pkg `.venv/.../liveops/models.py:27`). Znika `ASGINotificationMixin` i
  `long_running.Report`.
- `run(self, p)` zastępuje `create_report()`; postęp przez `p.percent(...)`
  / `p.track(...)`; brak `send_progress`.
- `on_restart()` zastępuje `on_reset()` (`liveops.models.LiveOperation.on_restart`,
  pkg models.py:183).
- Strona „live" = centralny `liveops:live` (`get_absolute_url()` zwraca
  `reverse("liveops:live", op_type=<app.model>, pk=...)`, pkg models.py:155),
  montowany raz w `src/django_bpp/urls.py:286` (`path("live/", include("liveops.urls"))`).
  Znikają widoki router/details — ich rolę pełni host page liveops.
- Widoki tworzenia/listy/wyników/restartu = cienkie podklasy owner-scoped
  (wzór: `src/import_pracownikow/views.py`).
- `LIVEOPS` już skonfigurowane globalnie (`src/django_bpp/settings/base.py:1049`):
  `RUNNER="celery"` (prod), w testach `settings/test.py` nadpisuje na `"eager"`
  (synchronicznie, bez Redis/workera). `liveops` jest w INSTALLED_APPS
  (base.py:455).

---

## 4. Mapowanie `Report.create_report` → liveops `run(self, p)` + rendering raportu

### 4.1 Sam przebieg

Legacy `create_report()` (models/uczelnia.py:108) przenosimy 1:1 do
`run(self, p)`, podmieniając TYLKO warstwę postępu i finalizację:

- `total = kombinacje.count()`; pętla jak dotąd, ale zamiast
  `if not n%10: self.send_progress(n*100.0/total)` używamy:
  - albo `p.percent(int(n*100/total))` (throttling ma już `Progress.percent`,
    pkg progress.py:52 — nie trzeba ręcznego `%10`),
  - albo idiomatycznie `for res in p.track(kombinacje, total=total):` (pkg
    progress.py:68) — dodatkowo woła `check_cancelled()` przed każdym elementem.
    **Uwaga:** `p.track` liczy `total=len(...)` gdy `total=None`; podajemy
    `total` jawnie, bo `kombinacje` to queryset (materializacja `list()` byłaby
    kosztowna). `.count()` + iteracja queryset są OK.
- **Scoping bez zmian:** `self.uczelnia_id` / `self.uczelnia` nadal filtrują
  kombinacje (:122) i płyną do `zbieraj_sloty`/`autorzy_zerowi`. Migracja NIE
  dotyka tej logiki — tylko warstwy postępu.
- Anulowanie: `p.track` / okresowe `p.check_cancelled()` daje działający Anuluj
  (którego legacy nie miało). Opcjonalne, ale „za darmo".

### 4.2 Transakcyjność (różnica behawioralna — WAŻNE)

Legacy owijało cały `create_report` w `transaction.atomic()`
(`src/long_running/models.py:108`). liveops `task_run` woła `operation.run(p)`
**bez** transakcji (pkg runner.py:143). Żeby zachować all-or-nothing generacji
(inaczej błąd w połowie zostawia częściowe wiersze), **owijamy ciało `run` w
`with transaction.atomic():`**. Konsekwencja: `p.result(...)` używa
`transaction.on_commit` (pkg progress.py:302) — wewnątrz atomic odpali się przy
commit (poprawnie); pushe `p.percent` są synchroniczne (group_send), więc pasek
działa mimo otwartej transakcji.

### 4.3 Finalizacja i rendering raportu (specyfika Report — brak wzorca)

**Nie istnieje zmigrowany Report referencyjny** — `import_pracownikow` woła
`p.result(context)` z bogatym słownikiem i renderuje panel inline. Dla Reportu
wyjście (wiersze) jest w bazie, a „wynikiem" jest osobna strona tabeli
(`-results`). Dwie ścieżki (do decyzji, patrz §9):

- **Ścieżka A (rekomendowana): auto-redirect na results.** `run()` nie woła
  `p.result()` (albo woła z pustym kontekstem). Definiujemy
  `get_success_url(self)` (pkg models.py:169) → `reverse("raport_slotow:
  raportslotowuczelnia-results", kwargs={"pk": self.pk})`. Po `FINISHED_OK`
  `liveops.js` przenosi usera prosto na tabelę wyników (wzór:
  `ImportPracownikow.get_success_url`, `src/import_pracownikow/models.py:224`).
  Result-fragment (host page) pełni tylko rolę fallbacku no-JS.
- **Ścieżka B: inline result-fragment.** `run()` woła `p.result(context)` z
  minimalnym kontekstem (np. liczba wierszy), a `raport_slotow_uczelnia_result.html`
  (nowy) renderuje krótkie podsumowanie + link „Zobacz wyniki". Więcej pracy,
  bez wyraźnej korzyści dla Reportu.

Auto-finalize: jeśli `run()` skończy bez `p.result()`, `task_run` sam ustawia
`finished_successfully=True` i woła `push_finished` (pkg runner.py:145-151) →
render `result_template_name`. Dlatego przy Ścieżce A i tak potrzebny jest
**minimalny** `result_template_name` (patrz §10) — inaczej push wyrenderuje pustkę
(bezpiecznie, ale brzydko dla no-JS).

### 4.4 Host page (strona „live")

Nowy szablon host (patrz §10) zawiera region `{% live_operation object %}`
owinięty w `<div hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>` (gotcha CSRF,
§7). Wzór: `src/import_pracownikow/templates/import_pracownikow/import_pracownikow.html:27`.

### 4.5 API v1 — DRUGA powierzchnia, pęka natychmiast po migracji (HIGH)

`RaportSlotowUczelnia` ma REST-owy odpowiednik, którego pierwotny plan pominął.
To NIE jest opcjonalne — serializer wywala się w momencie usunięcia pola.

Pliki:
- `src/api_v1/serializers/raport_slotow_uczelnia.py`
- `src/api_v1/viewsets/` (viewset `RaportSlotowUczelniaViewSet` — owner-scoped)
- `src/api_v1/tests/test_raport_slotow_uczelnia.py`

Dwa twarde pęknięcia po Fazie 2 (migracja modelu):
1. **`last_updated_on` w `fields`/`read_only_fields`** (`serializers/…:25,38`).
   Po `RemoveField(last_updated_on)` KAŻDE żądanie do viewsetu (nawet
   read-only GET listy) → DRF `ImproperlyConfigured` (pole w Meta nie istnieje
   na modelu). **Fix:** usuń `last_updated_on` z obu list w Meta. Rozważ dodanie
   `cancelled`/`finished_successfully` do read-only, jeśli chcesz je wystawić —
   ale minimalny fix to samo usunięcie `last_updated_on`.
2. **`create()` enqueue przez legacy task** (`serializers/…:66-76`):
   `perform_generic_long_running_task(ct.app_label, ct.model, inst.pk)`
   (`long_running/tasks.py:11`) na końcu woła `obj.task_perform()`
   (tasks.py:32), którego `LiveOperation` NIE ma → `AttributeError` w tasku
   celery (cichy — raport nigdy się nie wygeneruje). **Fix:** przepisz na
   `transaction.on_commit(lambda: inst.enqueue())`.
   **UWAGA — to REALNY przypadek enqueue-inside-atomic z §7.4:** `create()` jest
   `@transaction.atomic` (`serializers/…:66`), więc NIE wolno wołać `inst.enqueue()`
   bezpośrednio (task odpaliłby zanim wiersz się zacommituje → retry-loop
   `perform_generic_long_running_task` był właśnie obejściem tego; `enqueue()`
   przez runner NIE ma retry). MUSI być `transaction.on_commit`. Istniejący
   `ContentType.get_for_model` + `perform_generic_long_running_task` znikają.
3. **Test** `test_raport_slotow_uczelnia.py` — dziś tylko owner-scope na GET
   (nie dotyka `last_updated_on` w asercjach, ale request przechodzi przez
   serializer → padnie na (1)). Po fixie (1) testy GET powinny przejść. Dodaj
   test POST create (enqueue przez `on_commit`, pod eager runner generuje
   wiersze) — dziś BRAK testu ścieżki create (patrz §8.1 pkt LOW-4).

Ta praca należy do **Fazy 2** (migracja modelu) — serializer pęka w tej samej
chwili co pole. NIE odkładaj na Fazę 3.

---

## 5. Migracja modelu (nowa migracja, pk, FK/related_name, dane)

Dodaj **nową** migrację `src/raport_slotow/migrations/0022_liveops.py`
(nie edytuj istniejących; ostatnia to `0021_merge_20260604_1952.py`). Wzór:
`src/import_pracownikow/migrations/0010_liveops.py`.

Operacje (delta legacy `Operation` → `LiveOperation`):
- `AlterModelOptions(ordering=["-created_on"])` — było `-last_updated_on`.
  **Efekt UX (nie tylko sucha zmiana Meta):** lista sortuje po dacie
  UTWORZENIA, nie ostatniej modyfikacji. Regenerowany (regen) raport NIE
  wskakuje już na górę listy — zostaje w miejscu wg `created_on`. Legacy
  `last_updated_on` (auto_now) wypychało świeżo-przeliczony raport na szczyt.
  Akceptowalne (spójne z liveops i całą resztą operacji), ale odnotować.
- `RemoveField last_updated_on` — łamie API v1 serializer (§4.5 pkt 1); fix
  serializera należy do tej samej fazy.
- `AddField`: `cancel_requested` (Bool default False), `cancelled` (Bool),
  `current_stage` (Int -1), `language` (Char blank), `log` (JSON default list),
  `log_seq` (PositiveInt 0), `percent` (PositiveSmallInt 0), `result_context`
  (JSON null), `stage_states` (JSON default dict), `status_text` (Char blank).
  **Uwaga:** `status_text` istnieje w `LiveOperation` (models.py:56) —
  import_pracownikow ją dodał (0010:93); dodać też tu dla spójności stanu.
- `AlterField owner` → `related_name="+"` (pkg models.py:31). To zmiana tylko
  Django-level (reverse accessor), bez zmiany kolumny; makemigrations i tak
  ją wygeneruje.

**pk:** BEZ ZMIAN — już `UUIDField` z `default=uuid4` (legacy `Operation.id`,
`src/long_running/models.py:20`; liveops `LiveOperation.id`, pkg models.py:30 —
oba `uuid4`). URL-e już `<uuid:pk>`.

**FK/related_name — świadoma decyzja:** zmiana `owner` na `related_name="+"`
usuwa reverse accessor `user.raportslotowuczelnia_set`. Grep pokazał brak jego
użycia — bezpieczne. `RaportSlotowUczelniaWiersz.parent`
(`models/uczelnia.py:241`) zostaje bez zmian (`raportslotowuczelniawiersz_set`
używane w `run`/`get_details_set`).

**Dane:** raport_slotow NIE ma odpowiednika `performed/integrated→stan`
(import miał, 0010:8-11). Nowe pola mają defaulty → `AddField` bez data-migracji.
Usunięcie `last_updated_on` bez utraty istotnych danych (auto_now, pochodna).
Istniejące raporty zachowują `finished_on/started_on/finished_successfully`
(wspólne dla obu baz) — po migracji dalej otwierają się jako „skończone".

**Baseline:** po dodaniu migracji baseline będzie nieaktualny — **NIE
odświeżaj baseline w tym branchu** (reguła CLAUDE.md: baseline raz, przy
scalaniu). Odnotuj w PR, że `make baseline-update` należy zrobić przy merge.

---

## 6. Fazy (uporządkowane, każda niezależnie „zielona", TDD)

**Liczba faz: 5** (Faza 0 charakteryzacja → Faza 1 opcjonalny most zgodności →
Faza 2 model+migracja+API v1 → Faza 3 widoki+URL+szablony → Faza 4 sprzątanie).
Faza 1 jest opcjonalna (do pominięcia przy czystym cutover), więc ścieżka
minimalna to 4 fazy wykonawcze + Faza 0.

Kolejność minimalizuje okno niespójności. Każda faza kończy się przebiegiem
`uv run pytest src/raport_slotow` (i, gdzie wskazano, `src/api_v1`,
`src/import_pracownikow` oraz `src/long_running`).

### Faza 0 — testy charakteryzujące (RED→GREEN baseline)
Przed zmianami: uruchom istniejące testy raport_slotow, potwierdź zieleń
(`uv run pytest src/raport_slotow`). Spisz oczekiwane zmiany kontraktu (patrz
§8) — które testy MUSZĄ się zmienić (regen GET→POST, lista-delete, details).
Nic nie zmieniaj w kodzie.

### Faza 1 (opcjonalna) — most zgodności emisji (jeśli chcesz rozdzielić emisję od cutover)
Tylko jeśli chcesz najpierw przełączyć `create_report` na API `Progress`
zanim zmienisz bazę modelu. Wprowadź lokalny, minimalny `Progress`, który
FORWARD-uje `percent/status` do legacy `send_progress`/`send_notification` i
**nadpisuje `check_cancelled` na no-op** (legacy model NIE ma `cancel_requested`;
`Progress.check_cancelled` robi `refresh_from_db(fields=["cancel_requested"])`,
pkg progress.py:154 → wywaliłoby się `FieldError`). **NIE używaj `TextProgress`
na modelu legacy** z tego samego powodu (jego `check_cancelled` też sięga pola).
Ta faza jest zbędna, jeśli robisz czysty cutover (Faza 2+3 razem) — raport_slotow
jest prosty, więc most prawdopodobnie pomijamy. Udokumentowane dla kompletności.

### Faza 2 — model + migracja + API v1 (cutover bazy)
Model i API v1 pękają razem (serializer wymienia `last_updated_on` i woła
`task_perform`), więc idą w JEDNEJ fazie — inaczej po kroku 2 każdy request do
viewsetu zwraca 500.
1. Test (RED): `tests/tests_models/test_liveops_uczelnia.py` — instancja jest
   `LiveOperation`, ma pola `cancel_requested/cancelled/result_context/...`,
   `on_restart()` kasuje wiersze, `run(p)` generuje wiersze i respektuje
   `self.uczelnia` (scoping!). Wzór: `import_pracownikow/tests/test_models/test_liveops_model.py`.
2. Zmień bazę: `RaportSlotowUczelnia(LiveOperation)`; `create_report`→`run(self,p)`
   (owinięte w `transaction.atomic()`, §4.2); `on_reset`→`on_restart`; usuń
   `ASGINotificationMixin`; ustaw jawnie `host_template_name` (§10, kolizja) —
   `result_template_name` też jawnie, ale to tylko wybór pliku, nie kolizja;
   dodaj `get_success_url` (Ścieżka A, §4.3); zachowaj `clean()`,
   `get_details_set()`, `uczelnia`, walidacje.
3. `makemigrations raport_slotow` → nowa `0022_liveops.py` (§5). Zweryfikuj,
   że to delta (nie churn), `--check` czysty po zastosowaniu.
4. **API v1 (§4.5) — w tej samej fazie:** usuń `last_updated_on` z Meta
   `fields`/`read_only_fields` (`api_v1/serializers/raport_slotow_uczelnia.py:25,38`);
   przepisz `create()` (:66-76) z `perform_generic_long_running_task` na
   `transaction.on_commit(lambda: inst.enqueue())` (create jest `@atomic` →
   MUSI być on_commit). Zaktualizuj/rozszerz `api_v1/tests/test_raport_slotow_uczelnia.py`
   (GET po fixie przechodzi; dodaj test create-enqueue pod eager runner).
   Podejmij decyzję LOW-4 (§8.1): czy create ustawia `uczelnia`.
5. GREEN: `uv run pytest src/raport_slotow/tests/tests_models src/api_v1/tests/test_raport_slotow_uczelnia.py`.

### Faza 3 — widoki + URL-e + szablony (cutover UI)
1. Testy (RED): zaktualizowane `test_views/test_uczelnia.py` — patrz §8:
   - lista owner-scoped (decyzja o max-10, §8/§9),
   - tworzenie ustawia `uczelnia` i redirectuje na `liveops:live`,
   - results owner-scoped + eksport XLSX (istniejące testy w
     `test_raport_slotow_uczelnia.py` MUSZĄ przejść bez zmian albo z minimalną
     korektą fixture),
   - regen jako **POST** resetuje i re-enqueue (GET→POST).
2. Przepisz `views/uczelnia.py`:
   - `UtworzRaportSlotowUczelnia(UczelniaSettingRequiredMixin, FormDefaultsMixin,
     CreateLiveOperationView)` — nadpisz `form_valid`: ustaw `owner`,
     `uczelnia=uczelnia_dla_odczytu(request)`, `self.object=form.save()`,
     `self.object.enqueue()`, `redirect(self.object.get_absolute_url())`.
     **enqueue bezpośrednio — bez `on_commit`** (brak ATOMIC_REQUESTS; gotcha §7).
   - `ListaRaportSlotowUczelnia(BaseRaportAuthMixin, FormDefaultsMixin, ListView)`
     — owner-scoped `get_queryset` (jak `ListaImportowView`,
     `import_pracownikow/views.py:118`). Zachowaj custom szablon listy, ale
     zmień link z `-router` na `object.get_absolute_url` (liveops:live).
   - USUŃ `RouterRaportuSlotowUczelnia` i `SzczegolyRaportSlotowUczelnia`
     (rolę przejmuje `liveops:live`). URL-e `-router`/`-details`: albo usuń,
     albo zostaw jako cienki redirect na `liveops:live` (jeśli coś je reverse'uje
     — patrz §8; `-router` używa tylko własny list-template, `-details` tylko test).
   - `SzczegolyRaportSlotowUczelniaListaRekordow` — odetnij od
     `LongRunningResultsView`; odtwórz `parent_object` (owner-scoped +
     superuser-exempt, jak `ImportPracownikowResultsView.parent_object`,
     `import_pracownikow/views.py:662`) i `get_queryset`. Zachowaj cały
     `SingleTableMixin`/`FilterMixin`/`MyExportMixin`/eksport-XLSX. **Kontekst
     musi dalej zawierać `object=parent_object`** (szablon czyta `object.od_roku`
     itd., `raport_slotow_uczelnia.html:4,18`). Paginacja: robi ją django_tables2
     (`RequestConfig`), nie `ListView.paginate_by` — ale ustaw i tak
     `paginate_by` dla zgodności z gotchą, jeśli po odcięciu bazy `ListView`
     zacznie wymagać (zweryfikuj testem eksportu).
   - `WygenerujPonownieRaportSlotowUczelnia` — wzór `_PkOwnerRestartMixin`
     (`import_pracownikow/views.py:1386`): `RestartView` + `BaseRaportAuthMixin`
     (utrzymanie bramki grupy!) + `get_object` owner-scoped rozwiązujący model
     wprost (URL ma tylko `pk`, bez `op_type`). POST-only. **Guard „tylko gdy
     skończone" (§8.4):** nadpisz `post`, by resetował/re-enqueue'ował TYLKO gdy
     `obj.get_state()` jest terminalny (finished OK/error/cancelled) — inaczej
     regen w połowie runu skasuje wiersze piszące. Test: regen na
     nie-skończonym raporcie NIE resetuje.
3. Szablony (§10): nowy host `raport_slotow_uczelnia_live.html`; minimalny
   `raport_slotow_uczelnia_result.html`; zaktualizuj `-list.html` (link na
   `get_absolute_url`); zmień `<a href="../regen">` w `raport_slotow_uczelnia.html:27`
   na **formularz POST** (regen jest POST) z `{% csrf_token %}`. Usuń martwe
   `include "long_running/operation_details.html"` z `-detail.html` (jeśli
   `-detail`/`-details` znika).
4. GREEN: `uv run pytest src/raport_slotow`.

### Faza 4 — sprzątanie + weryfikacja integracyjna
- Usuń nieużywane szablony (`raportslotowuczelnia_detail.html`,
  `raportslotowuczelniawiersz_list.html`, ewentualnie `-list` jeśli zastąpiony)
  po potwierdzeniu braku referencji.
- **Grep REPO-WIDE (nie tylko `src/raport_slotow`)** dla resztek legacy
  powiązanych z tym modelem — pierwotny plan grepował tylko aplikację i przez
  to zgubił `api_v1`:
  ```
  grep -rn "task_perform\|task_create_report\|perform_generic_long_running_task\|last_updated_on" src/ --include="*.py"
  ```
  Zweryfikuj, że żadne trafienie NIE dotyczy `RaportSlotowUczelnia`
  (`raport_slotow`, `api_v1`). Potwierdź brak `import long_running` w
  `raport_slotow` ORAZ w `api_v1/serializers/raport_slotow_uczelnia.py`.
- `uv run pytest src/raport_slotow src/api_v1 src/import_pracownikow src/long_running`
  (regresja sąsiadów + API).
- Playwright (opcjonalnie, jeśli dotknięto UI live): `make assets` +
  `src/raport_slotow/tests/test_playwright`.
- Newsfragment `src/bpp/newsfragments/raport-slotow-liveops.feature.rst`.

---

## 7. Pre-loaded gotchas (wbudowane w plan)

1. **CSRF_COOKIE_HTTPONLY=True** (`settings/base.py:1596` wg zadania). Host
   template MUSI owinąć `{% live_operation object %}` w
   `<div hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>` — inaczej
   Anuluj/Ponów liveops → 403. Wzór: `import_pracownikow.html:27`.
2. **Results view / paginacja i `object`.** Szablon wyników
   (`raport_slotow_uczelnia.html`) używa `{% url ... %}` z `lista-…` i
   czyta `object.od_roku/…` → results-view MUSI przekazywać `object=parent_object`
   (jak legacy, `views/uczelnia.py:148`). Realną paginację robi django_tables2;
   `paginate_by` ustaw defensywnie i zweryfikuj testem XLSX.
3. **Restart bramkowany grupą.** liveops gejtuje tylko gdy `LIVEOPS["REQUIRED_GROUP"]`
   ustawione — w BPP NIE jest (`settings/base.py:1049`, brak klucza). Dlatego
   restart/regen MUSI dostać `BaseRaportAuthMixin` (grupa `GR_RAPORTY_WYSWIETLANIE`
   + owner-scope), tak jak legacy. Wzór `_PkOwnerRestartMixin`.
4. **enqueue() → celery `.delay()`, BEZ on_commit.** Tworzenie nie jest w
   `transaction.atomic` i brak `ATOMIC_REQUESTS` → bezpośredni `enqueue()` po
   `save()` jest bezpieczny (wzór `CreateLiveOperationView.form_valid`, pkg
   views.py:101). Gdybyś kiedyś owinął tworzenie w atomic — wtedy
   `transaction.on_commit(lambda: op.enqueue())`.
5. **Kolizja nazw szablonów — TYLKO host.** `class_to_snake("RaportSlotowUczelnia")`
   = `raport_slotow_uczelnia` → auto **host** = `raport_slotow/raport_slotow_uczelnia.html`
   = **istniejący szablon wyników** → prawdziwa kolizja. Ustaw JAWNIE
   `host_template_name` (np. `raport_slotow/raport_slotow_uczelnia_live.html`).
   Auto **result** = `raport_slotow/raport_slotow_uczelnia_result.html` (sufiks
   `_result`) — z NICZYM nie koliduje. `result_template_name` ustawiamy jawnie
   tylko dla czytelności / wyboru pliku, NIE z powodu kolizji.
6. **Most fazy 1 (jeśli użyty).** Lokalny `Progress` forwardujący do legacy
   `send_progress`/`send_notification` + `check_cancelled` jako no-op (legacy
   model nie ma `cancel_requested` → `refresh_from_db` by wywaliło). NIE
   `TextProgress` na modelu legacy.
7. **Nie edytuj istniejących migracji**; dodaj `0022_liveops.py`. **Nie
   odświeżaj baseline** w tym branchu (odnotuj potrzebę przy merge).
8. **Transakcyjność generacji** — owiń `run()` w `transaction.atomic()` (§4.2),
   bo `task_run` nie owija (legacy owijało).
9. **liveops RestartView resetuje BEZWARUNKOWO** (`liveops/views.py:175`), legacy
   tylko gdy skończone (`long_running/views.py:125`). Regen w połowie runu →
   `on_restart` kasuje wiersze, które biegnący task jeszcze pisze + drugi run.
   Guard w podklasie regenu (patrz §8.4).
10. **API v1 create jest `@transaction.atomic`** (`serializers/…:66`) — enqueue
    MUSI iść przez `transaction.on_commit` (§4.5). To jedyna ścieżka w kodzie,
    gdzie „enqueue-inside-atomic" faktycznie występuje (§7.4 był hipotetyczny dla
    widoku; API jest realny).

---

## 8. Zachowanie do utrzymania — ESPECIALLY per-uczelnia scoping + testy strażujące

### 8.1 Scoping per-uczelnia (KRYTYCZNE — nie zgubić)
- `uczelnia` FK na modelu ZOSTAJE (pole domenowe, nie liveops).
- **DWIE ścieżki zapisu** — pierwotny plan wspominał tylko widok:
  - **Widok:** `UtworzRaportSlotowUczelnia.form_valid` MUSI dalej ustawiać
    `uczelnia = uczelnia_dla_odczytu(request)` PRZED `save()` (przenieś do
    nadpisanego `form_valid` liveops).
  - **API v1 (LOW-4):** `RaportSlotowUczelniaSerializer.create`
    (`api_v1/serializers/…:66-76`) ustawia dziś tylko `owner`, NIE `uczelnia`
    → raport tworzony przez API jest NIE-zawężony (kombinacje po wszystkich
    uczelniach). To stan OBECNY (przed migracją), a `test_raport_slotow_uczelnia.py`
    świadomie polega na owner-scope, nie uczelnia-scope. **Świadoma decyzja przy
    realizacji:** (a) zostawić jak dziś (owner wystarcza do izolacji odczytu, a
    generacja bez `uczelnia` = raport globalny — być może zamierzone dla API),
    albo (b) dołożyć `uczelnia_dla_odczytu(request)` w `create()` dla parytetu z
    widokiem. Domyślnie NIE zmieniać zachowania (a) — ale UDOKUMENTOWAĆ w PR, że
    to celowe, nie przeoczenie.
- `run()` MUSI zachować `if self.uczelnia_id is not None:
  kombinacje.filter(jednostka__uczelnia_id=self.uczelnia_id)` oraz przekazywanie
  `uczelnia_id=self.uczelnia_id` do `zbieraj_sloty` i `uczelnia=self.uczelnia`
  do `autorzy_zerowi`. Migracja NIE dotyka tej logiki.
- **Testy strażujące:** `tests/test_uczelnia_helper.py` (helper),
  `tests/test_views/test_raport_slotow_zerowy_per_uczelnia.py` (mechanizm
  `uczelnia=` w core), `tests/test_per_uczelnia_uczelnia.py`,
  `tests/tests_models/test_uczelnia.py`. Dodaj test Fazy 2 sprawdzający, że
  `run(p)` na raporcie z ustawioną `uczelnia` generuje wiersze tylko dla jej
  jednostek (RED przed cutover jeśli dziś brak takiego testu na poziomie run()).

### 8.2 Bramka autoryzacji
`BaseRaportAuthMixin` (grupa `GR_RAPORTY_WYSWIETLANIE` + `uczelnia_attr` +
`UczelniaSettingRequiredMixin`) na liście, results i regenie — utrzymać na
wszystkich odpowiednikach. Tworzenie: `UczelniaSettingRequiredMixin` (jak dziś).

### 8.3 Kontrakty testów, które MUSZĄ się zmienić (spisać w Fazie 0)
- `test_RegenerujRaportuSlotowUczelnia` (`test_views/test_uczelnia.py:63`) —
  dziś **GET** na regen, asercja że `finished_on` się zmienia. liveops
  `RestartView` jest **POST-only** → przepisz na POST. Pod `RUNNER="eager"`
  enqueue biegnie synchronicznie → run() wykona się → `finished_on` się zmieni.
- `test_ListaRaportSlotowUczelnia` (:13) — dziś asercja, że lista KASUJE stare
  (`count 20 → 10`). liveops list-view nie kasuje. Decyzja (§9): albo
  odtworzyć „delete >N" w `get_queryset` (i test zostaje), albo porzucić tę
  quirk i **zmienić test**. Rekomendacja: porzucić auto-delete (housekeeping
  to nie zadanie list-view) i zaktualizować test.
- `test_SzczegolyRaportuSlotowUczelnia` (:27) — hituje `-details`. Po usunięciu
  details: repointuj na `liveops:live` (`get_absolute_url`) lub usuń test.
- `test_form_formdefaults.py:17` — importuje `UtworzRaportSlotowUczelnia`
  (klasa zostaje, tylko baza inna) — powinien przejść bez zmian.
- **API v1 (§4.5):** `api_v1/tests/test_raport_slotow_uczelnia.py` — GET-y padną
  na `last_updated_on` w Meta, dopóki serializer nie jest zfiksowany (Faza 2).
  Po fixie przechodzą; dodać test create-enqueue.

### 8.4 Guard restartu „tylko gdy skończone" (MEDIUM — nie zgubić)
Legacy `RestartLongRunningOperationView.get` resetuje **tylko** gdy
`self.object.finished_on is not None` (`long_running/views.py:125`). liveops
`RestartView.post` resetuje **BEZWARUNKOWO** (`liveops/views.py:175-209`):
woła `on_restart()` (kasuje wiersze) + zeruje stan + re-enqueue, niezależnie od
tego, czy operacja właśnie biegnie. Pod `RUNNER="celery"` (prod) to realny
wyścig: regen POST w połowie generacji → `on_restart` kasuje
`raportslotowuczelniawiersz_set`, który biegnący task nadal wypełnia, i startuje
drugi run równolegle.

`import_pracownikow` **zaakceptował** bezwarunkowy restart — jego
`_PkOwnerRestartMixin`/`ZatwierdzImportView` (`import_pracownikow/views.py:1386,1407`)
NIE sprawdzają `finished_on` (grep potwierdza brak takiego guardu); tam bezpieczeństwo
daje maszyna stanów `stan` (analiza vs integracja) i to, że akcje są bramkowane po
`stan`. **Raport slotów NIE ma takiej maszyny stanów** — jego jedyny sygnał to
`get_state()`. Dlatego: **dołóż guard** w podklasie regenu — nadpisz `post`, by
resetował/re-enqueue'ował TYLKO gdy `obj.get_state()` jest terminalny
(`FINISHED_OK`/`FINISHED_ERROR`/`CANCELLED`); dla `STARTED`/`NOT_STARTED` zwróć
redirect na live bez resetu (jak legacy „nic nie rób gdy nieskończone"). Test:
regen na nie-skończonym raporcie NIE zmienia `started_on`/nie kasuje wierszy.

---

## 9. Strategia testów

- **TDD per faza** (§6): najpierw test opisujący docelowy kontrakt (RED),
  potem implementacja (GREEN). Pytest-only, `@pytest.mark.django_db`,
  `model_bakery.baker.make`, fixtures z `src/conftest.py` i
  `src/raport_slotow/tests/conftest.py`.
- **Model (Faza 2):** `test_liveops_uczelnia.py` — typ `LiveOperation`, nowe
  pola, `on_restart` kasuje wiersze, `run(p)` generuje wiersze + respektuje
  `uczelnia` scoping, atomic (błąd w połowie → brak częściowych wierszy).
  Runner „eager" (test settings) → `run` synchronicznie, `WebProgress`
  group_send trafia w pusty kanał (bez Redis) — OK, terminalny stan zapisany.
- **Widoki (Faza 3):** owner-scope (obcy owner → 404), tworzenie ustawia
  `uczelnia` + redirect na live, regen POST resetuje, results renderuje tabelę
  + XLSX. Zachowaj istniejące `test_raport_slotow_uczelnia.py` (filtry + XLSX)
  — mają przejść (ewentualnie fixture bez `started_on` wymaga korekty, bo
  results-view liveops nie wymaga `finished`, więc powinno działać).
- **Migracja:** `baseline-update` (przy merge, nie w branchu) waliduje
  zastosowanie migracji na czystym kontenerze — tu tylko `makemigrations
  --check` po dodaniu 0022.
- **Regresja sąsiadów:** `uv run pytest src/import_pracownikow src/long_running`
  (upewnić się, że `long_running` dalej działa dla pozostałych operacji).
- **Uruchamiaj lokalnie** (reguła CLAUDE.md): `uv run pytest src/raport_slotow`
  po każdej fazie; pełne `make tests-without-playwright` przed PR.

---

## 10. Szablony — konkretny plan

| Szablon | Akcja | Uwaga |
|---|---|---|
| `raport_slotow_uczelnia_live.html` (NOWY) | host page liveops | jawny `host_template_name`; `{% load liveops %}`, `<div hx-headers=...>{% live_operation object %}</div>`, skrypty htmx/notifications/liveops (wzór `import_pracownikow.html`) |
| `raport_slotow_uczelnia_result.html` (NOWY, minimalny) | result-fragment | jawny `result_template_name`; krótkie „raport gotowy" + link do `-results` (fallback no-JS; realny redirect robi `get_success_url`) |
| `raport_slotow_uczelnia.html` (ISTNIEJE) | results-table — ZOSTAJE | tylko zmień `<a href="../regen">` (:27) na `<form method="post" action="../regen">{% csrf_token %}...</form>` |
| `raportslotowuczelnia_list.html` | link `-router`→`object.get_absolute_url` | lub przejdź na liveops list-template |
| `raportslotowuczelnia_detail.html` | USUŃ (po usunięciu `-details`) | zawiera `include long_running/operation_details.html` |
| `raportslotowuczelniawiersz_list.html` | zweryfikuj/usuń | wygląda na martwy leftover |

**Jawne nazwy na modelu (obowiązkowo, przez kolizję §7.5):**
`host_template_name = "raport_slotow/raport_slotow_uczelnia_live.html"`,
`result_template_name = "raport_slotow/raport_slotow_uczelnia_result.html"`.

---

## 11. Ryzyka i pytania otwarte

1. **BRAK zmigrowanego Reportu jako wzorca (flaga).** `import_pracownikow` to
   importer z bogatym `p.result()` inline; Report generuje wyjście do bazy i
   pokazuje osobną tabelę. Mapowanie „run→rendering" (Ścieżka A vs B, §4.3) jest
   wywnioskowane z API liveops + `long_running.Report`, nie z istniejącej
   migracji. **Do decyzji przy realizacji.** Rekomendacja: Ścieżka A
   (`get_success_url` → results) + minimalny result-fragment fallback.
2. **Kolizja nazw szablonów** (§7.5) — najłatwiejsza do przeoczenia; auto-host
   nadpisałby szablon wyników. Mitigacja: jawne nazwy.
3. **regen GET→POST** — zmiana kontraktu URL (link w szablonie + test). Ktoś z
   zabookmarkowanym GET `/regen` dostanie 405. Akceptowalne (akcja mutująca).
4. **Auto-delete listy (>10)** — porzucenie zmienia zachowanie i test
   (`test_ListaRaportSlotowUczelnia`). Alternatywa: odtworzyć w `get_queryset`.
   Rekomendacja: porzucić (housekeeping poza list-view).
5. **Transakcyjność** (§4.2) — jeśli NIE owiniemy `run` w atomic, błąd w połowie
   zostawi częściowe wiersze (regresja vs legacy). Owinąć.
6. **`WebProgress` w prod wymaga Redis channel-layer** (jest, `settings/base.py`)
   — w testach eager+brak Redis → group_send trafia w pustkę, ale terminalny
   stan i tak w bazie (results czyta z bazy). OK.
7. **Router/details URL-e** — czy zostawić jako redirect-shim dla kompatybilności
   linków, czy usunąć? `-router` referuje tylko własny list-template (do zmiany),
   `-details` tylko test. Rekomendacja: usunąć, zaktualizować referencje.
8. **Baseline** — trzeba odświeżyć przy merge (`make baseline-update`), nie w
   branchu; łatwe do zapomnienia.
9. **API v1 pęka natychmiast po migracji (HIGH, §4.5).** Usunięcie
   `last_updated_on` → DRF `ImproperlyConfigured` na KAŻDYM żądaniu do viewsetu;
   `create()` woła nieistniejący `task_perform` → cichy `AttributeError` w tasku
   (raport się nie generuje). Musi być fiksowane w tej samej fazie co model
   (Faza 2). Enqueue MUSI iść przez `transaction.on_commit` (create jest
   `@atomic`). Pierwotny plan (grep tylko po aplikacji) tę powierzchnię zgubił.
10. **Restart bez guardu wyścig z workerem (MEDIUM, §8.4).** liveops
    `RestartView` resetuje bezwarunkowo; regen w połowie runu kasuje wiersze,
    które task pisze. Rekomendacja: guard na `get_state()` terminalny (jak legacy
    „reset tylko gdy finished"). `import_pracownikow` zaakceptował bezwarunkowość,
    ale on ma maszynę stanów `stan` — raport slotów nie ma, więc guard potrzebny.
11. **API v1 create NIE ustawia `uczelnia` (LOW, §8.1).** Raport z API jest
    nie-zawężony (wszystkie uczelnie). Stan obecny; rekomendacja: zostawić jak
    dziś, ale udokumentować że to celowe (owner-scope izoluje odczyt).

---

## 12. Czego NIE robić

- **NIE** edytować istniejących migracji `src/raport_slotow/migrations/*`
  (dodać `0022_liveops.py`).
- **NIE** odświeżać baseline w tym branchu (raz, przy scalaniu).
- **NIE** zmieniać typu pk (już UUID) ani schematu `RaportSlotowUczelniaWiersz`
  (poza ewentualnym `related_name`, którego NIE ruszamy).
- **NIE** dotykać logiki scoping per-uczelnia (`uczelnia` FK, filtry w `run`,
  `uczelnia_dla_odczytu`) — przenieść 1:1.
- **NIE** używać `TextProgress` ani `check_cancelled` na modelu legacy (Faza 1
  most: `check_cancelled` no-op).
- **NIE** polegać na auto-nazwie host-template (kolizja) — ustawić jawnie.
- **NIE** owijać tworzenia w `transaction.atomic` bez `on_commit` przy enqueue;
  domyślnie enqueue bezpośrednio (bez atomic).
- **NIE** usuwać bramki grupowej `BaseRaportAuthMixin` na regenie/liście/results
  (liveops `REQUIRED_GROUP` jest nieustawione → sam liveops NIE gejtuje).
- **NIE** modyfikować kodu ani migracji w ramach tego zadania — to tylko plan.
