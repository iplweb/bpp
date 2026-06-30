# `django-live-operations` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Each phase ends with a green test gate + commit. Read the spec for any
> ambiguity: `docs/superpowers/specs/2026-06-30-live-operations-htmx-ws-design.md`
> — and §19 is NADRZĘDNE (overrides earlier sections).

**Goal:** Standalone, reusable Django package `django-live-operations` (import
`live_operations`): long-running operations with live WebSocket+HTML-OOB UI (no
reload, no polling), ergonomic `run(self, p)` API, stages + chaining, text/tqdm
mode, MkDocs docs, examples, and a one-command Docker demo + 3-tier tests.

**Architecture:** State-projection over WS via `channels_broadcast` (reuse its
client `addMessage` hook + idempotent `init`; HTML travels in a JSON envelope
`{"liveop_html": …}`). Terminal state committed in DB (source of truth for
snapshot); in-flight progress is live-only + self-heal. `Progress` is a
transport-neutral interface with `WebProgress`/`TextProgress` backends.

**Tech stack:** Python ≥3.10, Django ≥4.2, `channels`, `channels_redis`,
`django-channels-broadcast`, Celery (optional extra), tqdm (optional extra),
htmx 1.9 core (consumer-provided), pytest + pytest-django +
pytest-testcontainers-django, MkDocs (+ material).

## Global Constraints (binding for every phase)

- **uv run** for all Python; ruff (88 cols) clean; no `ruff check --fix`.
- **Zero dependency on BPP** — imports only Django/channels/channels_broadcast.
  No `from bpp...`. (Reusability + future PyPI.)
- **Location:** new package dir at repo root: `django-live-operations/` with its
  own `pyproject.toml`; importable app `live_operations`.
- **§19.1** socket addressing = fixed `channels_broadcast` path +
  `subscription_token` (channel `liveop.<pk>`). NO per-pk `ws-connect`/URL.
- **§19.2** server sends HTML in JSON envelope `{"liveop_html": "<… hx-swap-oob>"}`,
  **no top-level `id`** (client auto-ACKs `id` frames). Client = a
  `channels_broadcast` `addMessage` plugin that extracts `liveop_html`, applies
  OOB-swap by `id`, then `htmx.process(node)`.
- **§19.3** default no-persist: DB source-of-truth = terminal state only
  (`finished_*`, `result_context`, `traceback`). `status/percent/log` live-only,
  self-heal. `PERSIST_PROGRESS` and full-log/dedupe are OUT of v1.
- **§19.4** terminal state commits BEFORE the final result push (or push via
  `transaction.on_commit`). Every other `p.*` push is immediate.
- **§19.5** `Progress` core = `status/percent/track/log/stage/result/
  check_cancelled/chain_to`. `swap/html` = WebProgress-only (TextProgress →
  `NotImplementedError`). `p.result` text fallback = key=value dump of
  `result_context` if no `*_result.txt`.
- **§17.7** `async_to_sync(channel_layer.group_send)` for every send from the
  sync worker.
- **Auto-derivation (§4.4):** templates/channel derived from class:
  `<app_label>/<class_to_snake(Class)>.html` (host), `…_result.html` (result),
  channel `liveop.<pk>`. Override via class attrs.

## Phase 0 — Package scaffold + tooling + MkDocs skeleton

**Files (create):**
- `django-live-operations/pyproject.toml` — name `django-live-operations`,
  packages `live_operations`; deps: `django>=4.2`, `channels>=4`,
  `django-channels-broadcast`; extras: `celery`, `cli`(tqdm), `dev`(pytest,
  pytest-django, pytest-testcontainers-django, channels[daphne], ruff,
  mkdocs-material), `redis`(channels_redis).
- `live_operations/__init__.py`, `apps.py` (AppConfig), `conf.py`
  (`LIVE_OPERATIONS` settings dict + getters: `BASE_TEMPLATE`, `RUNNER`,
  `THROTTLE_HZ`).
- `live_operations/migrations/__init__.py`.
- `.pre-commit-config.yaml`, `ruff` config, `Makefile` (test/demo/docs targets).
- `mkdocs.yml` + `docs/index.md` (skeleton).
- `tests/__init__.py`, `tests/settings.py` (minimal Django settings with
  `channels`, `channels_broadcast`, `live_operations`, InMemory channel layer
  default for unit tests), `tests/conftest.py`, `pytest.ini`/`[tool.pytest]`.

**Test gate:** `uv run pytest` collects 0 tests without error; `uv run python -c
"import live_operations"` works; `uv run python -m mkdocs build` (skeleton) OK.
**Commit.**

