# Plan: migracja importera POLON z `long_running` na `django-liveops` (v3)

> Status: PLAN (do wykonania). Wersja 3 — poprawiona po dwóch rundach
> adversarialnego review (defekty zweryfikowane w kodzie tego worktree; patrz
> „Zmiany względem v2" i „Zmiany względem v1" na końcu). Ten dokument NIE zmienia
> kodu.

## Streszczenie

Importer POLON (`ImportPlikuPolon`) oraz importer absencji
(`ImportPlikuAbsencji`) nadal dziedziczą po `long_running.models.Operation`
+ `ASGINotificationMixin` (postęp przez `channels_broadcast`,
`?extraChannels=[pk]`). Migrujemy je na `liveops.LiveOperation` (kanały
`liveop.<pk>`, podpisany `subscription_token`, snapshot-on-connect,
throttlowany progress, runner celery). Zadanie jest **niepilne**: świeżo scalona
łatka (`long_running/authorizers.py` + `CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER`)
przywróciła live-progress na STAREJ ścieżce — to modernizacja spójnościowa, nie
naprawa awarii.

## Kontekst infrastrukturalny — CO JUŻ JEST (nie ruszać)

Infrastruktura liveops jest już wpięta na `dev` (i w tym worktree). Migracja
POLON to **wyłącznie zmiany w aplikacji** `import_polon` — bez plumbingu
ASGI/URL/settings:

- `pyproject.toml:160` — `django-liveops[celery]>=0.4.0,<0.5` (zainstalowane).
- `src/django_bpp/settings/base.py:455` — `"liveops"` w `INSTALLED_APPS`.
- `src/django_bpp/settings/base.py:1049` — `LIVEOPS = {BASE_TEMPLATE, RUNNER:
  "celery", THROTTLE_HZ: 10}`. **Brak `REQUIRED_GROUP`** (świadomie — bramkuje
  globalnie WSZYSTKIE liveopsy, w tym deduplikator).
- `src/django_bpp/settings/test.py:73` — `LIVEOPS = {**LIVEOPS, "RUNNER":
  "eager"}` — w testach dispatch jest SYNCHRONICZNY (bez Redis/workera).
- `src/django_bpp/asgi.py:13,23` — `liveops.routing`
  (`LiveOperationConsumer` = nadzbiór `NotificationsConsumer` + snapshot).
- `src/django_bpp/urls.py:286` — `path("live/", include("liveops.urls"))`
  (centralny `liveops:live` / `:cancel` / `:restart` po `op_type`).
- `src/django_bpp/settings/base.py:1596` — **`CSRF_COOKIE_HTTPONLY = True`**
  → `liveops.js` NIE odczyta tokenu z ciasteczka; host-template MUSI wstrzyknąć
  `X-CSRFToken` (patrz Faza 2, wzór `import_pracownikow.html:27`).
- `src/django_bpp/settings/base.py:1077` —
  `CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER =
  "long_running.authorizers.authorize_operation_channel"` — STARA ścieżka.
  **Zostaje** (inne importery nadal używają `extraChannels`); POLON „wypadnie"
  z autoryzatora sam, przestając być podklasą `Operation`.

### Referencje (co JEST i czego NIE MA na tym branchu)

Zweryfikowane w kodzie tego worktree — **rzeczywiście zmigrowane są TRZY
importery**: `import_pracownikow`, `import_punktacji_zrodel`,
`deduplikator_zrodel`.

- **KANONICZNY wzór = `import_pracownikow`** (najbliższy POLON-owi: dry-run→
  zapis, dzieci, uczelnia, grupa „wprowadzanie danych"):
  - migracja: `src/import_pracownikow/migrations/0010_liveops.py` — zawiera
    DOKŁADNIE naszą deltę: `AlterModelOptions ordering=["-created_on"]`,
    `RemoveField last_updated_on`, `AddField` ×10 (cancel_requested, cancelled,
    current_stage, language, log, log_seq, percent, result_context,
    stage_states, status_text), `AlterField owner related_name="+"`.
  - model: `src/import_pracownikow/models.py:72,251-345` — `run(self,p)` z
    obudową rollbar+re-raise, `on_restart()`, `reset_liveops_state()`.
  - host template: `src/import_pracownikow/templates/import_pracownikow/
    import_pracownikow.html` (z wrapperem CSRF, kolejnością skryptów).
  - widoki: `src/import_pracownikow/views.py:118-174` (ListView + Create),
    `1386-1455` (`_PkOwnerRestartMixin(GroupRequiredMixin, RestartView)`).
  - testy bramki: `src/import_pracownikow/tests/test_auth_gate.py`.
- **`import_list_ministerialnych` — NIE scalony na dev.** Zweryfikowane:
  `src/import_list_ministerialnych/models.py:10` to nadal
  `ASGINotificationMixin, Operation`; migracje kończą się na `0008_*`;
  `feat/liveops-import-list-ministerialnych` **NIE jest** przodkiem `dev`
  (`git merge-base --is-ancestor … → NOT-ancestor`). Jego diff
  (`origin/feat/liveops-import-list-ministerialnych`) można oglądać jako
  ilustrację, ale NIE traktować jako „w drzewie". (Patrz też „Ryzyka" —
  konflikt baseline przy scalaniu tych dwóch gałęzi.)

