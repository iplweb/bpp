# PBN Import Cleanup — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Remove the dead WebSocket layer, fix view-layer log-loading
performance, fix three correctness bugs, and address two small smells in the
`pbn_import` app — without touching the legacy `pbn_integrator` command
(item 3 is blocked — see review).

**Architecture:** `pbn_import` is a thin UI/orchestration layer over the
`pbn_integrator` engine. All realtime currently runs through HTMX polling;
the parallel Channels/WebSocket path is dead. Changes are localized to
`pbn_import` plus one line-pair in `django_bpp/asgi.py`.

**Tech Stack:** Django, Django Channels (being partially removed), HTMX,
Celery, pytest + model_bakery.

**Branch:** `feature/pbn-import-cleanup` (worktree
`~/Programowanie/bpp-pbn-import-cleanup`) → PR into `feature/multi-hosted-config`.

**Testing:** `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest
src/pbn_import/tests/ -p no:cacheprovider` for targeted runs. The broader
suite is being stabilised on `feature/multi-hosted-config` by another agent;
keep changes green within `pbn_import`.

---

## Task 1: Remove the dead WebSocket / Channels layer

**Files:**
- Delete: `src/pbn_import/consumers.py`
- Delete: `src/pbn_import/routing.py`
- Delete: `src/pbn_import/tests/test_consumers.py`
- Delete: `src/pbn_import/tests/test_routing.py`
- Modify: `src/pbn_import/tasks.py` (remove `send_websocket_update`, the
  unused module-level `update_progress`, all WS calls, channels imports)
- Modify: `src/pbn_import/views.py` (remove `send_websocket_update` method
  at 303–308, its call at ~284, the `channels`/`async_to_sync` imports at 7)
- Modify: `src/pbn_import/templates/pbn_import/dashboard.html` (remove the
  `<script>` WebSocket block, ~449–486)
- Modify: `src/django_bpp/asgi.py` (drop `import pbn_import.routing` and the
  `+ pbn_import.routing.websocket_urlpatterns` term)
- Modify: `src/pbn_import/tests/test_tasks.py` (drop WS-specific assertions)

- [ ] **Step 1: Confirm the module-level `tasks.update_progress` is unused**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && grep -rn "tasks.update_progress\|from .tasks import update_progress\|from pbn_import.tasks import update_progress" src/`
Expected: no hits → safe to delete the function (lines ~33–57). If any hit
appears, keep the function but strip only its `send_websocket_update(...)`
call.

- [ ] **Step 2: Confirm `pbn_import.routing` is the only pbn websocket wiring
  and `channels_broadcast` still needs Channels**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && grep -n "routing\|websocket_urlpatterns" src/django_bpp/asgi.py`
Expected: both `channels_broadcast.routing` and `pbn_import.routing` are
summed. Only the `pbn_import.routing` term is removed; `channels_broadcast`
stays. Do NOT remove `CHANNEL_LAYERS` from settings.

- [ ] **Step 3: Delete the four files**

```bash
cd ~/Programowanie/bpp-pbn-import-cleanup
git rm src/pbn_import/consumers.py src/pbn_import/routing.py \
       src/pbn_import/tests/test_consumers.py src/pbn_import/tests/test_routing.py
```

- [ ] **Step 4: Edit `tasks.py`** — remove `from channels.layers import
  get_channel_layer`, `from asgiref.sync import async_to_sync` (only if now
  unused), the `send_websocket_update` function, the unused module-level
  `update_progress` function, and the three `send_websocket_update(...)`
  call sites (~48, ~124, ~156). Preserve all non-WS logic (status updates,
  Rollbar reporting, ImportLog writes, completion status persistence).

- [ ] **Step 5: Edit `views.py`** — remove the `send_websocket_update` method
  (303–308) and its caller (~284 in the import-start path), plus the
  `channels`/`async_to_sync` imports at top (verify no other use first:
  `grep -n "async_to_sync\|get_channel_layer" src/pbn_import/views.py`).

- [ ] **Step 6: Edit `dashboard.html`** — remove the `<script>` block that
  does `const ws = new WebSocket(...)` and its `switch(data.type)` handlers
  (~449–486). Leave the HTMX polling attributes (`hx-trigger="load, every 5s"`)
  untouched.

- [ ] **Step 7: Edit `asgi.py`** — delete the `import pbn_import.routing` line
  and change the `websocket_urlpatterns` assignment to
  `channels_broadcast.routing.websocket_urlpatterns` only.

