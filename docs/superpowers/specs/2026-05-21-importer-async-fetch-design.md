# Spec: Asynchroniczny Fetch + Create w wizardzie `importer_publikacji`

Data: 2026-05-21
Branch: `feat/importer-async-fetch`
Worktree: `~/Programowanie/bpp-importer-async`

## 1. Problem

Wizard importu publikacji (`src/importer_publikacji/views/wizard.py`) ma
dwa kroki, w których kliknięcie przycisku blokuje request HTTP na
dziesiątki sekund:

1. **Fetch** (`FetchView.post`, wizard.py:97–207) — po podaniu DOI /
   identyfikatora wywołuje synchronicznie:
   - `provider.fetch(normalized)` — 1× HTTP call do CrossRef/OpenAlex/
     DSpace/PBN/WWW providera (sekundy, czasem dziesiątki),
   - `_auto_match_authors(session, result.authors, result.year)`
     (authors.py:68–108) — per autor: `Komparator.porownaj_author`
     (crossref_bpp/core.py:336–394) z ORCID lookup + `matchuj_autora`
     trigram + fallback `Autor.objects.filter(nazwisko__icontains,
     imiona__icontains)`, plus `_get_dyscyplina`. Dla artykułu w
     Cytokine z 50+ współautorami: setki query do PG.
   - `_prefill_dyscypliny_z_zgloszen` (authors.py:154–187) — kilka query
     + N save.

2. **Create** (`CreateView.post`, wizard.py:531–591) — synchronicznie
   tworzy rekord `Wydawnictwo_*`, autorów (`_add_authors_to_record`,
   publikacja.py:110–145, M× insertów + Autor_Jednostka), streszczenia,
   liczy punktację, opcjonalnie linkuje PBN. Dla 100 autorów potrafi
   przeciągnąć się do kilkudziesięciu sekund.

Skutek: user widzi przeglądarkę "wisi", bez feedbacku. Web worker
(gunicorn) jest zablokowany na ten czas, co przy 4 workerach i 30 s
operacji wystarczy żeby 5. user zobaczył timeout.

## 2. Cel

Wyciągnąć obie operacje do Celery tasków z:

- paskiem postępu (etapy + per-stage counter dla najwolniejszego etapu),
- user-friendly komunikatem błędu + automatycznym Rollbar reportem dla
  admina,
- przyciskiem "Spróbuj ponownie" przy błędzie,
- minimalną generyczną infrastrukturą (jeden widok statusu, jeden
  partial postępu) — dwa taski dziś, więcej w przyszłości bez
  duplikacji UI.

Pozostawić wszystkie pozostałe kroki wizard-a synchroniczne — pracują
na danych z DB i nie potrzebują tła.

## 3. Architektura (Approach B)

### 3.1 Nowe pliki

- `src/importer_publikacji/tasks.py` — dwa task-i `@shared_task(bind=
  True)`:
  - `fetch_session_task(self, session_id, request_user_id)`
  - `create_publication_task(self, session_id, request_user_id,
    also_pbn)`
- `src/importer_publikacji/views/task_status.py` — `ImportTaskStatusView`
  (jeden parametryzowany widok, używany dla obu tasków).
- `src/importer_publikacji/views/retry.py` — `ImportTaskRetryView` (POST)
  resetujący sesję i enqueueujący zadanie ponownie.
- `src/importer_publikacji/progress.py` — czysta funkcja
  `report_progress(task, stage_code, sub_current=0, sub_total=1)` która
  na podstawie tabeli wag etapów konwertuje (stage, sub_current,
  sub_total) na overall percent i woła `task.update_state(state=
  "PROGRESS", meta={...})`.
- `src/importer_publikacji/templates/importer_publikacji/step_task_
  status.html` — pełna strona (extends index.html style), HTMX poll co
  3 s.
- `src/importer_publikacji/templates/importer_publikacji/partials/
  task_progress.html` — Foundation progress meter + stage label + per-
  stage counter.