---

## Stan obecny (mapa legacy POLON)

### Modele — `src/import_polon/models.py`

- `ImportPlikuPolon(ASGINotificationMixin, Operation)` — pola: `rok`, `plik`,
  `ukryj_niezmatchowanych_autorow`, `zapisz_zmiany_do_bazy`,
  `ignoruj_miejsce_pracy`, `uczelnia` (FK `bpp.Uczelnia`). `perform()` →
  `analyze_file_import_polon(self.plik.path, self)`; `on_reset()` kasuje dzieci;
  `get_details_set()`; `autorzy_niezmatchowani()` (multi-hosted).
- `ImportPlikuAbsencji(ASGINotificationMixin, Operation)` — `plik`,
  `zapisz_zmiany_do_bazy`; `perform()` → `analyze_file_import_absencji`;
  `on_reset()`.
- Dzieci: `WierszImportuPlikuPolon`, `WierszImportuPlikuAbsencji` (FK `parent`).
- `ImportPolonOverride` — słownik.

`Operation` (`src/long_running/models.py:17`) daje: `id` (UUID pk), `owner`
(FK, **bez** `related_name`), `created_on`, `last_updated_on` (auto_now),
`started_on`, `finished_on`, `finished_successfully`, `traceback`,
`get_state`, `mark_*`, `mark_reset`, `task_perform`, `get_url`,
`get_absolute_url`→`get_url("router")`. **Brak** `cancel_requested`.

### Ścieżka postępu (legacy)

`ASGINotificationMixin`: `send_progress(pct)` (3× w `core/import_polon.py`:
505,542,611; 1× w `core/import_absencji.py:130`), `send_notification` (2× w
każdym rdzeniu), `send_processing_finished`. Widoki subskrybują
`extraChannels=[pk]`. Autoryzacja: `authorize_operation_channel`.

### Widoki — `views/plik_polon.py` + `plik_absencji.py`

- `PokazImporty(BaseImportPlikuPolonMixin, LongRunningOperationsView)` —
  zawężenie multi-hosted (`Q(uczelnia==current)|Q(uczelnia__isnull=True)`),
  per-uczelnia trim `max_previous_ops`, order_by `-last_updated_on`.
- `UtworzImportPlikuPolon(…, CreateLongRunningOperationView)` — `form_valid`
  ustawia `uczelnia = Uczelnia.get_for_request(request)`.
- `ImportPolonRouterView` / `…DetailsView` / `RestartImportView`.
- `ImportPolonResultsView(…, LongRunningResultsView)` — filtry + kontekst
  `unmatched_autor_dyscyplina`.
- `ZapiszDoBazyMixin(RestrictToOwnerMixin, LongRunningTaskCallerMixin,
  DetailView)` (`plik_polon.py:21-48`) — **owner-scope z
  `RestrictToOwnerMixin`** (import z `long_running.views`); POST
  (`@transaction.atomic` + `select_for_update`) → guard → flip flagi →
  `self.object.mark_reset()` (linia 46) → `self.task_on_commit(pk)` (linia 47)
  → `HttpResponseRedirect("..")` (linia 48).
- `views/__init__.py` — star-importuje oba moduły (`from .plik_absencji import *`
  + `from .plik_polon import *`).

### URL-e — `src/import_polon/urls.py`

`index`, `utworz-import`, `importplikupolon-router|details|restart|
zapisz-do-bazy|results`; lustrzane `importplikuabsencji-*`; `index-absencji`
(linia 35 — mapuje na `views.PokazImporty`, czyli listę POLON, **nie**
absencji), `utworz-import-absencji`.

### Szablony

- `importplikupolon_detail.html`, `importplikuabsencji_detail.html` — include
  `long_running/operation_details.html`. **Do usunięcia.**
- `importplikupolon_list.html` — link `…importplikupolon-router` + label
  `{{ object.uczelnia }}`.
- `wierszimportuplikupolon_list.html` / `…absencji_list.html` — strona wyników;
  include `operation_details.html` + przycisk „zapisz do bazy".
- `potwierdz_zapis_do_bazy.html` — form `action="."` (POST OK) + link Anuluj
  `href=".."` (**→ router URL, do naprawy w Fazie 2**).

### Testy

- `test_multi_uczelnia_scoping.py` — Finding 1-4; woła rdzeń (2×) i
  `PokazImporty().get_queryset()`.
- `test_zapisz_do_bazy.py` — **11 testów** (`grep -c '^def test'` = 11); liczą
  callbacki `on_commit` po `task_on_commit` (`_reimport_scheduled`). **Wymaga
  przepisania — patrz Faza 2.**
- Call-site’y rdzenia bez `p`: `test_import_polon_core.py` (**6×**: linie
  33,45,112,160,206,241), `test_import_polon_override.py` (4×),
  `test_import_polon_ignoruj.py` (3×), `test_import_absencji_core.py` (2×),
  `test_multi_uczelnia_scoping.py` (2×).

---

## Docelowy stan (liveops)

### API liveops (zweryfikowane, wersja 0.4)

