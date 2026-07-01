# Text/CLI Mode

The same `run(self, p)` method that powers the WebSocket UI can also run in a
terminal with tqdm progress bars.

## Management command

```bash
python manage.py run_liveop <app_label>.<ModelName> [--owner USERNAME]
```

Examples:

```bash
# Run DemoImport as the 'admin' user
python manage.py run_liveop demo.DemoImport --owner admin

# Owner defaults to the first superuser (created as admin/admin if none exists)
python manage.py run_liveop demo.DemoImport
```

The command creates a new operation instance, runs it synchronously with
`TextProgress` (tqdm if installed, else plain `print`), and reports the final
state. No Redis, no Celery, no browser required.

## Programmatic text run

```python
from live_operations.progress import TextProgress
from live_operations.runner import task_run

op = MyOp.objects.create(owner=user)
p = TextProgress(op)
task_run(op, p)
```

## tqdm integration

If `tqdm` is installed (`pip install django-live-operations[cli]`), `p.track()`
uses a native tqdm progress bar. Otherwise it falls back to periodic `print` at
10% intervals.

## What maps and what doesn't

| Feature | Web | Text |
|---------|-----|------|
| `p.status(text)` | Updates `#op-status` via OOB | `print(text)` |
| `p.percent(n)` | Updates `#op-progress` bar | tqdm bar or print |
| `p.log(line)` | Appends to `#op-log` | `print(line)` |
| `p.stage(name)` | Updates `#op-stages` stepper | `=== [n/N] name ===` header |
| `p.result(ctx)` | Renders result template OOB | key=value dump or `*_result.txt` |
| `p.check_cancelled()` | Reads DB | Reads DB |
| `p.chain_to(next)` | Re-inits WS to next op | Runs next op inline |
| `p.swap(selector, …)` | OOB swap any region | **NotImplementedError** |
| `p.html(selector, raw)` | OOB raw HTML | **NotImplementedError** |

`swap` and `html` are web-only. A `run()` that calls them raises
`NotImplementedError` in text mode. If you need CLI portability, use
`p.log()`, `p.status()`, and `p.result()` only.

## Result output in text mode

`p.result(context)` in text mode:

1. Tries to find `<app>/<snake>_result.txt` template and renders it.
2. If not found, prints `key=value` for each item in `context`.

The `.txt` template is optional. One `run()` method works without it.