- [ ] **Step 8: Edit `test_tasks.py`** — remove tests/assertions that patch or
  assert `send_websocket_update` / channel layer. Keep tests for status
  transitions, Rollbar, completion.

- [ ] **Step 9: Run pbn_import tests + a Django check**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_tasks.py src/pbn_import/tests/test_views_dashboard.py -p no:cacheprovider -q && uv run python src/manage.py check`
Expected: PASS, no import errors for the removed modules.

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "refactor(pbn_import): usuń martwą warstwę WebSocket (item 1)

Koperta import_update nie pasowała do handlerów konsumenta ani do
switch(data.type) po stronie klienta — każda wiadomość WS była
porzucana. Cały realtime realizuje polling HTMX. Usuwa consumers,
routing, helpery send_websocket_update, wpięcie ASGI i martwy skrypt
klienta.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Cap log queryset sizes in views (performance)

**Files:**
- Modify: `src/pbn_import/views.py` (add `MAX_LOGS_DISPLAY` constant; slice at
  515, 520, 583, 600)
- Test: `src/pbn_import/tests/test_views_session.py` (or
  `test_views_progress.py`)

- [ ] **Step 1: Write the failing test** — create a session with >250
  `ImportLog` rows and assert the all-logs HTMX endpoint returns at most
  `MAX_LOGS_DISPLAY` rows in context.

```python
# src/pbn_import/tests/test_views_session.py
import pytest
from model_bakery import baker
from django.urls import reverse
from pbn_import.views import MAX_LOGS_DISPLAY
from pbn_import.models import ImportSession, ImportLog


@pytest.mark.django_db
def test_all_logs_view_caps_results(admin_client):
    session = baker.make(ImportSession)
    baker.make(ImportLog, session=session, _quantity=MAX_LOGS_DISPLAY + 25)
    resp = admin_client.get(
        reverse("pbn_import:all_logs", args=[session.pk])
    )
    assert resp.status_code == 200
    assert len(resp.context["all_logs"]) == MAX_LOGS_DISPLAY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_views_session.py::test_all_logs_view_caps_results -p no:cacheprovider -q`
Expected: FAIL — `ImportError: cannot import name 'MAX_LOGS_DISPLAY'` (or
length 225). (Verify the exact url name + context key against `urls.py` /
`ImportAllLogsView`; adjust `reverse(...)` / context key if different.)

- [ ] **Step 3: Implement** — near the top of `views.py` add
  `MAX_LOGS_DISPLAY = 200`. Apply `[:MAX_LOGS_DISPLAY]` to the four
  `ImportLog.objects.filter(...).order_by("-timestamp")` querysets at
  ~515 (`context["logs"]`), ~520 (`context["error_logs"]`), ~583
  (`ImportAllLogsView`), ~600 (`ImportErrorLogsView`). Do not change
  `ImportLogStreamView` (already `[:50]`) or `ImportLogDownloadView` (must
  stay full).

- [ ] **Step 4: Run test to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Run the session/progress view tests**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_views_session.py src/pbn_import/tests/test_views_progress.py -p no:cacheprovider -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "perf(pbn_import): ogranicz rozmiar querysetów logów w widokach (item 4)

Endpointy HTMX re-fetchowane co 5 s ładowały WSZYSTKIE wiersze ImportLog
sesji. Wprowadza MAX_LOGS_DISPLAY=200 i slice w 4 miejscach; pełny log
pozostaje pobieralny przez ImportLogDownloadView.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Fix HTMX-cancel 500 + remove dead `progress.html`

**Files:**
- Modify: `src/pbn_import/views.py:373` (`CancelImportView`: render
  `progress_compact.html`)
- Delete: `src/pbn_import/templates/pbn_import/components/progress.html`
- Test: `src/pbn_import/tests/test_views_session.py`

- [ ] **Step 1: Check `progress_compact.html`'s required context**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && grep -nE "\{\{|\{%" src/pbn_import/templates/pbn_import/components/progress_compact.html | head -40`
Expected: confirm it only needs `session` (and derived attrs). If it needs
extra context, add it to the render call in Step 3.

- [ ] **Step 2: Write the failing test** — assert HTMX cancel returns 200, not
  500.

```python
# src/pbn_import/tests/test_views_session.py
@pytest.mark.django_db
def test_htmx_cancel_returns_200(admin_client):
    session = baker.make(ImportSession, status="running")
    resp = admin_client.post(
        reverse("pbn_import:cancel", args=[session.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
```