`LiveOperation` (`liveops/models.py`): pk UUID; `owner` (`related_name="+"`);
`created_on/started_on/finished_on`; `finished_successfully`,
`cancel_requested`, `cancelled`, `traceback`, `result_context`, `language`,
`status_text`, `percent`, `log`, `log_seq`, `current_stage`, `stage_states`;
klasowe `stages`, override `host_template_name`/`result_template_name`.
Kontrakt: `run(self,p)`, `on_restart()`. Kanał `liveop.<pk>`, `op_type_key()`
= `<app_label>.<model_name>`. `get_absolute_url()` → `liveops:live`.
`enqueue()` przy `RUNNER="celery"` → `_celery_task.delay(...)` **bez**
`transaction.on_commit`.

`Progress` (`liveops/progress.py`): `status`, `percent` (throttle),
`track(iterable, total, label)` (throttle + `check_cancelled` per item), `log`,
`stage(name)`, `result(ctx, **extra)`, `error(msg)`. **`check_cancelled()`
(linia 154) woła `refresh_from_db(fields=["cancel_requested"])`** — istotne dla
Fazy 1 (legacy `Operation` nie ma tego pola). `MockProgress`
(`liveops/testing.py`) — nagrywa, finalizuje, bez throttle, `check_cancelled`
no-op.

Runner (`liveops/runner.py`): `task_run` ustawia `started_on`, woła `run(p)`,
auto-finalizuje, łapie `OperationCancelled`/wyjątki (zapis `traceback`).

Widoki (`liveops/views.py`): `CreateLiveOperationView`, `LiveOperationListView`,
generyczne `LiveOperationView`/`CancelView`/`RestartView` (owner-scope, bramka
`REQUIRED_GROUP` = no-op gdy nieustawione). Consumer robi `send_snapshot()`
na connect.

---

## Migracja modelu

Oba modele przechodzą z `Operation` na `LiveOperation`. **NIE modyfikujemy
migracji 0001-0016** — nowa `0017_*`, POWIELAJĄCA na dwa modele deltę z
`import_pracownikow/migrations/0010_liveops.py`:

- `AlterModelOptions`: `ordering` `["-last_updated_on"]` → `["-created_on"]`.
- `RemoveField last_updated_on` (jedyny konsument to sortowanie listy —
  `PokazImporty` przechodzi na `-created_on`; **zweryfikowano grepem: żaden kod
  nie czyta `user.importplikupolon_set` / `importplikuabsencji_set` ani
  `.last_updated_on` POLON-a poza `plik_polon.py:69`**).
- `AddField` ×10 (pola liveops z defaultami).
- `AlterField owner` → `related_name="+"` (tylko stan migracji, bez SQL).

Pola wspólne (`id`, `created_on`, `started_on`, `finished_on`,
`finished_successfully`, `traceback`) mają identyczne definicje → brak operacji.
pk zostaje UUID → URL-e `<uuid:pk>` bez zmian. Po zmianie modeli uruchomić
`uv run python src/manage.py makemigrations --check`. **Baseline: NIE odświeżać
w tym branchu** (dopiero przy scalaniu).

---

## Fazy (przyrostowe, TDD) — 4 fazy

> Atomowość: `ImportPlikuPolon` i `ImportPlikuAbsencji` dzielą klasę bazową,
> jedną migrację, wspólny plik widoków ORAZ wspólny `ZapiszDoBazyMixin`.
> Cutover bazy modelu USUWA z użycia `mark_reset`/`task_perform`/`get_url`, więc
> **cała warstwa widoków + `ZapiszDoBazyMixin` + jego testy muszą przejść w
> TYM SAMYM commicie/PR** co model — inaczej `test_zapisz_do_bazy.py` (11
> testów) jest czerwony między fazami. Dlatego Faza 2 to JEDEN zielony cutover
> obejmujący również dry-run→zapisz.

### Faza 1 — rdzeń przyjmuje `Progress` (stary model działa dalej)

- `core/import_polon.py::analyze_file_import_polon(fn, parent_model, p)` —
  dodać wymagany `p`. `send_progress(...)` → pętla
  `for … in p.track(list(enumerate(records)), total=total, label="Import
  POLON")`; `send_notification(err,"error")` → `p.log(err)` (potem `raise`).
- `core/import_absencji.py::analyze_file_import_absencji(fn, parent_model, p)` —
  analogicznie.
- **Most zgodności = LOKALNA podklasa `Progress` FORWARDUJĄCA do legacy API,
  NIE `TextProgress` i NIE pusty no-op.** Legacy `Operation` nie ma pola
  `cancel_requested`, a `Progress.track` woła `check_cancelled()` →
  `refresh_from_db(fields=["cancel_requested"])` (`liveops/progress.py:154`) → w
  realnej ścieżce celery byłby `ValueError` (unit-testy z `MockProgress` by to
  przegapiły) — dlatego `check_cancelled` nadpisujemy na **no-op** (fix awarii
  zostaje). Ale pozostałych emiterów NIE zerujemy: skoro Fazy 1 i 2 mogą trafić
  osobno, czysty no-op wygasiłby pasek postępu na starej stronie details między
  nimi (zielone testy, regresja behawioralna). Most FORWARDUJE do legacy:
  `_emit_percent(v) → parent_model.send_progress(v)`,
  `log(line) → parent_model.send_notification(line, "info")`
  (i `status`/`error` analogicznie). Cała klasa oraz linia w `perform()` znikają
  w Fazie 2.
