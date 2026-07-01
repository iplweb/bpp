# Testing

`django-live-operations` uses a three-tier test approach.

## Tier 1: Unit tests (InMemory channel layer)

Fast tests with no external dependencies. Use
`channels.layers.InMemoryChannelLayer` (the default in test settings).

```python
# tests/settings.py
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

Test the consumer with `WebsocketCommunicator`:

```python
import json
import pytest
from channels.testing import WebsocketCommunicator
from live_operations.consumers import LiveOperationConsumer
from live_operations.security import make_subscription_token


@pytest.mark.django_db(transaction=True)
async def test_snapshot_on_connect(user, finished_op):
    token = make_subscription_token(user, finished_op)
    app = LiveOperationConsumer.as_asgi()
    communicator = WebsocketCommunicator(
        app, f"/asgi/notifications/?subscription_token={token}"
    )
    communicator.scope["user"] = user

    connected, _ = await communicator.connect()
    assert connected

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "liveop_html" in data
    assert "op-result" in data["liveop_html"]
    await communicator.disconnect()
```

## Tier 2: Progress tests (fake channel layer)

Test `WebProgress` by capturing what `group_send` receives, without a real
channel layer:

```python
import pytest
from asgiref.sync import sync_to_async
from unittest.mock import MagicMock
from live_operations.progress import WebProgress


@pytest.mark.django_db
def test_progress_status_pushes_envelope(running_op):
    sent = []
    mock_layer = MagicMock()
    mock_layer.group_send = sync_to_async(
        lambda channel, msg: sent.append(msg)
    )

    p = WebProgress(running_op, mock_layer)
    p.status("Testing…")

    assert sent
    assert "op-status" in sent[0]["liveop_html"]
```

## Tier 3: Round-trip tests (real Redis via testcontainers)

The strongest proof: worker → Redis → consumer → client. Requires Docker.

```python
# tests/test_roundtrip.py
import pytest
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_url():
    with RedisContainer("redis:7-alpine") as c:
        host = c.get_container_host_ip()
        port = c.get_exposed_port(6379)
        yield f"redis://{host}:{port}"


@pytest.fixture
def redis_channel_layer(settings, redis_url):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [redis_url]},
        }
    }
    yield


@pytest.mark.django_db(transaction=True)
async def test_fd388(user, redis_channel_layer):
    # finish op before connect, then assert snapshot == result
    ...
```

See the bundled `tests/test_roundtrip.py` for the complete implementation
including the FD#388 case and §19.4 ordering test. If Docker is unavailable the
module skips itself with a clear reason (never a false pass).

## pytest configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
asyncio_mode = "auto"
testpaths = ["tests"]
```

Use `@pytest.mark.django_db(transaction=True)` for all async consumer tests.
With `transaction=True`, Django commits real transactions — required for
`on_commit` callbacks (used by `p.result()`) to fire correctly.

## Tips

- The `settings` fixture (pytest-django) is the cleanest way to override
  `CHANNEL_LAYERS` per-test. Django's `ChannelLayerManager` clears its backend
  cache automatically when the setting changes (via the `setting_changed`
  signal), so the next `get_channel_layer()` returns the new backend.
- Session-scoped Redis container + function-scoped settings override = one
  container for the whole session, fresh channel-layer config per test.
