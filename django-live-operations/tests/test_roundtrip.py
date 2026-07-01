"""
Round-trip tests: worker → Redis channel layer → WebsocketCommunicator.

These tests exercise the FULL path and require Docker + testcontainers[redis].
If Docker or testcontainers is unavailable, the entire module is skipped with
a clear reason.

Tests:
1. Connect to a RUNNING op → WebProgress pushes status/log → client receives
   the {"liveop_html": ...} frames via Redis.
2. FD#388 case: op FINISHES before client connects → snapshot-on-connect
   delivers the RESULT fragment (not "in progress"). This is the headline
   guarantee of django-live-operations.
3. §19.4 ordering: result() called inside transaction.atomic() → terminal
   state committed to DB before result fragment is delivered; late connector
   sees result.
"""
from __future__ import annotations

import asyncio
import json
import subprocess

import pytest

# ---------------------------------------------------------------------------
# Guard: skip module if testcontainers or Docker unavailable
# ---------------------------------------------------------------------------

try:
    from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

    _TC_AVAILABLE = True
except ImportError:
    _TC_AVAILABLE = False
    RedisContainer = None  # type: ignore[assignment,misc]

if not _TC_AVAILABLE:
    pytest.skip(
        "testcontainers not installed — install django-live-operations[dev] "
        "to run round-trip tests",
        allow_module_level=True,
    )


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


if not _docker_available():
    pytest.skip(
        "Docker is not available — round-trip tests require a running Docker daemon",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Imports (only reached when testcontainers + Docker are available)
# ---------------------------------------------------------------------------
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from live_operations.consumers import LiveOperationConsumer
from live_operations.progress import WebProgress
from live_operations.security import make_subscription_token
from tests.models import DemoOp

User = get_user_model()

# ---------------------------------------------------------------------------
# Session-scoped Redis container
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_url():
    """Start a Redis 7 container; yield its URL; stop on session end."""
    with RedisContainer("redis:7-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}"


# ---------------------------------------------------------------------------
# Per-test channel layer override
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_channel_layer(settings, redis_url):
    """Override CHANNEL_LAYERS to point at the Redis testcontainer.

    Django's ChannelLayerManager listens to the setting_changed signal and
    clears its backend cache automatically when CHANNEL_LAYERS changes, so
    the next get_channel_layer() call returns a fresh RedisChannelLayer
    pointed at the container.
    """
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [redis_url],
            },
        }
    }
    yield
    # settings fixture restores the original value on teardown,
    # which fires setting_changed → clears backends cache.


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_communicator(user, token: str) -> WebsocketCommunicator:
    app = LiveOperationConsumer.as_asgi()
    communicator = WebsocketCommunicator(
        app,
        f"/asgi/notifications/?subscription_token={token}",
    )
    communicator.scope["user"] = user
    return communicator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user("rt_user", password="x")