- Zaktualizować test-call-site’y rdzenia na `MockProgress(model)`:
  `test_import_polon_core.py` (6×), `test_import_polon_override.py` (4×),
  `test_import_polon_ignoruj.py` (3×), `test_import_absencji_core.py` (2×),
  `test_multi_uczelnia_scoping.py` (2×).

Gate Fazy 1 (zielone): `uv run pytest
src/import_polon/tests/test_import_polon_core.py
src/import_polon/tests/test_import_polon_override.py
src/import_polon/tests/test_import_polon_ignoruj.py
src/import_polon/tests/test_import_absencji_core.py
src/import_polon/tests/test_multi_uczelnia_scoping.py`.

### Faza 2 — atomowy cutover (model + widoki + URL + szablony + zapisz-do-bazy)

Model (`models.py`) — wzór `import_pracownikow/models.py:72,251-345`:
- `ImportPlikuPolon(LiveOperation)`, `ImportPlikuAbsencji(LiveOperation)` —
  usunąć importy `Operation`/`ASGINotificationMixin` + lokalny most z Fazy 1.
- `perform()`→`run(self, p)`: woła rdzeń z `p`, finalizuje
  `p.result({"total": self.get_details_set().count()})`; obudowa
  `try/except: traceback.print_exc(); rollbar.report_exc_info(); raise`.
- `on_reset()`→`on_restart()`.
- Dodać `reset_liveops_state()` + `_POLA_LIVEOPS_RESET`
  (kopia `import_pracownikow/models.py:306-345`).
- Nazwy szablonów: `class_to_snake("ImportPlikuPolon") = "import_pliku_polon"`
  (nie `importplikupolon`!). **Ustawić jawne `host_template_name` /
  `result_template_name`** albo utworzyć pliki pod auto-nazwą — byle spójnie.
