# Concepts

## State projection, not event stream

`django-live-operations` sends **HTML fragments that represent current state**,
not a stream of events that must be replayed.

Each fragment is a `hx-swap-oob` element keyed by `id`. The client applies
it via `htmx.process()`. Applying the same fragment twice is idempotent —
the second swap overwrites the first with the same content. This eliminates:

- ACK bookkeeping: no "did you receive message 42?"
- Replay on reconnect: just re-send the current state
- Ping-pong on reload: reconnect → snapshot → done

Compare this to the classic event-stream model, where every event must be
acknowledged, replayed on reconnect, and deduplicated. That approach is
fragile: a race between the result push and the ACK can put the page in
an inconsistent state (the FD#388 failure).

## Idempotent OOB swap

The client plugin (`live-operations.js`) extracts `msg.liveop_html` from the
JSON envelope and calls `htmx.process()` on each `hx-swap-oob` node. The swap
replaces the existing DOM element by `id` with the new content. If the same
update arrives twice, the result is the same as if it arrived once.

This means:

- Progress bar at 50% → arrives twice → still 50%
- Status "Weryfikacja…" → snapshot sends it again → still "Weryfikacja…"
- Result fragment → snapshot on reconnect → same result shown

## Snapshot-on-connect

When a client connects (or reconnects), `LiveOperationConsumer.connect()`
calls `operation.send_snapshot()`. This reads the **current state from DB**
and sends a fresh HTML snapshot to the connecting client.

For a running operation, the snapshot shows an in-progress status.
For a finished operation, the snapshot shows the **result** (or error).

This is the FD#388 fix: an operation that finishes before the client connects
delivers the result on connect — not "in progress". The snapshot always
reflects reality.

## v1 no-persist default

In v1, the **source of truth** is the terminal state in the database:
`finished_on`, `finished_successfully`, `result_context`, `traceback`.

**Only terminal state** is persisted. Live progress (`status`, `percent`,
`log`) is sent over the WebSocket but not written to the database during the
run. This is a deliberate trade-off:

- **Benefit**: no database writes during every progress tick → fast, no
  per-tick overhead
- **Trade-off**: a client that connects mid-operation misses the history
  (percent and log lines sent before connect are not replayed)
- **Self-heal**: the next progress tick delivers a current percent; the
  client is never stuck (it just misses history)

A future `PERSIST_PROGRESS` mode (not in v1) will write progress to a separate
DB connection and replay it on connect. The fields `status_text`, `percent`,
`log`, `log_seq` are placeholder columns for this mode.

## Why no reload, no polling

The page never navigates away. The WebSocket stays open from start to finish.
The result replaces the "in progress" region in-place via `hx-swap-oob`.
No `setInterval`, no `hx-trigger="every 3s"`, no redirect to a results page.

Reconnect after network interruption: `channels_broadcast` reconnects
automatically, and `send_snapshot()` brings the client up to date instantly.
Because swaps are idempotent, the resync is always safe.