- `src/importer_publikacji/templates/importer_publikacji/partials/
  task_error.html` — callout `alert` + user-friendly message + przycisk
  retry (POST do `retry` endpointu) + `<details>` z tracebackiem dla
  `request.user.is_superuser`.
- `src/importer_publikacji/migrations/0007_async_import_state.py` —
  zależy od `0006_merge_20260421_1100`.
- Testy: `src/importer_publikacji/tests/test_tasks.py`,
  `test_views_task_status.py`, `test_views_retry.py`,
  `test_progress.py`. Aktualizacje istniejących `test_views.py` (asercje
  o tym, że POST FetchView/CreateView nie wykonuje pracy inline, tylko
  enqueueuje task).

### 3.2 Zmiany w istniejących plikach

- **`src/importer_publikacji/models.py`** (`ImportSession`):
  - Dodanie do `Status` choices (po `FETCHED`, przed `VERIFIED`):
    - `FETCHING = "fetching", "Trwa pobieranie"`
    - `CREATING = "creating", "Trwa tworzenie rekordu"`
    - `IMPORT_FAILED = "import_failed", "Błąd importu"`
  - Nowe pola:
    - `celery_task_id = CharField(max_length=64, blank=True,
      default="")`
    - `last_error_message = CharField(max_length=255, blank=True,
      default="")`
    - `last_error_traceback = TextField(blank=True, default="")`
    - `last_failed_stage = CharField(max_length=16, blank=True,
      default="")` — wartość `"fetch"` lub `"create"`, do decyzji gdzie
      retry-ować.
  - `get_continue_url()` (models.py:150–157): nowe statusy mapowane do
    `task-status` (dla `FETCHING` / `CREATING`) i odpowiedniego kroku z
    callout-em błędu (dla `IMPORT_FAILED`).

- **`src/importer_publikacji/views/wizard.py:FetchView.post`** — zamiast
  inline-owej pracy: walidacja `FetchForm` zostaje synchroniczna,
  tworzy `ImportSession` z `status=FETCHING`, zapisuje `provider_name`,
  `identifier`, `created_by`. Enqueueuje `fetch_session_task.delay(
  session.pk, request.user.pk)`. Zapisuje `task.id` jako
  `session.celery_task_id`. Zwraca redirect (HTMX HX-Redirect dla
  HX-Request) na `ImportTaskStatusView` z `session_id`.

- **`src/importer_publikacji/views/wizard.py:CreateView.post`** — zamiast
  inline `_create_publication`: ustawia `session.status = CREATING`,
  zapisuje `celery_task_id`. Enqueueuje `create_publication_task.delay
  (session.pk, request.user.pk, "_create_and_pbn" in request.POST)`.
  Redirect na status view jak wyżej.

- **`src/importer_publikacji/templates/importer_publikacji/partials/
  session_list.html`** (linie 102–112) — dodać branche dla nowych
  statusów: `FETCHING` / `CREATING` → CSS class `warning`,
  `IMPORT_FAILED` → CSS class `alert`.

- **`src/importer_publikacji/urls.py`** — dwa nowe URL-e:
  - `task-status/<uuid:session_id>/` → `ImportTaskStatusView`
    (name="task-status")
  - `task-retry/<uuid:session_id>/` → `ImportTaskRetryView`
    (name="task-retry")

### 3.3 Stages i wagi

Wagi pozwalają obliczyć overall percent na podstawie stage i sub-
counter. Wartości są stałymi w `progress.py`:

```python
FETCH_STAGES = [
    # (code, label, weight)
    ("provider_fetch",  "Pobieram dane z dostawcy...",        10),
    ("create_session",  "Tworzę sesję importu...",             5),
    ("match_type_lang", "Dopasowuję typ publikacji i język...", 5),
    ("match_authors",   "Dopasowuję autorów ({current}/{total})...", 60),
    ("prefill_zgl",     "Wyszukuję zgłoszenia dla dyscyplin...", 20),
]

CREATE_STAGES = [
    ("verify",          "Weryfikuję dane publikacji...",        5),
    ("create_record",   "Tworzę rekord publikacji...",         10),
    ("add_authors",     "Zapisuję autorów ({current}/{total})...", 50),
    ("create_abstracts","Tworzę streszczenia...",               5),
    ("calc_score",      "Uzupełniam punktację ze źródła...",    10),
    ("link_pbn",        "Powiązanie z PBN...",                  20),
]
```

Overall percent = `(sum_of_completed_weights + current_stage_weight *
sub_current / sub_total) / sum_of_weights * 100`.

Per-stage counter pokazywany tylko gdy `total > 1` (czyli dla
`match_authors` i `add_authors`). Pozostałe stages renderują samą
etykietę bez `(M/N)`.

### 3.4 Anatomia taska

Pseudokod (`fetch_session_task`):

```python
@shared_task(bind=True)
def fetch_session_task(self, session_id, request_user_id):
    session = ImportSession.objects.get(pk=session_id)
    try:
        report_progress(self, "provider_fetch")
        provider = get_provider(session.provider_name)
        result = provider.fetch(session.identifier)
        if result is None:
            raise ProviderReturnedNothing("...")  # user-safe msg

        report_progress(self, "create_session")
        session.raw_data = result.raw_data
        session.normalized_data = {...}
        session.save()

        report_progress(self, "match_type_lang")
        # ... mapper + porownaj_language ...
        session.save()

        report_progress(self, "match_authors", 0, len(result.authors))
        for i, author_data in enumerate(result.authors):
            _auto_match_single_author(session, author_data, i,
                                       result.year)
            report_progress(self, "match_authors", i + 1,
                            len(result.authors))

        report_progress(self, "prefill_zgl")
        _prefill_dyscypliny_z_zgloszen(session)

        session.status = ImportSession.Status.FETCHED
        session.celery_task_id = ""
        session.save()
    except Exception:
        session.status = ImportSession.Status.IMPORT_FAILED
        session.last_failed_stage = "fetch"
        session.last_error_message = _user_safe_message(sys.exc_info())
        session.last_error_traceback = traceback.format_exc()
        session.save()
        raise  # @task_failure.connect → rollbar.report_exc_info()
```

`create_publication_task` analogicznie, ze stages z `CREATE_STAGES`.

Refactor: wyciągnięcie `_auto_match_single_author` z obecnego
`_auto_match_authors` (przeniesienie ciała pętli do osobnej funkcji)
żeby task mógł raportować postęp po każdej iteracji bez duplikacji
logiki. Stara funkcja `_auto_match_authors` zostaje jako thin wrapper
(używana w testach) — robi pętlę bez progress reporting.

### 3.5 Widok statusu (HTMX polling)

`ImportTaskStatusView.get(request, session_id)`:

**Source of truth dla "done/failed" to `session.status`**, nie
`AsyncResult.state`. Powód: race condition — task może być w stanie
`SUCCESS` w Redis chwilę zanim `session.save()` z `status=FETCHED`
zafiałduje się w DB. Polling dwa razy na sekundę i zobaczenie
"SUCCESS" z `session.status == FETCHING` skutkuje błędnym
przekierowaniem. AsyncResult używamy **tylko** do odczytu `task.info`
(meta progress).

1. Pobierz sesję.
2. Jeśli `session.status == IMPORT_FAILED`: renderuj
   `task_error.html` partial z `session.last_error_message`,
   przyciskiem retry, i opcjonalnym `<details>` z
   `session.last_error_traceback` dla superusera.
3. Jeśli `session.status` w `{FETCHED, COMPLETED, VERIFIED, ...}`
   (czyli każdy stan terminalny dla wcześniej-trwającego importu):
   HTMX response z `HX-Redirect` na `session.get_continue_url()`.
   Non-HTMX: zwykły `HttpResponseRedirect`.
