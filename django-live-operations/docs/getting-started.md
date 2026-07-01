# Getting Started

## Installation

```bash
pip install django-live-operations
# With Redis support (production):
pip install django-live-operations[redis]
# With Celery worker:
pip install django-live-operations[celery]
# With tqdm CLI mode:
pip install django-live-operations[cli]
```

## 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    "channels",
    "channels_broadcast",
    "live_operations",
]
```

## 2. Configure channel layer

For development (no Redis):

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

For production (Redis):

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("redis", 6379)],
        },
    }
}
```

## 3. ASGI application + routing

Create `asgi.py` (or update your existing one):

```python
# asgi.py
import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from live_operations.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

## 4. Live Operations settings

Add to `settings.py`:

```python
LIVE_OPERATIONS = {
    "BASE_TEMPLATE": "base.html",   # your project's base template
    "RUNNER": "celery",             # "eager" | "threading" | "celery"
    "THROTTLE_HZ": 10,              # max percent updates per second
    # "REQUIRED_GROUP": "operators", # optional: restrict access to a group
}
```

> **Production requirement:** live updates (WebSocket push) require
> `RUNNER="celery"` (or `"threading"`) **and** a Redis channel layer.
> The default `RUNNER="eager"` runs operations synchronously in the
> HTTP request — no live updates, no Redis required, but the page
> blocks until the operation finishes and only shows terminal state.

## 4a. Client-side JavaScript

In your base template, include htmx, the channels_broadcast client, and
live-operations.js (in this order):

```html
{% load static %}
<script src="https://unpkg.com/htmx.org@1.9/dist/htmx.min.js"></script>
<script src="{% static 'channels_broadcast/js/notifications.js' %}"></script>
<script src="{% static 'live_operations/live-operations.js' %}"></script>
```

## 5. Run the demo

```bash
cd example/
pip install -e ..[dev]
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
# or with full stack:
docker compose up
```

Open the URL printed by the seed command. You will see a live progress bar,
stage stepper, log, and result — all without page reload.
