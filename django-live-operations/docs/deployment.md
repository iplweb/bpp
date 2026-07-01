# Deployment

> **Live updates require `RUNNER="celery"` + Redis.**
> The default `RUNNER="eager"` runs operations synchronously in the HTTP
> request thread — no WebSocket push, no live updates, the page blocks
> until the operation finishes and only shows the terminal snapshot on
> connect.  For production always set `RUNNER="celery"` and provide a
> Redis channel layer.

## Requirements

- ASGI server (Daphne or uvicorn)
- Redis (channel layer)
- Celery worker (for `RUNNER="celery"`)

## ASGI server

```bash
# Daphne
pip install daphne
daphne -b 0.0.0.0 -p 8000 myproject.asgi:application

# uvicorn
pip install uvicorn
uvicorn myproject.asgi:application --host 0.0.0.0 --port 8000
```

## Docker Compose example

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 myproject.asgi:application
    environment:
      - CHANNEL_LAYERS_REDIS=redis://redis:6379
    depends_on: [redis]
    ports: ["8000:8000"]

  worker:
    build: .
    command: celery -A myproject worker -l info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on: [redis]
```

## Settings for production

```python
import os

LIVE_OPERATIONS = {
    "BASE_TEMPLATE": "base.html",
    "RUNNER": "celery",
    "THROTTLE_HZ": 10,
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get(
                "CHANNEL_LAYERS_REDIS", "redis://redis:6379"
            )],
        },
    }
}

CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "redis://redis:6379/0"
)
```

## Client-side JavaScript

In your base template, include htmx, channels_broadcast, and
live-operations.js (in this order):

```html
{% load static %}
<script src="https://unpkg.com/htmx.org@1.9/dist/htmx.min.js"></script>
<script src="{% static 'channels_broadcast/js/notifications.js' %}"></script>
<script src="{% static 'live_operations/live-operations.js' %}"></script>
```

Both `channels_broadcast/js/notifications.js` and
`live_operations/live-operations.js` are shipped as Django static files by
their respective packages — `collectstatic` picks them up automatically.

## Eager mode (snapshot-only, no Redis/Celery)

For lightweight deployments that don't need live updates (operations run
synchronously and only terminal state is shown):

```python
LIVE_OPERATIONS = {
    "RUNNER": "eager",
    ...
}
```

The operation runs synchronously in the request thread. Progress pushes hit an
empty channel group (no connected client yet), so only the terminal snapshot is
delivered on connect. No Celery, no background thread — but the HTTP request
blocks until the operation finishes. Best for short operations or CI.

## Celery worker configuration

```python
# celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
app = Celery("myproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

The `live_operations` runner registers a Celery `shared_task` automatically
when Celery is installed. No manual task registration needed — `enqueue()`
dispatches `_celery_task.delay(app_label, model_name, pk)` which re-loads the
operation and runs it.

## Running the bundled demo

```bash
cd example/
docker compose up
```

Open `http://localhost:8000/`. The `seed_demo` management command creates a
demo user with auto-login (dev mode). You will see a live multi-stage operation
with a progress bar, log, and result — all without page reload.
