# django-live-operations — demo

## One command (browser demo)

```bash
make demo
```

Opens `http://localhost:8000`. The `web` container runs `seed_demo` on
startup — visit `http://localhost:8000/__login__/` to log in as `demo/demo`,
then click **+ Nowy import** and watch 5 stages of live progress (WebSocket,
no reload).

What you'll see:
- Stage stepper advances through Wczytanie → Walidacja → Dopasowanie → Zapis → Raport.
- Progress bar resets per stage.
- Log lines stream in real time.
- When done: a result table appears (total/ok/skipped/errors) — no page reload.

## Zero-infra text path (no Docker, no Redis, no browser)

```bash
make demo-text
```

Runs `DemoImport` synchronously in `TextProgress` mode (stdout). tqdm bar
if installed, else plain percent prints. No Redis, no ASGI, no browser needed.
Useful for CI smoke tests.

## Stack

| Service | Role |
|---------|------|
| `redis:7` | Channel layer broker |
| `web`   | Daphne ASGI on :8000 (migrate + seed on start) |
| `worker` | Celery worker consuming liveop tasks |

## Auto-login

`/__login__/` logs you in as the first superuser (dev only, `DEBUG=True`).
This is how `make demo` skips the login form.