## Phase 1 — Core: naming, models, runner, Progress (Web + Text)

**Files:**
- `naming.py` — `class_to_snake(name)` (handle acronyms/digits: regex pair like
  `inflection`); `host_template_name(model)`, `result_template_name(model)`,
  `channel_name(op)` = `f"liveop.{op.pk}"`. **Pure, unit-tested.**
- `models.py` — `LiveOperation(abstract)`: UUID pk, `owner` FK, timestamps,
  `finished_successfully`, `cancel_requested`, `cancelled`, `traceback`,
  `result_context (JSONField null)`; placeholder `status_text/percent/log/
  log_seq` (documented: written only under future PERSIST). `stages=[]`,
  `current_stage`, `stage_states (JSON)`. Methods: `run(self, p)` (raise
  NotImplementedError), `get_state()`, template/channel resolvers (via naming),
  `subscription_token` property (Phase 2), `enqueue()` (Phase 1 via runner).
- `runner.py` — `enqueue(operation)` dispatching per `RUNNER` setting:
  `eager` (run inline, terminal-snapshot-only), `celery` (shared task →
  `operation.task_run()`), `threading` (dev). `task_run()` orchestrates:
  mark_started → run(p) → on success commit terminal + push result (on_commit)
  → on error set traceback + push error → cooperative cancel handling.
- `progress.py` — `Progress` (abstract core API), `OperationCancelled`,
  `WebProgress(operation, channel_layer)` (sends via `async_to_sync(group_send)`
  JSON envelope), `TextProgress(operation, stream)` (tqdm/print).
  `p.track(iterable, total, label, unit)` generator with throttling
  (THROTTLE_HZ) + `check_cancelled()` per item. `p.stage()` context manager.
  `p.result(context=None, **extra)` / `p.error(msg)`. `swap/html` on WebProgress
  only; TextProgress raises NotImplementedError.

**Test gate (unit, no DB needed for naming; `@pytest.mark.django_db` for a
concrete test model in `tests/`):**
- naming: snake-case incl. `ImportPBN2`→`import_pbn2`; template/channel names.
- `TextProgress`: captures stdout; `track` yields all + prints bar; `log`;
  `result` dumps `result_context` key=value when no `.txt`; `swap`→NotImplemented.
- `WebProgress` with a **fake channel layer** (captures `group_send`): asserts
  JSON envelope `{"liveop_html": …}`, no top-level `id`, fragment has the region
  `id` + `hx-swap-oob`; throttling coalesces; `result` push deferred to commit.
- `runner` eager: a test `LiveOperation` subclass runs end-to-end; terminal
  fields committed; cancel via `cancel_requested` → `cancelled`.
**Commit per sub-area (naming / models+migration / runner / progress).**

## Phase 2 — Transport: consumer wiring, security token, client JS plugin

**Files:**
- `security.py` — issue/verify `subscription_token` (reuse
  `channels_broadcast.security` signer) binding `user → liveop.<pk>`; short TTL.
  `LiveOperation.subscription_token` builds it for the owner.
- Consumer: reuse stock `channels_broadcast` `NotificationsConsumer` (token path
  authorizes `liveop.<pk>`). Add **snapshot-on-connect**: a small hook/served
  fragment that, on connect, group_sends current TERMINAL state (if finished →
  result fragment; else a "running" status fragment). Implementation note:
  channels_broadcast `on_connect` replays Notifications — for live_operations we
  instead send a snapshot via a connect signal or a thin consumer subclass that
  calls `operation.send_snapshot()`. Decide minimal approach; keep within
  channels_broadcast contract. Receive() must tolerate stray `ack_message`.
- `static/live_operations/live-operations.js` — `channels_broadcast` plugin:
  reads `data-liveop-channel`/`data-liveop-token` from `#op-<pk>`, calls
  `channelsBroadcast.init([channel], {subscriptionToken})`; overrides
  `addMessage`: if `msg.liveop_html` → parse fragment, OOB-swap by `id`
  (innerHTML/outerHTML/beforeend per `hx-swap-oob`), `htmx.process(node)`,
  dedupe log by `data-nr` (no-op in v1 default); on `msg.liveop_chain` →
  `init([next_channel], {token})`. Connection indicator. Fall through to
  original handler otherwise.

**Test gate:**
- `security`: token round-trips; wrong user/op rejected; expired rejected.
- consumer (channels `WebsocketCommunicator` + InMemory layer): connect with
  valid token → receives snapshot envelope; manual `group_send` of a fragment →
  client receives; stray ack tolerated; unauthorized connect closed.