# ---------------------------------------------------------------------------
# Test 1: Running op → WebProgress pushes → client receives
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_webprogress_delivers_to_connected_client(
    user, redis_channel_layer
):
    """
    Full Redis round-trip: WebProgress.status()/log() → Redis group_send →
    LiveOperationConsumer → WebsocketCommunicator receives the frame.

    Proves that the JSON envelope {"liveop_html": ...} is transported via
    the real Redis channel layer end-to-end (§19.2).
    """
    from django.utils import timezone

    op = await asyncio.to_thread(
        DemoOp.objects.create,
        owner=user,
        started_on=timezone.now(),
    )
    token = await asyncio.to_thread(make_subscription_token, user, op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected, "WebSocket connection must be accepted"

    # Drain the connect-time snapshot
    snap_raw = await communicator.receive_from(timeout=10)
    snap = json.loads(snap_raw)
    assert "liveop_html" in snap

    # Simulate a Celery/threading worker pushing status via WebProgress
    layer = get_channel_layer()
    p = WebProgress(op, layer)
    await asyncio.to_thread(p.status, "Crunching numbers…")

    frame_raw = await communicator.receive_from(timeout=10)
    frame = json.loads(frame_raw)
    assert "liveop_html" in frame, (
        "WebProgress.status() must arrive via Redis as liveop_html envelope"
    )
    assert "id" not in frame, "§19.2: envelope must NOT have top-level id"
    assert "op-status" in frame["liveop_html"]
    assert "Crunching numbers" in frame["liveop_html"]

    # Also verify log delivery
    await asyncio.to_thread(p.log, "row 42 processed")
    log_raw = await communicator.receive_from(timeout=10)
    log_frame = json.loads(log_raw)
    assert "row 42 processed" in log_frame.get("liveop_html", ""), (
        "WebProgress.log() must arrive via Redis"
    )

    await communicator.disconnect()


# ---------------------------------------------------------------------------
# Test 2: FD#388 — op finishes BEFORE client connects → snapshot = result
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_fd388_late_connector_receives_result_snapshot(
    user, redis_channel_layer
):
    """
    FD#388 headline guarantee:

    An operation that finishes BEFORE the client connects delivers the RESULT
    fragment on connect — not the "in progress" status.

    The original failure: result push → client connects → snapshot shows
    "in progress" (DB not yet read or race condition) → page reloads →
    infinite loop. Fix: snapshot-on-connect reads terminal state from DB and
    renders the result fragment directly.

    This test asserts that guarantee explicitly using a real Redis layer.
    """
    from django.utils import timezone

    op = await asyncio.to_thread(
        DemoOp.objects.create,
        owner=user,
        started_on=timezone.now(),
    )

    # --- Op finishes BEFORE client connects ---
    # WebProgress.result() commits terminal state to DB (autocommit) and
    # via on_commit pushes the result fragment — but no client is connected
    # yet, so that push lands in an empty group and is lost.
    layer = get_channel_layer()
    p = WebProgress(op, layer)
    await asyncio.to_thread(p.result, {"message": "import complete"})

    # Sanity: verify DB has the terminal state committed
    await asyncio.to_thread(op.refresh_from_db)
    assert op.finished_successfully is True, (
        "Terminal state must be committed to DB before the client connects"
    )
    assert op.result_context == {"message": "import complete"}

    # --- Client connects AFTER op finishes ---
    token = await asyncio.to_thread(make_subscription_token, user, op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    snap_raw = await communicator.receive_from(timeout=10)
    snap = json.loads(snap_raw)
    assert "liveop_html" in snap

    html = snap["liveop_html"]

    # THE FD#388 GUARANTEE: snapshot must show the RESULT, not "in progress"
    assert "op-result" in html, (
        "FD#388: late connector must receive the result fragment, "
        "not the in-progress status — snapshot-on-connect reads DB state"
    )
    assert "hx-swap-oob" in html
    assert "Operation in progress" not in html, (
        "FD#388: snapshot must NOT show 'in progress' for a finished operation"
    )

    await communicator.disconnect()


# ---------------------------------------------------------------------------
# Test 3: §19.4 — terminal committed before result push
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_s19_4_terminal_committed_before_result_push(
    user, redis_channel_layer
):
    """
    §19.4: when result() is called inside transaction.atomic(), the terminal
    state is committed to DB BEFORE the result fragment is delivered.

    transaction.on_commit defers _push_result until the outermost transaction
    commits. A late connector (joining after the atomic block exits) therefore
    sees both:
      - the DB state committed (refresh_from_db shows finished_successfully)
      - the snapshot delivering the result fragment

    This ensures there is no window where the result has been pushed but the
    DB hasn't committed yet (the FD#388 race condition).
    """
    from django.db import transaction
    from django.utils import timezone

    op = await asyncio.to_thread(
        DemoOp.objects.create,
        owner=user,
        started_on=timezone.now(),
    )
    layer = get_channel_layer()
    p = WebProgress(op, layer)

    def _run_inside_atomic() -> None:
        """
        Inside transaction.atomic():
          - op.save() writes within the transaction (not yet committed to DB)
          - on_commit(_push_result) is deferred until the outermost atomic exits

        After the 'with' block: DB commits, on_commit fires, result pushed.
        At that point no client is connected, so the push is lost — but the
        DB commit is real and the late connector's snapshot reads it.
        """
        with transaction.atomic():
            p.result({"message": "atomic done"})
        # Here: DB committed AND on_commit has fired (push sent to empty group)

    await asyncio.to_thread(_run_inside_atomic)

    # Verify DB committed
    await asyncio.to_thread(op.refresh_from_db)
    assert op.finished_successfully is True, (
        "§19.4: DB must be committed after transaction.atomic() exits"
    )
    assert op.result_context == {"message": "atomic done"}

    # Late connector — must see result, not "in progress"
    token = await asyncio.to_thread(make_subscription_token, user, op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    snap_raw = await communicator.receive_from(timeout=10)
    snap = json.loads(snap_raw)
    html = snap.get("liveop_html", "")

    assert "op-result" in html, (
        "§19.4: after atomic commit, late connector must see result fragment"
    )
    assert "Operation in progress" not in html, (
        "§19.4: snapshot must not show in-progress after terminal commit"
    )

    await communicator.disconnect()
