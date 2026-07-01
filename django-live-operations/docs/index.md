# django-live-operations

Long-running Django operations with live WebSocket + HTMX UI — **no page reload, no polling**.

## What it solves

When a user kicks off a slow operation (CSV import, PDF generation, API sync), most
Django apps either:

- Redirect to a polling page that hammers the server every few seconds, or
- Use a custom WebSocket + JavaScript stack that the developer has to wire up manually.

`django-live-operations` gives you a single `run(self, p)` method. Everything else
— WebSocket transport, HTML fragment updates, snapshot-on-connect, security tokens,
stage navigation, chaining — is handled by the framework.

## 30-second example

```python
# models.py
from live_operations.models import LiveOperation

class ImportPunktacji(LiveOperation):
    class Meta:
        app_label = "my_app"

    stages = ["Wczytaj", "Weryfikuj", "Zapisz"]

    def run(self, p):
        with p.stage("Wczytaj"):
            rows = list(p.track(load_csv(), label="Wczytywanie"))
        with p.stage("Weryfikuj"):
            valid = [r for r in rows if r.is_valid()]
        with p.stage("Zapisz"):
            for row in p.track(valid, label="Zapis"):
                row.save()
        p.result({"saved": len(valid)})
```

The user sees a live progress bar, stage stepper, log, and final result — all in-place,
without leaving the page. Works the same via CLI:

```bash
python manage.py run_liveop my_app.ImportPunktacji
```

## Features

- Live progress bar, status, log, stages via WebSocket + HTMX OOB swap
- Snapshot-on-connect: reconnecting clients immediately see current state
- FD#388 fix: operations that finish before the client connects deliver the
  result on connect (not "in progress") — state projection, not event stream
- Text/tqdm mode: the same `run()` works in CLI/management commands
- Stages and chaining: multi-step operations, no reload between steps
- Security: short-lived signed subscription tokens, owner-scoped channels
- Transport-neutral `Progress` API; web-only `swap/html` clearly marked
