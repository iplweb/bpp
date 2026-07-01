# Architecture

## Design specification

The full design rationale, protocol decisions, and adversarial review findings
live in the internal design spec
(`docs/superpowers/specs/2026-06-30-live-operations-htmx-ws-design.md`). This
page summarises the failure modes it fixes and the binding decisions.

## The three failure modes fixed (§1)

The original `long_running` framework had structural problems (observed in
FD#388):

1. **Navigation wins the ACK race.** Server sends result → client queues an
   ACK and immediately navigates away → page unloads, ACK never sent →
   notification re-delivered on the next page → another navigation →
   ping-pong loop.

2. **Reload destroys the socket.** Every page refresh disconnects the
   WebSocket, forces a reconnect, and re-replays unacknowledged events. Reload
   and WebSocket fight each other.

3. **Manual UID ceremony.** Developers wired up channel names, extra channels,
   URL prefixes, and state-to-URL mappings by hand for every operation type.

`django-live-operations` eliminates all three:

1. **No navigation.** The result arrives as an OOB swap. The page never
   unloads. There is no ACK model. Idempotent swaps make duplicate delivery
   harmless.

2. **Reconnect = snapshot.** On every connect, the server pushes current state
   from DB. The socket can be destroyed and reconnected any number of times.

3. **Auto-derived names.** Channel = `liveop.<pk>`. Template =
   `<app>/<snake_class>.html`. Subscription token = signed, embedded in HTML.
   Zero manual UID wiring.

## Transport layer (§19.2)

The server sends JSON envelopes:
`{"type": "chat_message", "liveop_html": "<html>"}`. The `liveop_html` value is
an HTML fragment with `hx-swap-oob` attributes. There is deliberately **no
top-level `id`** in the envelope — the `channels_broadcast` client auto-ACKs
frames with `id` as Notifications, which is the wrong semantic for our
fragments.

The `live-operations.js` plugin intercepts `msg.liveop_html`, parses the
fragment, and applies each `hx-swap-oob` element to the DOM by id-based
replacement, then calls `htmx.process(node)` to activate any `hx-*` attributes
in the new content.

## Snapshot-on-connect (§19.3)

`LiveOperationConsumer.connect()` calls `operation.send_snapshot()` for each
authorised `liveop.*` channel. `send_snapshot()` reads current state from DB
and sends the appropriate fragment:

- `FINISHED_OK` → renders the result template → `<div id="op-result" ...>`
- `FINISHED_ERROR` → renders an error div
- `CANCELLED` → renders a cancelled div
- `STARTED` / `NOT_STARTED` → renders an "in progress" status

## Terminal-first persistence (§19.3)

Only terminal state is written to DB: `finished_on`, `finished_successfully`,
`result_context`, `traceback`. Progress (`status`, `percent`, `log`) is
live-only. A client connecting mid-operation misses historical progress but
self-heals on the next tick.

## Commit before push (§19.4)

`p.result()` (and `p.error()`) write to DB and then register
`transaction.on_commit(_push_result)`. This guarantees: DB committed → result
pushed. A client connecting between push and commit (the FD#388 window) sees
committed state on `send_snapshot()`. This is the only place where `on_commit`
is required — every other `p.*` push is immediate.

## Component map

```
Browser
  │  WebSocket (/asgi/notifications/?subscription_token=...)
  ▼
LiveOperationConsumer (consumers.py)
  │  on connect: verify token → group_add → send_snapshot()
  │  on message: chat_message → forward to WS client
  ▼
RedisChannelLayer (channels_redis)
  ▲
WebProgress (progress.py)
  │  async_to_sync(channel_layer.group_send)
  │  wraps each fragment in {"type":"chat_message","liveop_html":"..."}
  │
Celery worker / threading worker
  │
LiveOperation.run(self, p)  ← developer code
```

## Auto-derivation

Given `class ImportPunktacji(LiveOperation)` in `my_app`:

| Derived value | Result |
|--------------|--------|
| Host template | `my_app/import_punktacji.html` |
| Result template | `my_app/import_punktacji_result.html` |
| Channel name | `liveop.<uuid>` |
| Subscription token | signed `{user_pk, ["liveop.<uuid>"], ttl=300}` |