4. Jeśli `session.status` w `{FETCHING, CREATING}`: pobierz
   `task = AsyncResult(session.celery_task_id)`. Renderuj
   `task_progress.html` z `task.info` (stage, current, total, progress).
   Jeśli `task.info` nie jest dict-em (task PENDING przed pierwszym
   `update_state`) — renderuj fallback "Inicjalizacja...".
5. Non-HTMX GET: pełna strona `step_task_status.html` z embedded
   partial-em (initial render).

Polling: `hx-get` na `#progress-container` z `hx-trigger="every 3s"`,
`hx-swap="innerHTML"`. Po zakończeniu task-a partial renderowany
przez view zawiera `HX-Redirect` header — HTMX wykonuje hard
navigation.

### 3.6 Retry

`ImportTaskRetryView.post(request, session_id)`:

1. Sprawdź `session.status == IMPORT_FAILED`.
2. Wyzeruj `last_error_*`, `last_failed_stage`.
3. W zależności od `last_failed_stage`:
   - `"fetch"` → wyzeruj `raw_data`, `normalized_data`, **usuń
     wszystkie powiązane `ImportedAuthor`y** (`session.authors.all().
     delete()`) — fetch może paść w połowie pętli `match_authors` i
     część rekordów już istnieje; retry musi startować od zera, żeby
     nie powstały duplikaty. Status = `FETCHING`. Enqueue
     `fetch_session_task`.
   - `"create"` → status = `CREATING`. Jeśli `_create_publication`
     padł w trakcie, `session.created_record_*` mogą wskazywać na
     niekompletny rekord (`_create_publication` jest `@transaction.
     atomic` — całość rollback-uje przy wyjątku, więc rekord nie
     powstaje), ale dla bezpieczeństwa: wyzeruj
     `created_record_content_type` i `created_record_id`. Enqueue
     `create_publication_task`.
4. Zapisz `celery_task_id`. Redirect na `task-status`.

### 3.7 Obsługa błędów

- Każdy task ma try/except wokół całej pracy. Wyjątek → ustawia
  `IMPORT_FAILED`, zapisuje `last_error_message` (user-safe),
  `last_error_traceback` (pełny), i `raise` — globalny
  `@task_failure.connect` w `src/django_bpp/celery_tasks.py:40-42`
  automatycznie wywoła `rollbar.report_exc_info()`. Nie wywołujemy
  Rollbara ręcznie w tasku.
- Mapping `_user_safe_message(exc_info)`:
  - `ProviderReturnedNothing` / `provider.fetch` zwrócił `None` →
    "Nie udało się pobrać danych z dostawcy. Sprawdź poprawność
    identyfikatora i spróbuj ponownie."
  - `requests.HTTPError` / timeout → "Dostawca danych nie odpowiada.
    Spróbuj za chwilę."
  - `ValidationError` → wiadomość z `e.messages`.
  - cokolwiek innego → "Wystąpił błąd podczas {fetch|create}.
    Administrator został powiadomiony."

### 3.8 Bezpieczeństwo i autoryzacja

- Widok status sprawdza, że `request.user == session.created_by` lub
  `request.user.is_superuser`. Powtarzamy obecny `ImporterPermissionMixin`.
- Retry endpoint analogicznie.
- `celery_task_id` to UUID Celery; nie wystawiamy go na zewnątrz w
  query stringu — żyje tylko w DB. URL statusu jest po `session_id`.

## 4. Data flow

