# django-live-operations

`django-live-operations` is a standalone, reusable Django package for running
long-duration operations with a live WebSocket + HTMX user interface — no page
reloads, no polling. The developer implements a single `run(self, p)` method and
calls `p.status()`, `p.track()`, `p.log()`, and `p.result()`; the framework
handles channel naming, security tokens, HTML fragment delivery, OOB-swap,
snapshot-on-connect, and cooperative cancellation.

See the full design spec and implementation plan in `docs/superpowers/specs/`
and `docs/superpowers/plans/` within the repository.
