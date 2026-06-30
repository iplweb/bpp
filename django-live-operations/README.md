# django-live-operations

A standalone, reusable Django package for long-running operations with a live
WebSocket + HTMX user interface — no page reloads, no polling.

The developer writes one method:

```python
class MyImport(LiveOperation):
    def run(self, p):
        for row in p.track(rows, label="Processing"):
            process(row)
            p.log(f"done: {row}")
        p.result()
```

The framework handles channels, tokens, OOB-swaps, snapshot-on-connect,
throttling, and cooperative cancellation.

See `docs/` for the full documentation.