```
[user POST DOI]
    ↓
FetchView.post
    ├─ FetchForm.is_valid()? nie → render z błędem (sync, jak teraz)
    ├─ create ImportSession(status=FETCHING)
    ├─ task = fetch_session_task.delay(session.pk, user.pk)
    ├─ session.celery_task_id = task.id; session.save()
    └─ redirect → ImportTaskStatusView(session_id)
                    ↓
                  GET (HTMX poll co 3s)
                    ├─ task PENDING → partial "Inicjalizacja..."
                    ├─ task PROGRESS → partial "stage + M/N + %"
                    ├─ task SUCCESS → HX-Redirect → session.get_continue_url()
                    └─ task FAILURE → partial "błąd + retry button"

[Celery worker]
    ↓
fetch_session_task
    ├─ session.refresh_from_db()
    ├─ try:
    │   ├─ report_progress("provider_fetch")
    │   ├─ result = provider.fetch(session.identifier)
    │   ├─ report_progress("create_session"); session.save()
    │   ├─ report_progress("match_type_lang"); session.save()
    │   ├─ report_progress("match_authors", 0, N)
    │   ├─ for i, author in authors:
    │   │   ├─ _auto_match_single_author(...)
    │   │   └─ report_progress("match_authors", i+1, N)
    │   ├─ report_progress("prefill_zgl")
    │   ├─ _prefill_dyscypliny_z_zgloszen(session)
    │   ├─ session.status = FETCHED; session.celery_task_id = ""
    │   └─ session.save()
    └─ except Exception:
        ├─ session.status = IMPORT_FAILED
        ├─ session.last_failed_stage = "fetch"
        ├─ session.last_error_message = _user_safe_message(...)
        ├─ session.last_error_traceback = traceback.format_exc()
        ├─ session.save()
        └─ raise  (→ @task_failure.connect → Rollbar)
```

Analogicznie dla `create_publication_task`.

## 5. Testowanie

- **`test_tasks.py`** (nowy):
  - `test_fetch_session_task_success` — mock provider, asseruj że
    `session.status == FETCHED`, `celery_task_id` clearowany,
    `update_state` wywołane z prawidłowymi etapami.
  - `test_fetch_session_task_provider_returns_none` — provider zwraca
    `None`. Asseruj: `status == IMPORT_FAILED`, `last_error_message`
    zawiera "dostawcy", `last_error_traceback` niepuste,
    `last_failed_stage == "fetch"`.
  - `test_fetch_session_task_provider_exception` — provider raises.
    Asseruj jak wyżej + sprawdź że `raise` propagowane (Celery zobaczy
    FAILURE).
  - `test_create_publication_task_success` — model_bakery sesja w stanie
    AUTHORS_MATCHED z autorami → task → `Wydawnictwo_*` istnieje,
    `session.status == COMPLETED`, autorzy podłączeni.
  - `test_create_publication_task_failure` — exception w
    `_create_publication`. Asseruj rollback (transakcja atomic),
    `status == IMPORT_FAILED`, `last_failed_stage == "create"`.
  - **Wszystkie testy w trybie `CELERY_TASK_ALWAYS_EAGER=True`** —
    egzekucja synchroniczna w teście (`pytest-celery` lub fixture).

- **`test_progress.py`** (nowy):
  - `test_report_progress_first_stage` — asseruj percent computed.
  - `test_report_progress_mid_stage_with_counter` — stage 4/5, current=
    25, total=50 → asseruj że meta zawiera prawidłowe pola i percent.
  - `test_report_progress_last_stage` — asseruj że ostatni etap
    osiąga 100% przy `sub_current == sub_total`.

- **`test_views_task_status.py`** (nowy): różne stany task-a (PENDING/
  PROGRESS/SUCCESS/FAILURE) → asercje na response (status code,
  content, HX-Redirect header). Mock `AsyncResult`.

- **`test_views_retry.py`** (nowy): POST retry resetuje pola błędu,
  enqueueuje task, redirect na task-status. Idempotency: retry na
  sesji nie-w-IMPORT_FAILED zwraca 400.