- JS: a small DOM test (optional, via a headless harness or documented manual
  check) — OR assert the plugin logic in isolation if a JS test runner is set
  up; otherwise cover via the Phase 5 browser demo + a Playwright smoke.
**Commit.**

## Phase 3 — Views, templatetag, templates (host + region fragments)

**Files:**
- `views.py` — CBV mixins: `CreateLiveOperationView` (form → owner, enqueue,
  redirect to live view), `LiveOperationView` (host page; if finished renders
  result fragment immediately for deep-link), `LiveOperationListView`,
  `CancelView` (POST sets cancel_requested), `RestartView`. All owner+perm
  gated (configurable permission/group).
- `urls.py` — `app_name="live_operations"`; index/new/live/cancel/restart
  (NO per-pk ws path — §19.1).
- `templatetags/live_operations.py` — `{% live_operation op %}` → renders
  `#op-<pk>` container with `data-liveop-channel`/`data-liveop-token` +
  `_regions.html`.
- `templates/live_operations/` — `operation.html` (default host, extends
  `BASE_TEMPLATE`), `_regions.html` (status/progress/log/stages/result/cancel),
  `_status.html`, `_progress.html`, `_log.html`, `_stages.html` (stepper),
  `_result.html`, `_cancelled.html`. Fragment render helpers produce
  `hx-swap-oob` wrappers.

**Test gate (django_db + client):**
- create → redirect to live; live page renders regions + data-* + token; cancel
  POST sets flag; finished op live page renders result inline (deep-link).
- templatetag renders channel/token; permission gating (403/redirect).
**Commit.**

## Phase 4 — Stages + chaining

**Files:** extend `progress.py` (`p.stage` updates `current_stage`/`stage_states`
+ pushes stepper fragment; `p.chain_to(next_op)` finalizes current, enqueues
next, pushes container swap + `{"liveop_chain": {channel, token}}`),
`_stages.html`. Text backend: stage = header + per-stage bar; chain = inline
`next.run(p)`.

**Test gate:** stepper fragment reflects current/done/failed; multi-stage run;
`chain_to` (eager: runs next inline; web: asserts chain envelope sent). Text
mode: stages print headers; chain runs inline.
**Commit.**

## Phase 5 — Demo project + one-command Docker stack

**Files:** `django-live-operations/example/` — minimal Django project (ASGI with
channels routing including channels_broadcast), a `DemoImport(LiveOperation)`
with 5 stages (fake upload→analiza→wyniki, sleeps + `p.track`/`p.log`),
templates, urls; `manage.py seed_demo` (create owner + dev auto-login token +
sample); `docker-compose.yml` (redis, web=Daphne, worker=Celery);
`Makefile` `demo` target; `README` "run in one command".
- Also `manage.py run_liveop example.DemoImport` for text/CLI (no browser).

**Test gate:** `docker compose config` valid; `seed_demo` idempotent (django_db);
`run_liveop` runs DemoImport in eager/text mode green; a Playwright smoke
(optional, gated) loads the demo and sees progress→result without navigation.
**Commit.**

## Phase 6 — Tests round-trip (Redis) + MkDocs docs + examples polish

**Files:**
- `tests/test_roundtrip.py` — worker→Redis layer→`WebsocketCommunicator` using
  `pytest-testcontainers-django` Redis; full live cycle incl. "finished before
  connect → snapshot shows result" (the FD#388 case) and `on_commit` terminal
  ordering (§19.4).
- `docs/` (MkDocs): Getting Started, Concepts (state projection, snapshot,
  no-reload), Tutorial (build an importer like the spec example), API reference
  (`LiveOperation`, `Progress` core vs Web-only, runner, settings), Stages &
  Chaining, Text/CLI mode, Deployment (ASGI + Redis + Celery), Testing,
  Architecture & rationale (link the spec), Troubleshooting (the §1 failure
  modes). `mkdocs.yml` nav.
**Test gate:** full `uv run pytest` green (unit + roundtrip); `mkdocs build
--strict` clean.
**Commit.** Then PR update.

## Self-Review checklist (run after writing)
- Every §19 constraint has a phase that enforces it (token addressing, JSON
  envelope, terminal on_commit, no-persist guarantees, swap/html web-only).
- No `from bpp` anywhere in the package.
- Demo is genuinely one-command; CLI path needs no Redis/ASGI.
- Tests cover the FD#388 "finished-before-connect" case on Redis.
