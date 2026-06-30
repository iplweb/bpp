# django-live-operations — Phase 1 Implementation Report

**Date:** 2026-07-01  
**Branch:** feat/live-operations  
**Commits:** 4 sub-commits (naming / models+migration / progress / runner)

---

## Modules implemented

### 1. `live_operations/naming.py`

```python
class_to_snake(name: str) -> str
host_template_name(model_cls: Any) -> str   # override via class attr str
result_template_name(model_cls: Any) -> str  # override via class attr str
channel_name(op: Any) -> str                # → "liveop.<pk>"
```

**Key design note:** Python's `type.__name__` is a C-level data descriptor —
`FakeModel.__name__` always returns the class's real name even if `__name__ =
"..."` was set in the class body. However, `vars(model_cls).get("__name__")`
reads the class's `__dict__` and returns the override. `_class_name()` helper
uses this to support test fakes and explicit name overrides.

Two-pass inflection regex: `ImportPBN2 → import_pbn2`, `ABCTest → abc_test`.

---

### 2. `live_operations/models.py` + `tests/migrations/0001_initial.py`

```python
class LiveOperation(models.Model):  # abstract
    id: UUIDField(pk, default=uuid4)
    owner: FK(AUTH_USER_MODEL)
    created_on / started_on / finished_on: DateTimeField
    finished_successfully: BooleanField
    cancel_requested / cancelled: BooleanField
    traceback: TextField(null)
    result_context: JSONField(null)           # §19.3 terminal state
    # placeholders (v1 live-only, §19.3):
    status_text / percent / log / log_seq / current_stage / stage_states
    stages: list[str] = []                   # class attr, not DB field

    def run(self, p): raise NotImplementedError
    def get_state() -> str  # NOT_STARTED/STARTED/FINISHED_OK/FINISHED_ERROR/CANCELLED
    def get_host_template_name() / get_result_template_name() / get_channel_name()
    def enqueue()
```

Concrete test models: `DemoOp`, `ErrorOp` in `tests/models.py` (app_label="tests"),
both in `tests/migrations/0001_initial.py`.

---

### 3. `live_operations/progress.py` + 5 fragment templates

**Core `Progress` API (both backends):**
```python
status(text, level="info")
percent(value)            # throttled: THROTTLE_HZ gate + delta≥1 pass-through
track(iterable, total, label, unit) -> Generator  # check_cancelled per item
log(line)
stage(name) -> contextmanager  # updates current_stage + stage_states
result(context=None, **extra)
error(message)
check_cancelled()         # refresh_from_db; raise OperationCancelled if set
chain_to(next_op)         # stub (Phase 4)
swap(selector, name, **ctx)   # base: NotImplementedError("webowe")
html(selector, raw, mode)     # base: NotImplementedError("webowe")
```

**`WebProgress(Progress)`:**
- `_push(html)`: `async_to_sync(channel_layer.group_send)(channel, {"type":"chat_message","liveop_html":html})`
- §19.2 enforced: no top-level `id` key
- `swap(selector, html_raw=...)` / `html(selector, raw, mode)` implemented
- §19.4 terminal-commit-before-push: `save()` is immediate; result fragment pushed via `transaction.on_commit()`

**`TextProgress(Progress)`:**
- tqdm native `track()` when available, else plain percent-at-intervals
- `result()` tries `*_result.txt` template, falls back to `key=value` dump
- `swap`/`html` raise `NotImplementedError("swap/html są webowe; użyj log/status/result")`

**Templates created:**
- `_status.html` — `<div id="op-status" hx-swap-oob="true">`
- `_progress.html` — `<div id="op-progress" hx-swap-oob="true">`
- `_log_line.html` — `<div hx-swap-oob="beforeend:#op-log">`
- `_result.html` — `<div id="op-result" hx-swap-oob="true">`
- `_error.html` — `<div id="op-result" hx-swap-oob="true">`

**Fake channel layer (test/FakeChannelLayer):**
```python
class FakeChannelLayer:
    sent: list[tuple[str, dict]] = []
    async def group_send(self, group, message): self.sent.append(...)
```
`async_to_sync` runs it synchronously so no event loop setup is needed in tests.

**§19.4 implementation:** `WebProgress.result()` saves `finished_on/finished_successfully/result_context` synchronously, then registers `transaction.on_commit(_push_result)`. In autocommit (no wrapping atomic), on_commit fires immediately after save. Inside atomic(), fires after commit. The `operation` instance is excluded from `result_context` (not JSON-serialisable) — a `storage_ctx` / `render_ctx` split is used.

---

### 4. `live_operations/runner.py`

```python
enqueue(operation, progress=None) -> None  # dispatches per RUNNER setting
task_run(operation, progress) -> None      # core loop
_make_progress(operation) -> Progress      # auto WebProgress or TextProgress
```

**Pre-flight cancel check** in `task_run`: `refresh_from_db(fields=["cancel_requested"])` before calling `run()`. If `cancel_requested=True`, marks `cancelled+finished_on` without calling `run()`.

**`_get_cancelled_class()` indirection:** avoids circular import at module level — `OperationCancelled` is imported lazily inside `task_run`.

**Celery guard:** `try: from celery import shared_task` at module level; `ImportError` silently skipped. Calling `"celery"` runner without Celery installed raises `RuntimeError` with clear message.

---

## TDD evidence (red → green per module)

| Module | RED proof | Tests |
|--------|-----------|-------|
| naming | `ModuleNotFoundError: No module named 'live_operations.naming'` | 10 |
| models | `ModuleNotFoundError: No module named 'live_operations.models'` | 9 |
| progress | `ModuleNotFoundError: No module named 'live_operations.progress'` (collection error) | 20 |
| runner | `ImportError: cannot import name 'runner' from 'live_operations'` | 4 |

**Total: 44 tests, all GREEN.**

---

## Concerns / notes for Phase 2+

1. **`_class_name()` in naming.py** reads `vars(model_cls)["__name__"]` — this is needed for test fakes but won't affect real Django models (their `__name__` is set at C level by the class definition keyword, so `vars()` won't have it, and `model_cls.__name__` gives the correct name).

2. **`result_context` excludes "operation" key** — the model instance is added to the template render context but is stripped before DB storage. Callers of `p.result()` should not rely on `result_context["operation"]` being persisted.

3. **`stage()` context manager** updates `current_stage`/`stage_states` on the in-memory instance but does NOT save to DB (Phase 1 scope). Phase 4 will add `save()` calls and stepper fragment pushes.

4. **`check_cancelled()` does a DB read per call** — one extra query per `track()` item. For high-frequency tracks this is acceptable (v1); Phase 4 may add a time-gated cancel check.

5. **`chain_to()` stub** raises `NotImplementedError` in all backends (Phase 4). TextProgress has a real inline implementation but is not yet wired.
