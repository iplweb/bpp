# Security

## Subscription token model

Access to a live operation channel is controlled by a **short-lived signed
subscription token**. The token is issued by the server when rendering the host
page and embeds:

- The user's primary key
- The channel name(s) authorised (e.g. `liveop.<uuid>`)
- An expiry time (default 300 seconds)

The token is signed using Django's `TimestampSigner` with `SECRET_KEY`. It is
verified by `channels_broadcast.NotificationsConsumer` on every WebSocket
connect.

A token for user A is rejected when presented by user B (`user.pk` is embedded
and checked against `scope["user"].pk`). A token for operation A does NOT
authorise operation B's channel.

```python
from live_operations.security import make_subscription_token
token = make_subscription_token(user, operation)
```

The `LiveOperation.subscription_token` property returns this token, and
`{% live_operation op %}` embeds it in the container's `data-liveop-token`
attribute.

## Owner-scoped channels

The channel name is `liveop.<uuid>` where the UUID is the operation's primary
key. The subscription token binds a specific user to that specific channel.

All views (`LiveOperationView`, `CancelView`, `RestartView`, etc.) filter
querysets to `owner=request.user` via `BaseLiveOperationMixin.get_queryset()`
— cross-user access is impossible through the built-in views.

## HTML fragment safety

Fragments are transported inside a JSON envelope and swapped into the DOM by
`id`. Autoescaping applies to template-rendered content:

- `p.status(text)` — rendered via Django template, auto-escaped.
- `p.log(line)` — auto-escaped.
- `p.error(message)` — uses `format_html` to escape the message before pushing.
- `p.result(context)` — rendered via Django template, auto-escaped.
- `render_op_result` fallback — escapes each `key=value` pair.
- `p.html(selector, raw)` — **trusted HTML only**. This is an explicit escape
  hatch (like `mark_safe`). Never pass user-controlled data to `p.html()`.
- `p.swap(selector, name=..., html_raw=...)` — `html_raw=` is trusted HTML;
  named templates use Django auto-escaping.

## CSRF

WebSocket connections are not subject to Django's CSRF middleware.
Authentication is handled via the subscription token. The cancel and restart
views are POST-only and protected by Django's standard CSRF protection.

## Group membership restriction

To restrict live operations to a specific group of users:

```python
LIVE_OPERATIONS = {
    "REQUIRED_GROUP": "operators",
}
```

Authenticated users not in the group receive a 403 from all
`BaseLiveOperationMixin` views.

## Token TTL

The default token lifetime is 300 seconds. It is verified only on connect — an
open WebSocket connection is not re-verified. After connecting, the consumer
stays subscribed until the socket closes. For operations that keep the page
open longer than the TTL, the initial connect must simply happen within the
window; a reconnect requires a freshly rendered page (new token).
