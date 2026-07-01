# API Reference

## LiveOperation (abstract model)

`from live_operations.models import LiveOperation`

Concrete subclasses must implement `run(self, p)`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField (PK) | Auto-generated UUID |
| `owner` | FK → AUTH_USER_MODEL | Operation owner |
| `created_on` | DateTimeField | Auto set on create |
| `started_on` | DateTimeField | Set when runner starts |
| `finished_on` | DateTimeField | Set on completion or error |
| `finished_successfully` | BooleanField | True if `p.result()` was called |
| `cancel_requested` | BooleanField | Set by cancel view |
| `cancelled` | BooleanField | Set by runner on cancellation |
| `traceback` | TextField | Exception traceback on error |
| `result_context` | JSONField | Context dict from `p.result()` |
| `stages` | class attr `list[str]` | Stage names (not a DB field) |
| `current_stage` | IntegerField | Index of active stage |
| `stage_states` | JSONField | Per-stage state dict |

### Methods

#### `run(self, p) → None`

Override in subclasses. Receives a `Progress` instance. Call `p.result()` to
mark success, `p.error(msg)` to mark failure. If `run()` returns without
calling either, the runner auto-finalizes as success.

#### `enqueue() → None`

Dispatch via the configured `RUNNER`. Equivalent to `runner.enqueue(self)`.

#### `get_state() → str`

Returns one of: `"NOT_STARTED"`, `"STARTED"`, `"FINISHED_OK"`,
`"FINISHED_ERROR"`, `"CANCELLED"`.

#### `subscription_token → str` (property)

Returns a short-lived signed token authorising `self.owner` to subscribe to
this operation's WebSocket channel. Used by `{% live_operation op %}`.

#### `get_host_template_name() → str`

Auto-derived: `<app_label>/<class_to_snake(Class)>.html`. Override by setting
`host_template_name = "..."` as a class attribute.

#### `get_result_template_name() → str`

Auto-derived: `<app_label>/<class_to_snake(Class)>_result.html`. Override by
setting `result_template_name = "..."` as a class attribute.

#### `get_channel_name() → str`

Returns `f"liveop.{self.pk}"`.

#### `get_absolute_url() → str`

Returns the URL of the live host page
(`reverse("live_operations:live", kwargs={"pk": self.pk})`).

#### `send_snapshot() → None`

Called by the consumer on connect. Pushes the current state as an HTML
fragment to this operation's channel group.

---

## Progress API

`from live_operations.progress import Progress, WebProgress, TextProgress`

### Core API (both backends)

#### `p.status(text, level="info") → None`

Send a status message. `level` may be `"info"`, `"warning"`, `"error"`.

#### `p.percent(value: int) → None`

Send a percent update (0–100). Throttled by `THROTTLE_HZ`. Rapid same-value
calls are coalesced by a time gate.

#### `p.track(iterable, total=None, label=None, unit="szt.") → Generator`

Wrap an iterable: yields each item, updates percent after each, calls
`check_cancelled()` before each item. If `total` is None, the iterable is
fully consumed first to get the count.

#### `p.log(line: str) → None`

Append a log line.

#### `p.stage(name: str) → context manager`

Enter a named stage. Updates `current_stage` and `stage_states` on the
operation. On exit (success), marks the stage as "done". On exception, marks
as "failed" or "cancelled". Pushes the updated stepper HTML.

#### `p.result(context=None, **extra) → None`

Mark the operation as successfully finished. Commits `finished_on`,
`finished_successfully=True`, `result_context` to DB. Sends the result HTML
fragment via `transaction.on_commit` (DB committed before push — §19.4).

#### `p.error(message: str) → None`

Mark the operation as failed. Commits `finished_on`,
`finished_successfully=False`, `traceback`. Sends the error fragment via
`transaction.on_commit`.

#### `p.check_cancelled() → None`

Re-reads `cancel_requested` from DB. Raises `OperationCancelled` if set.
Called automatically by `p.track()` on each item.

#### `p.chain_to(next_op) → None`

Finish the current operation and seamlessly start `next_op`. No page reload.
See [Stages and Chaining](stages-and-chaining.md).

### Web-only API (WebProgress only)

Calling these on `TextProgress` raises `NotImplementedError`.

#### `p.swap(selector, name=None, html_raw=None, **ctx) → None`

Push an arbitrary DOM region update. `selector` is the element `id` (with or
without `#`). Either pass `html_raw=` for raw HTML, or `name=` to auto-derive
a template `<app>/<snake>_<name>.html`.

Note: use only in `run()` methods that will never run in text/CLI mode. See
[Text mode](text-mode.md).

#### `p.html(selector, raw, mode="innerHTML") → None`

Push raw HTML to `selector`. `raw` is **trusted** HTML (not escaped) — never
pass user-controlled data here. Use `p.status()`, `p.log()`, or `p.result()`
for data-bearing updates. `mode="beforeend"` appends instead of replacing.

---

## Views and mixins

`from live_operations.views import ...`

### `BaseLiveOperationMixin`

Login-required, owner-scoped base for all views. Optional group gate via
`LIVE_OPERATIONS["REQUIRED_GROUP"]`. `get_queryset()` always filters to
`owner=request.user`.

### `CreateLiveOperationView`

`CreateView` that sets `owner=request.user`, saves, calls `op.enqueue()`, and
redirects to `op.get_absolute_url()`.

### `LiveOperationView`

`DetailView` that renders the host template. Template order:
`op.get_host_template_name()` → `live_operations/operation.html`.

### `LiveOperationListView`

`ListView` of operations owned by `request.user`.

### `CancelView`

POST-only: sets `cancel_requested=True`, redirects to live page.

### `RestartView`

POST-only: resets terminal state, re-enqueues, redirects to live page.

---

## Template tag

```django
{% load live_operations %}
{% live_operation op %}
```

Renders the live container with `data-liveop-channel` and `data-liveop-token`
attributes. The `live-operations.js` script scans for these on
DOMContentLoaded and calls `channelsBroadcast.init()` to subscribe.

There is also `{% render_op_result op %}` which renders the result fragment
for a finished operation (falls back to an escaped `key=value` dump if the
result template is missing).

---

## Settings (`LIVE_OPERATIONS` dict)

| Key | Default | Description |
|-----|---------|-------------|
| `BASE_TEMPLATE` | `"base.html"` | Base template for built-in views |
| `RUNNER` | `"eager"` | `"eager"` / `"threading"` / `"celery"` |
| `THROTTLE_HZ` | `10` | Max percent updates per second |
| `REQUIRED_GROUP` | `None` | Group name; `None` = no group restriction |

### RUNNER values

- `"eager"` — runs synchronously in the calling thread. No Redis or Celery
  needed. For tests and degradation mode. Only the terminal snapshot is
  visible (progress pushes hit an empty group).
- `"threading"` — runs in a background daemon thread. Needs a channel layer
  (InMemory or Redis). For development.
- `"celery"` — dispatches via a Celery shared task. Needs Redis + a Celery
  worker. For production.