- **Aktualizacja `test_views.py`**:
  - Wszystkie testy które robiły `client.post(fetch_url, {...})` i
    asseruowały `session.normalized_data` / `authors.count()` muszą
    zmienić tryb: bo POST nie wykonuje pracy inline. Trzy opcje:
    (a) ustaw `CELERY_TASK_ALWAYS_EAGER=True` w conftest tej klasy →
    POST kończy się sync i istniejące asercje działają;
    (b) jawnie wywołaj `fetch_session_task(...)` po POST;
    (c) rozdziel testy: "test_fetch_view_enqueues_task" (asercja
    enqueueowania) + "test_fetch_session_task_does_work" (asercja na
    rezultacie).
    Preferowane: (c) — czyściej, mniej zależności od EAGER.

- **EAGER jest globalnie WŁĄCZONE pod testami** —
  `src/django_bpp/settings/base.py:335` ustawia
  `CELERY_TASK_ALWAYS_EAGER=True` + `CELERY_EAGER_PROPAGATES_
  EXCEPTIONS=True` gdy `TESTING`. Czyli `client.post(fetch_url, ...)`
  w teście **wykona task synchronicznie** (w tym samym procesie, tej
  samej transakcji). Istniejące testy w `test_views.py` które
  asseruowały rezultat po POST-cie — będą działać bez zmian. Preferowany
  kierunek aktualizacji to **(a)**: nie ruszać istniejących testów,
  dorzucić tylko nowe pokrycia (task_status view, retry, error path).
  EAGER means: można testować całość przez Django client, bez
  ręcznego wywoływania task-a, bez `mock.patch('...delay')`.

## 6. Co NIE jest w scope

- **Optymalizacja samego komparatora** (`Komparator.porownaj_author`,
  trigram + N icontains lookups). Cel tego specu to przerzucenie pracy
  na tło, nie przyspieszenie jej. Optymalizacja komparatora to osobny
  spec — kandydat: prefetch wszystkich Autor po roku + Python-side
  matching, ale to wymaga osobnej dyskusji o trade-offach.
- **"Miliard źródeł"** w Source step. Wspomniane w pierwotnym wątku
  jako odrębny problem (autocomplete widget). Osobne zadanie.
- **Cancel button** na widoku statusu. Task się skończy, ale to OK
  dla 30-sekundowych operacji. Jeśli kiedyś zechcemy cancel: `celery
  task.revoke(terminate=True)` + ustawienie `IMPORT_FAILED` z
  user-safe "Anulowano".
- **WebSocket / SSE**. HTMX polling co 3 s wystarczy.
- **Reuse infrastruktury w innych modułach** (np. `importer_autorow_
  pbn`). Robimy generyczność w obrębie `importer_publikacji`; jeśli
  inny moduł skorzysta — refactor do `long_running/` zrobimy wtedy.

## 7. Granica kompatybilności

- Migracja `0007_async_import_state` dodaje pola z `default=""` / nowe
  Status choices — nie wpływa na istniejące rekordy. Sesje aktualnie
  w stanie FETCHED/VERIFIED/etc. nadal działają normalnie.
- Stara funkcja `_auto_match_authors` zachowana jako thin wrapper —
  istniejące testy w `test_authors.py` nie wymagają zmian poza
  prawdopodobnym importem.

## 8. Otwarte ryzyka

- **Stale sesje w stanie FETCHING/CREATING gdy worker padnie**. Po
  restarcie workera Celery task ginie, `celery_task_id` w DB wskazuje
  na nieistniejący task. Mitigation: `ImportTaskStatusView` po
  detekcji `AsyncResult` w stanie PENDING (mimo że sesja FETCHING) +
  upłynął rozsądny TTL (np. 10 min od `last_updated`), traktuje jak
  IMPORT_FAILED z komunikatem "Zadanie nie zakończyło się w czasie.
  Spróbuj ponownie." User klika retry → nowy task.
- **Two tabs problem**. User otwiera dwie zakładki, w obu klika
  Fetch dla tej samej sesji (lub Create) — w drugiej zakładce
  Status sesji jest już CREATING. Mitigation: FetchView/CreateView
  sprawdza `session.status` przed enqueueowaniem; jeśli już
  FETCHING/CREATING — redirect na task-status bez nowego task-a.