- Migracja `0017_*` (patrz „Migracja modelu"); `makemigrations --check`.

Widoki (`views/plik_polon.py`, `plik_absencji.py`):
- Usunąć importy `long_running.views`.
- `PokazImporty(GroupRequiredMixin, ListView)` — `model=ImportPlikuPolon`,
  `group_required="wprowadzanie danych"`; `get_queryset` = owner-scope +
  `order_by("-created_on")` + **zachować** zawężenie multi-hosted + per-uczelnia
  trim (wzór ListView `import_pracownikow/views.py:118-133`). Analogiczny
  `PokazImportyAbsencji`; **przy okazji naprawić `index-absencji`** (patrz Faza 4
  — bugfix + newsfragment).
- `UtworzImportPlikuPolon(GroupRequiredMixin, CreateLiveOperationView)` —
  `form_valid` ustawia TYLKO `form.instance.uczelnia =
  Uczelnia.get_for_request(request)` i woła `return super().form_valid(form)`;
  reszta (owner + `form.save()` + `enqueue()` + redirect na `get_absolute_url`)
  robi bazowe `CreateLiveOperationView.form_valid` (`liveops/views.py:101-105`).
  **Uwaga o cytacie**: `import_pracownikow.NowyImportView.form_valid`
  (`views.py:160-174`) świadomie NIE wywołuje `super()`/`enqueue()` — przekierowuje
  na krok mapowania — więc to NIE jest wzór na enqueue; wzorem enqueue jest
  bazowa metoda liveops. `UtworzImportPlikuAbsencji` bez `uczelnia` — może użyć
  gołego `CreateLiveOperationView`.
- `ImportPolonResultsView(GroupRequiredMixin, ListView)` — owner-scope przez
  `parent_object` (`get_object_or_404(..., owner=request.user)`). **Ostrożnie z
  wzorem `import_pracownikow/views.py:650-667`**: on podaje w kontekst
  `parent_object=` (NIE `object=`) i NIE ma `paginate_by`. POLON-owy
  `wierszimportuplikupolon_list.html` renderuje `{% url … object.pk %}` (~176)
  i stronicowanie (~339,394), więc widok MUSI mieć:
  - `paginate_by = 25` (inaczej cicha utrata paginacji — tysiące wierszy na
    jednej stronie; testy tego NIE łapią),
  - `get_context_data(object=self.parent_object, …)` (inaczej `NoReverseMatch`
    na `object.pk` — testy łapią),
  - zachowany dotychczasowy `filter_form` + kontekst `unmatched_autor_dyscyplina`
    (`unmatched_count`), które obecny `ImportPolonResultsView` już buduje.
  Absencji analogicznie (`object=self.parent_object` + `paginate_by=25` pod
  `wierszimportuplikuabsencji_list.html`).
- **Usunąć** `ImportPolonRouterView`, `ImportPolonDetailsView` + absencyjne
  odpowiedniki. `RestartImportView` (POLON + absencji) NIE usuwać ślepo —
  **zastąpić** gejtowanym wariantem opartym na liveops `RestartView` (patrz
  „Restart" niżej).
- **`ZapiszDoBazyMixin` — przepisać (owner-scope BEZ `long_running`)**:
  - dziedziczenie: `LoginRequiredMixin` + `DetailView`/`SingleObjectMixin`;
    owner-scope przez własny `get_queryset` = `self.model.objects.filter(
    owner=self.request.user)` (zastępuje `RestrictToOwnerMixin` z
    `long_running.views`) — po to, by Faza 4 „brak importów long_running"
    przeszła.
  - GET bez zmian (`potwierdz_zapis_do_bazy.html`).
  - POST (`@transaction.atomic` + `select_for_update`) — guard bez zmian
    (`finished_successfully and not zapisz_zmiany_do_bazy`), ale zamiast
    `mark_reset()` + `task_on_commit`:
    ```
    self.object.zapisz_zmiany_do_bazy = True
    self.object.on_restart()                      # kasuje wiersze-dzieci
    pola = self.object.reset_liveops_state()
    self.object.save(update_fields=["zapisz_zmiany_do_bazy", *pola])
    transaction.on_commit(self.object.enqueue)     # patrz Ryzyko #2
    ```
  - **`HttpResponseRedirect("..")` (obecnie linia 48) → `HttpResponseRedirect(
    self.object.get_absolute_url())`** (stary „.." = router URL kasowany w tej
    fazie → 404).
  - `ZapiszDoBazyImportView`/`ZapiszDoBazyImportAbsencjiView` zostają z
    `GroupRequiredMixin` (bramka grupy).

URL-e (`urls.py`): usunąć `*-router|details` (POLON + absencji); **zostawić
`*-restart`** (teraz celuje w gejtowany `_PkOwnerRestartMixin`, POST); zostawić
`index`, `utworz-import`, `*-results`, `*-zapisz-do-bazy`, `index-absencji`,
`utworz-import-absencji`.

`views/__init__.py`: nadal star-import obu modułów (bez zmiany struktury), ale
zweryfikować, że nic z zewnątrz nie importuje po imieniu usuniętych klas
(router/details/restart) — gwiazdka podąża za zawartością modułów, więc
usunięcie klas wystarcza; sprawdzić importy w innych appach/urls.

Szablony:
- Host `import_polon/import_pliku_polon.html` (+ absencji) — wzór DOSŁOWNY
  `import_pracownikow/templates/import_pracownikow/import_pracownikow.html`:
  `{% extends "base.html" %}`, `{% load static liveops %}`, breadcrumbs, i
  **OBOWIĄZKOWO wrapper CSRF** (bo `CSRF_COOKIE_HTTPONLY=True`):
  ```
  <div hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
      {% live_operation object %}
  </div>
  <script src="{% static 'liveops/vendor/htmx.min.js' %}"></script>
  <script src="{% static 'channels_broadcast/js/notifications.js' %}"></script>
  <script src="{% static 'liveops/liveops.js' %}"></script>
  ```
  (kolejność skryptów istotna).
- Result `import_polon/import_pliku_polon_result.html` (+ absencji) — panel
  „zakończono" + link `{% url "import_polon:importplikupolon-results"
  operation.pk %}`. **Liczniki z `operation.get_details_set()`**, NIE tylko z
  `result_context` (stare importy mają `result_context=NULL` — patrz Ryzyko #3).
- `importplikupolon_list.html`: link → `{{ object.get_absolute_url }}`,
  zachować `{{ object.uczelnia }}`.
- **NOWY** `import_polon/importplikuabsencji_list.html` — dziś `index-absencji`
  pożycza `importplikupolon_list.html` (bo mapuje na `PokazImporty`); po
  wydzieleniu `PokazImportyAbsencji(ListView)` nie ma szablonu listy absencji →
  `TemplateDoesNotExist`. Utworzyć osobny szablon: link wiersza →
  `{{ object.get_absolute_url }}`, przycisk „utwórz nowy import" →
  `{% url "import_polon:utworz-import-absencji" %}` (bez pola `uczelnia`).
- `wierszimportuplikupolon_list.html` / `…absencji_list.html`: usunąć
  `{% include "long_running/operation_details.html" %}` + toggle JS. Zachować
  przycisk „zapisz do bazy".
- `potwierdz_zapis_do_bazy.html`: **link Anuluj `href=".."` →
  `href="{{ object.get_absolute_url }}"`** (stary „.." = router URL → 404).
- Usunąć `importplikupolon_detail.html`, `importplikuabsencji_detail.html`.

Restart — **gejtowany grupą** (precedens #508 F4). Centralny `liveops:restart`
gejtuje tylko gdy `LIVEOPS["REQUIRED_GROUP"]` ustawione — w BPP NIE jest
(`liveops/views.py:50-59` → no-op), a legacy `RestartImportView` siedział za
grupą „wprowadzanie danych" (`plik_polon.py:104`). Restart z
`zapisz_zmiany_do_bazy=True` PONOWNIE zapisuje do bazy, więc nie zostawiamy go
owner-only. Dodać (wzór `import_pracownikow/views.py:1386-1404`) mały
`_PkOwnerRestartMixin(GroupRequiredMixin, RestartView)` (owner-scope +
`group_required="wprowadzanie danych"`) i gejtowane widoki restartu POLON +
absencji, wpięte pod własne URL-e restartu (przywrócić `*-restart`), a przycisk
restartu na host-page kierować na nie (a nie na centralny `liveops:restart`).
Dodać test bramki (wzór `import_pracownikow/tests/test_auth_gate.py`): user bez
grupy → POST restart nie zmienia stanu; z grupą → przechodzi.

Testy Fazy 2 (nowe + przepisane, wszystko zielone na koniec):
- `test_run_finalizuje_polon` / `…_absencji` — `op.run(MockProgress(op))` na
  fixture-pliku: `finished_successfully`, `result_context`, wiersze utworzone.
- `test_liveops_live_view_renderuje_host` — `op.get_absolute_url() ==
  "/live/import_polon.importplikupolon/<pk>/"`; GET (admin) 200; treść zawiera
  `data-liveop-channel`, `data-liveop-token` ORAZ `X-CSRFToken` (wrapper).
- **Przepisany `test_zapisz_do_bazy.py` (11 testów)** — patrz „Strategia testów".
- `test_restart_bez_grupy_nie_zmienia_stanu` / `…_z_grupa_przechodzi` (wzór
  `import_pracownikow/tests/test_auth_gate.py`) — bramka grupy na restarcie.
  **Asercja przez EFEKT UBOCZNY, NIE po kodzie 403**: braces
  `GroupRequiredMixin` ma domyślnie `raise_exception=False` (żaden widok BPP nie
  ustawia inaczej), więc zalogowany user bez grupy dostaje **302 →
  redirect_to_login**, a nie 403. Sprawdzać: operacja NIE została zresetowana /
  re-run (stan bez zmian, wiersze-dzieci nietknięte) — ewentualnie dodatkowo
  `status_code == 302`; NIGDY nie asertować 403 (strażnik #508 F4 też idzie po
  efekcie ubocznym, nie po kodzie).
- Zielone bez zmian merytorycznych: całe `test_multi_uczelnia_scoping.py`
  (get_queryset po `-created_on`; membership bez zmian),
  `test_widok_tworzacy_przypina_uczelnie` (POST create — `enqueue()` w
  `form_valid` jest SYNCHRONICZNE przy eager, więc import realnie biegnie;
  sprawdzić że `run()` domyka na fixture-danych).

### Faza 3 — polish live UI (opcjonalnie)

- `stages` + `with p.stage(...)` (stepper; wzór
  `import_pracownikow/models.py:270-284`). Niewymagane funkcjonalnie.
- `get_success_url()` — domyślnie None (zostaje na stronie live z wynikiem).

### Faza 4 — sprzątanie + newsfragmenty

- Grep: `import_polon` nie importuje `long_running` ani `ASGINotificationMixin`;
  brak martwych URL-name.
- **NIE** usuwać `long_running`, autoryzatora, `CHANNELS_BROADCAST_*`.
- **`admin.py` / `apps.py` — bez zmian** (`admin.py` rejestruje tylko
  `ImportPolonOverride`; nie dotyka Operation/liveops) — executor nie musi ich
  ruszać.
- **DWA newsfragmenty** w `src/bpp/newsfragments/`:
  - `<slug>.feature.rst` — „Import POLON i absencji na django-liveops
    (live-progress WebSocket + HTMX)".
  - `<slug2>.bugfix.rst` — **naprawa `index-absencji`**: dziś strona „absencje"
    (`urls.py:35`) pokazuje listę importów POLON zamiast absencji; Faza 2
    przepina `index-absencji` na `PokazImportyAbsencji`. To osobna,
    user-widoczna poprawka → osobny fragment.

---

## Zachowanie do utrzymania (checklista + strażnicy)

| Zachowanie | Gdzie | Test-strażnik |
|-----------|-------|---------------|
| Multi-hosted: raport niezmatchowanych | `ImportPlikuPolon.autorzy_niezmatchowani` (bez zmian) | `test_multi_uczelnia_scoping.py::test_autorzy_niezmatchowani_*` |
| Multi-hosted: walidacja ZATRUDNIENIE | `core/import_polon.py::validate_zatrudnienie_...` | `..::test_walidacja_zatrudnienia_zawezona_do_uczelni_importu` |
| Multi-hosted: guard mutacji obcej uczelni | `core/import_polon.py::autor_z_innej_uczelni` | `..::test_import_nie_modyfikuje_autora_innej_uczelni` |
| Lista zawężona do uczelni + `uczelnia=None` wstecz | `PokazImporty.get_queryset` (ListView) | `..::test_lista_importow_zawezona_*`, `_bez_rozstrzygnietej_*` |
| Create przypina `uczelnia` | `UtworzImportPlikuPolon.form_valid` | `..::test_widok_tworzacy_przypina_uczelnie_z_requestu` |
| Label uczelni na liście | `importplikupolon_list.html` | (wizualny) |
| Dry-run → zapisz (flip + reset + re-run) | `ZapiszDoBazyMixin.post` | `test_zapisz_do_bazy.py` (przepisany) |
| Guardy zapisu (zapisany/błąd/w-trakcie/404) | `ZapiszDoBazyMixin.post` | `test_zapisz_do_bazy.py::*guard*`, `*other_user_404` |
| Reset kasuje wiersze-dzieci | `on_restart()` | `..::test_zapisz_do_bazy_polon_post_deletes_child_rows` |
| Przycisk „zapisz" tylko dla dry-run | `wierszimportuplikupolon_list.html` + results | `..::test_results_page_shows_button`, `_hides_button` |
| Routing details/results/restart | `liveops:live/restart` + `*-results` | nowy `test_liveops_live_view_*` |

Bramka grupy: `LIVEOPS` **nie ma** `REQUIRED_GROUP`, więc centralne
`liveops:live`/`:cancel` są tylko owner-scoped. Grupa „wprowadzanie danych"
nadal bramkuje create/list/results/zapisz (`GroupRequiredMixin`) ORAZ **restart**
(gejtowany `_PkOwnerRestartMixin`, patrz Ryzyko #5 — restart jest destrukcyjny).
Utworzyć import może tylko członek grupy, a live/wynik widzi tylko właściciel →
brak regresji. **Nie** ustawiać `REQUIRED_GROUP` globalnie (zbramkowałoby
deduplikator i inne liveopsy).

---

## Strategia testów

- **`transaction.on_commit` w testach pytest-django NIE odpala się** (test biegnie
  w rollbackowanej transakcji), chyba że użyjesz
  `django_capture_on_commit_callbacks(execute=True)`. Wcześniejsze (v1)
  stwierdzenie „eager + on_commit → import biegnie w teście" było BŁĘDNE dla
  ścieżki zapisz-do-bazy (tam enqueue jest w `on_commit`).
  - Ścieżka **create** (`enqueue()` wołane wprost w `form_valid`, poza
    `on_commit`) JEST synchroniczna przy eager — `test_widok_tworzacy_*` realnie
    uruchamia import.
  - Ścieżka **zapisz-do-bazy** (`transaction.on_commit(enqueue)`):
    - guard-testy (stan bez zmian) → `django_capture_on_commit_callbacks()`
      BEZ `execute` i asercja, że lista callbacków enqueue jest pusta / że stan
      nie ruszył;
    - „re-run faktycznie przetworzył wiersze" → `…(execute=True)` żeby
      wymusić enqueue (przy eager wykona się synchronicznie po commicie);
    - flip-flag + reset stanu (`zapisz_zmiany_do_bazy=True`, `started_on`/
      `finished_on` None, dzieci skasowane) sprawdzać PRZED wykonaniem enqueue
      (capture bez execute) — inaczej re-run znów je ustawi.
- Faza 1: rdzeń zielony z `MockProgress` (gate: core+override+ignoruj+absencji+
  multi_uczelnia).
- Faza 2: nowe `test_run_finalizuje_*`, `test_liveops_live_view_*`; regresja:
  `test_multi_uczelnia_scoping.py`, `test_widok_tworzacy_*`; przepisany
  `test_zapisz_do_bazy.py`.
- Zielone bez zmian merytorycznych (poza `p`): `test_update_rodzaj_autora.py`,
  `test_import_polon_validation.py`, `test_utils.py`.
- Komendy: `uv run pytest src/import_polon/tests/ -q` (Docker daemon dla
  testcontainers; RUNNER=eager z `settings/test.py`).

---

## Ryzyka i pytania otwarte

1. **Migracja 0017 (oba modele naraz).** `owner related_name="+"` (AlterField
   bez SQL) — zgrepowano, brak użyć reverse accessora. `last_updated_on` znika
   (jedyny konsument: sortowanie listy → `-created_on`). `makemigrations
   --check` po zmianie. Baseline dopiero przy scalaniu.
2. **Celery enqueue w bloku `@transaction.atomic` (zapisz-do-bazy).**
   `enqueue()` przy `RUNNER="celery"` woła `.delay()` bez `on_commit` — w bloku
   atomic worker mógłby czytać stan sprzed commitu. Rozwiązanie:
   `transaction.on_commit(self.object.enqueue)`. Konsekwencja: przepisanie
   `test_zapisz_do_bazy.py` (patrz „Strategia testów").
3. **Snapshot/result dla STARYCH importów (`result_context=NULL`).** Result-
   template musi liczyć z `operation.get_details_set()`. Nazewnictwo:
   `class_to_snake("ImportPlikuPolon")="import_pliku_polon"` — pliki host/result
   pod tą nazwą albo jawne `host_template_name`/`result_template_name`.
4. **CSRF.** `CSRF_COOKIE_HTTPONLY=True` (base.py:1596) → bez wrappera
   `hx-headers` przyciski Anuluj/Ponów na host-page dają 403. Wrapper
   obowiązkowy (wzór `import_pracownikow.html:27`).
5. **Bramka grupy na restarcie — GEJTUJEMY (nie owner-only).** Centralny
   `liveops:restart` gejtuje tylko przy ustawionym `REQUIRED_GROUP`
   (`liveops/views.py:50-59`), którego BPP nie ustawia → owner-only. Ale restart
   z `zapisz_zmiany_do_bazy=True` PONOWNIE zapisuje do bazy, a legacy
   `RestartImportView` był za grupą „wprowadzanie danych" (`plik_polon.py:104`).
   Projekt uznał to już za dziurę przy `import_pracownikow` (#508 F4:
   `_PkOwnerRestartMixin(GroupRequiredMixin, RestartView)`,
   `views.py:1386` + `test_auth_gate.py`). **Decyzja: powielić ten wzór dla
   POLON + absencji** (własny gejtowany widok restartu pod `*-restart`, przycisk
   host-page celuje w niego) zamiast akceptować owner-only. `cancel` (nie-
   destrukcyjny) może zostać owner-only na centralnym `liveops:cancel`.
6. **`notify_list_changed` / auto-refresh listy.** Własna `PokazImporty` nie ma
   liveops-owego JS list-live → lista nie odświeży się sama (jak dziś). Bez
   regresji.
7. **Token TTL 24h** — POLON mieści się; snapshot-on-connect pokrywa reconnect.
   Niskie ryzyko.
8. **Faza 1 most zgodności.** Musi być LOKALNY no-op `Progress` (nie
   `TextProgress`) — inaczej `check_cancelled → refresh_from_db(["cancel_
   requested"])` na legacy `Operation` rzuci `ValueError` w realnej ścieżce
   celery (unit-testy z `MockProgress` by to przegapiły).
9. **Koordynacja z gałęzią `feat/liveops-import-list-ministerialnych`.** Jest
   otwarta i też migruje importer na liveops. Przy scalaniu OBU:
   (a) potencjalny konflikt baseline (`baseline-sql/baseline.sql` — jeden wielki
   plik, odświeżać raz, przy merge); (b) obie dodają migracje/newsfragmenty —
   niezależne katalogi, więc same fragmenty nie kolidują, ale baseline tak.
   Uzgodnić kolejność scalania.
10. **`index-absencji` (urls.py:35).** Dziś mapuje na listę POLON — user-
    widoczny bug; Faza 2 naprawia (osobny newsfragment bugfix).

---

## Czego NIE robić

- **NIE** modyfikować migracji `import_polon/0001-0016` — tylko `0017`.
- **NIE** odświeżać baseline w tym branchu.
- **NIE** usuwać `long_running`, `long_running/authorizers.py`,
  `CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER`.
- **NIE** ustawiać `LIVEOPS["REQUIRED_GROUP"]`.
- **NIE** ruszać wspólnych plików `long_running/*`.
- **NIE** cytować `import_list_ministerialnych` jako „w drzewie" — nie jest
  scalony; wzór kanoniczny to `import_pracownikow`.

---

## Zmiany względem v2 (v3, dla recenzenta)

- **Results views (MAJOR)**: jawny wymóg `paginate_by = 25` +
  `get_context_data(object=self.parent_object, …)` dla POLON i absencji —
  ślepe skopiowanie `import_pracownikow` (`parent_object=`, brak paginacji)
  dałoby `NoReverseMatch` na `object.pk` (~176) i cichą utratę stronicowania.
- **Bugfix `index-absencji` (MAJOR)**: dodano wymóg utworzenia NOWEGO
  `importplikuabsencji_list.html` — bez niego wydzielony `PokazImportyAbsencji`
  daje `TemplateDoesNotExist`.
- **Restart gejtowany (MINOR 5)**: Ryzyko #5 zmienione z „owner-only OK" na
  „GEJTUJEMY grupą" (`_PkOwnerRestartMixin` + auth-gate test; precedens #508 F4);
  `*-restart` URL zostaje; zaktualizowano sekcje Widoki/URL/Zachowanie/Testy.
- **Faza 1 most (MINOR 3)**: nie czysty no-op — forwarduje do legacy
  `send_progress`/`send_notification` (żeby nie wygasić paska między fazami);
  `check_cancelled` nadal no-op (fix awarii zostaje).
- **Liczba testów (MINOR 4)**: `test_zapisz_do_bazy.py` = **11**, nie 13
  (poprawione wszędzie).
- **Cytat create (NIT 6)**: `UtworzImportPlikuPolon.form_valid` = ustaw
  `uczelnia` + `super().form_valid()`; enqueue robi bazowe
  `CreateLiveOperationView.form_valid` (`liveops/views.py:101-105`) — a nie
  `NowyImportView` (`:160-174`), które celowo NIE enqueue’uje.

## Zmiany względem v1 (dla recenzenta)

- **Referencje**: `import_list_ministerialnych` przeniesiony do „NIE scalony"
  (zweryfikowane: `models.py:10` = Operation, migracje do 0008, nie-przodek
  dev); wzór kanoniczny → `import_pracownikow` (migracja `0010_liveops.py`,
  host `import_pracownikow.html`).
- **Fazy**: dry-run→zapisz (`ZapiszDoBazyMixin` + przepisanie
  `test_zapisz_do_bazy.py`) wciągnięte do atomowej Fazy 2 (było osobną fazą, co
  dawało 13 czerwonych testów między fazami). Fazy: 5 → **4**.
- **Redirecty**: dopisany fix `HttpResponseRedirect("..")` → `get_absolute_url()`
  (POST zapisu) i link Anuluj w `potwierdz_zapis_do_bazy.html`.
- **CSRF**: dodany obowiązkowy wrapper `hx-headers` (CSRF_COOKIE_HTTPONLY).
- **Faza 1 most**: `TextProgress` → LOKALNY no-op Progress (pole
  `cancel_requested`).
- **Strategia testów**: skorygowany błąd o `on_commit` w testach
  (`django_capture_on_commit_callbacks(execute=True)`); poprawiona liczba
  call-site’ów rdzenia (6, nie 3) i rozszerzony gate Fazy 1.
- **ZapiszDoBazyMixin owner-scope**: dopisane, czym zastąpić
  `RestrictToOwnerMixin` z `long_running`.
- **Gapy**: drugi newsfragment (bugfix `index-absencji`), nota o
  `views/__init__.py`, nota że `admin.py`/`apps.py` bez zmian, koordynacja z
  otwartą gałęzią liveops-list-ministerialnych.