(Verify the cancel url name in `urls.py`; adjust `reverse(...)` accordingly.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_views_session.py::test_htmx_cancel_returns_200 -p no:cacheprovider -q`
Expected: FAIL — `NoReverseMatch: 'stats'` (500).

- [ ] **Step 4: Implement** — at `views.py:373` change the template path from
  `"pbn_import/components/progress.html"` to
  `"pbn_import/components/progress_compact.html"`. Then
  `git rm src/pbn_import/templates/pbn_import/components/progress.html`.

- [ ] **Step 5: Verify no remaining references to the deleted template / stats
  url**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && grep -rn "components/progress.html\|pbn_import:stats" src/`
Expected: no hits.

- [ ] **Step 6: Run test to verify it passes**

Run: same as Step 3. Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix(pbn_import): anulowanie HTMX zwraca 200 zamiast 500 (item 5)

components/progress.html odwoływał się do nieistniejącej trasy
pbn_import:stats → NoReverseMatch przy anulowaniu importu. CancelImportView
renderuje teraz progress_compact.html (używany wszędzie indziej);
martwy progress.html usunięty.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Remove the no-op `SavePresetView`

**Files:**
- Modify: `src/pbn_import/views.py` (delete `SavePresetView`, 484–494)
- Modify: `src/pbn_import/urls.py:52` (delete the `presets/save/` route)
- Test: grep-based (negative)

- [ ] **Step 1: Confirm nothing references the view or its url name**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && grep -rn "save_preset\|SavePresetView" src/ --include="*.py" --include="*.html"`
Expected: only the definition (`views.py`) + the route (`urls.py`). No
template/JS caller.

- [ ] **Step 2: Implement** — delete the `SavePresetView` class (`views.py`
  484–494) and the `path("presets/save/", ...)` line (`urls.py:52`). Remove
  the now-unused `csrf_exempt` / `json` imports only if nothing else uses them
  (grep first).

- [ ] **Step 3: Django check + url import sanity**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run python src/manage.py check && uv run pytest src/pbn_import/tests/test_views_permissions.py -p no:cacheprovider -q`
Expected: PASS, no `AttributeError`/`NoReverseMatch`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore(pbn_import): usuń no-op SavePresetView + trasę (item 5)

Widok był @csrf_exempt, robił json.loads(request.body) bez zabezpieczenia
(500 na złym body), niczego nie zapisywał i nie był referencjonowany.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Fix `progress_data` clobber race (minimal, no migration)

**Files:**
- Modify: `src/pbn_import/utils/base.py` (scope saves + refresh_from_db)
- Test: `src/pbn_import/tests/test_import_step.py` (or `test_import_session.py`)

- [ ] **Step 1: Write the failing test** — two `ImportStepBase`-style writers
  on the same session must not clobber each other's `progress_data` keys.

```python
# src/pbn_import/tests/test_import_step.py
@pytest.mark.django_db
def test_progress_data_writes_do_not_clobber(...):
    session = baker.make(ImportSession, progress_data={})
    # Writer A sets progress_data["steps"]["author_import"]
    # Writer B (separate in-memory instance) sets
    #   progress_data["current_subtask"]
    # After both save, reload from DB and assert BOTH keys present.
    ...
    session.refresh_from_db()
    assert "steps" in session.progress_data
    assert "current_subtask" in session.progress_data
```

(Model the two writers on the actual `ImportStepBase.update_progress` and
`TqdmSessionProgress.update` code paths; use two distinct `ImportSession`
instances fetched independently to simulate stale in-memory copies.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_import_step.py -k clobber -p no:cacheprovider -q`
Expected: FAIL — one key missing after the second writer's full/unscoped save.

- [ ] **Step 3: Implement** — in `base.py`:
  - In `update_progress` (~131–142): call
    `self.session.refresh_from_db(fields=["progress_data"])` before reading
    `self.session.progress_data["steps"]`, then change the trailing
    `self.session.save()` (142) to
    `self.session.save(update_fields=["progress_data"])`.
  - In `start` (~151–152): change `self.session.save()` to
    `self.session.save(update_fields=["current_step"])`.
  - In `TqdmSessionProgress.update` (~42–55): call
    `self.session.refresh_from_db(fields=["progress_data"])` before mutating
    `current_subtask` (keep its existing `save(update_fields=["progress_data"])`).
  - Verify `ImportSession.update_progress` (model method, called at base.py
    126) — if it does an unscoped `self.save()`, scope it to the fields it
    actually mutates (`current_step`, `current_step_progress`,
    `completed_steps` as applicable). Do NOT include `progress_data` there.

- [ ] **Step 4: Run test to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Run the step + session tests**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_import_step.py src/pbn_import/tests/test_import_session.py -p no:cacheprovider -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(pbn_import): zawęź zapisy progress_data, unikaj wyścigu nadpisania (item 5)

Pełne session.save() po mutacji jednego klucza JSONField mogło nadpisać
równoległy zapis throttlowanego TqdmSessionProgress (stale in-memory).
refresh_from_db(fields=[progress_data]) przed mutacją + update_fields przy
zapisie. Bez migracji.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Move PBN-auth network call out of `ImportManager.__init__`

**Files:**
- Modify: `src/pbn_import/utils/import_manager.py` (drop the `__init__` call
  at 47; ensure `run()` checks auth before first use)
- Test: `src/pbn_import/tests/test_import_manager.py`

- [ ] **Step 1: Write the failing test** — constructing `ImportManager` must
  NOT call the client (`get_languages` is only invoked once `run()`/auth
  runs).

```python
# src/pbn_import/tests/test_import_manager.py
@pytest.mark.django_db
def test_constructor_does_not_hit_pbn(...):
    client = MagicMock()
    session = baker.make(ImportSession, config={})
    ImportManager(session, client, {})
    client.get_languages.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_import_manager.py -k constructor_does_not_hit -p no:cacheprovider -q`
Expected: FAIL — `get_languages` was called during construction.

- [ ] **Step 3: Implement** — remove `self._check_pbn_authorization()` from
  `__init__` (line 47). At the very start of `run()`, before any step needs
  auth, add a guard so auth is checked exactly once:

```python
def run(self):
    if self.pbn_authorized is False and self.pbn_error_message is None:
        # not yet probed (constructor no longer probes)
        self._check_pbn_authorization()
    ...
```

Keep the existing re-check after InitialSetup (`import_manager.py:135`).
Verify existing `test_import_manager.py` tests that assumed post-construction
`pbn_authorized`/`pbn_error_message` still hold — update them to call `run()`
(or `_check_pbn_authorization()`) explicitly if needed.

- [ ] **Step 4: Run test to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Run the full import-manager test module**

Run: `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/test_import_manager.py -p no:cacheprovider -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(pbn_import): usuń efekt uboczny sieci z ImportManager.__init__ (item 6)

Konstruktor wywoływał client.get_languages() po sieci tylko do sondażu
autoryzacji. Sondaż przeniesiony na start run(); API publiczne bez zmian.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Mark stale `CODEBASE_MAP.md` as historical

**Files:**
- Modify: `src/pbn_import/CODEBASE_MAP.md` (header note only — do NOT rewrite
  the whole doc)

- [ ] **Step 1: Add a prominent note** under the title noting the map is
  auto-generated, dated 2026-01-16, no longer matches current line counts,
  and describes a since-removed `data_integration` step; point readers to
  this review for the current state. Keep it short (3–5 lines). No code/tests.

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "docs(pbn_import): oznacz CODEBASE_MAP jako historyczny (item 6)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run the whole `pbn_import` test package:
  `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run pytest src/pbn_import/tests/ -p no:cacheprovider -q`
- [ ] `uv run python src/manage.py check`
- [ ] `cd ~/Programowanie/bpp-pbn-import-cleanup && uv run ruff check src/pbn_import/ src/django_bpp/asgi.py && uv run ruff format --check src/pbn_import/`
- [ ] Add a newsfragment under `src/bpp/newsfragments/` (towncrier) if the
  repo convention requires it — check existing `+*.feature.rst` examples.
- [ ] Push branch and open PR into `feature/multi-hosted-config` with a body
  summarising items 1/4/5/6 done and item 3 explicitly **blocked** (legacy
  command owns unique sync/clear/ORCID/DOI/ISBN functionality — needs a
  separate rehoming effort or confirmation those paths are dead).

## Out of scope / deferred

- **Item 2** (`fix_*` scripts) — left untouched per user.
- **Item 3** (delete legacy `pbn_integrator` command) — **blocked**; not a
  duplicate orchestrator. See review §3.
