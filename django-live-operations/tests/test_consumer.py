"""
Tests for LiveOperationConsumer.

Scenarios:
- connect with valid token for FINISHED op → receives snapshot envelope
- connect with valid token for RUNNING op → receives running status snapshot
- manual group_send of a fragment → client receives it
- invalid token (wrong-user token) → connection closed
- stray ack_message frame → no crash, consumer still alive

Uses channels.testing.WebsocketCommunicator + InMemoryChannelLayer.
pytest-asyncio asyncio_mode="auto" (set in pyproject.toml).
"""
from __future__ import annotations

import json

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.utils import timezone

from live_operations.consumers import LiveOperationConsumer
from live_operations.security import make_subscription_token
from tests.models import DemoOp

User = get_user_model()


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _make_communicator(user, token: str) -> WebsocketCommunicator:
    app = LiveOperationConsumer.as_asgi()
    communicator = WebsocketCommunicator(
        app,
        f"/asgi/notifications/?subscription_token={token}",
    )
    communicator.scope["user"] = user
    return communicator


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #


@pytest.fixture
def user(db):
    return User.objects.create_user("cons_user", password="x")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("cons_other", password="x")


@pytest.fixture
def finished_op(user):
    return DemoOp.objects.create(
        owner=user,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
        result_context={"message": "done"},
    )


@pytest.fixture
def running_op(user):
    return DemoOp.objects.create(
        owner=user,
        started_on=timezone.now(),
    )


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #


@pytest.mark.django_db(transaction=True)
async def test_connect_finished_op_receives_snapshot(user, finished_op):
    """Valid token for a FINISHED op → snapshot fragment with op-result."""
    token = make_subscription_token(user, finished_op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected, "WebSocket connection should be accepted"

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "liveop_html" in data, "Snapshot must use liveop_html envelope"
    assert "id" not in data, "§19.2: no top-level id (would auto-ACK)"
    assert "op-result" in data["liveop_html"]
    assert "hx-swap-oob" in data["liveop_html"]

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_connect_running_op_receives_snapshot(user, running_op):
    """Valid token for a RUNNING op → snapshot status fragment."""
    token = make_subscription_token(user, running_op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "liveop_html" in data
    assert "hx-swap-oob" in data["liveop_html"]

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_manual_group_send_delivered_to_client(user, running_op):
    """A manual group_send on the operation's channel reaches the connected client."""
    token = make_subscription_token(user, running_op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    # Drain the connect-time snapshot
    await communicator.receive_from(timeout=2)

    # Manually push a fragment to the operation's group
    channel_layer = get_channel_layer()
    channel = running_op.get_channel_name()
    await channel_layer.group_send(
        channel,
        {
            "type": "chat_message",
            "liveop_html": '<div id="op-status" hx-swap-oob="true">pushed</div>',
        },
    )

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "liveop_html" in data
    assert "pushed" in data["liveop_html"]

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_invalid_token_connection_closed(user, finished_op, other_user):
    """Token for other_user is rejected when presented by user → closed."""
    # Token bound to other_user — presenting as user (different pk)
    wrong_token = make_subscription_token(other_user, finished_op)
    communicator = _make_communicator(user, wrong_token)

    connected, _ = await communicator.connect()
    if connected:
        # Consumer accepted but then closed (no liveop channels authorised)
        output = await communicator.receive_output(timeout=2)
        assert output["type"] == "websocket.close"
    else:
        # Rejected outright
        assert not connected


@pytest.mark.django_db(transaction=True)
async def test_stray_ack_message_no_crash(user, running_op):
    """Stray ack_message frame is silently absorbed; consumer stays alive."""
    token = make_subscription_token(user, running_op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    # Drain snapshot
    await communicator.receive_from(timeout=2)

    # Send a stray ack_message (id refers to nothing)
    await communicator.send_to(
        text_data=json.dumps({"type": "ack_message", "id": 999_999_999})
    )

    # Verify consumer is still alive by pushing a group message
    channel_layer = get_channel_layer()
    channel = running_op.get_channel_name()
    await channel_layer.group_send(
        channel,
        {"type": "chat_message", "liveop_html": "<div>still-alive</div>"},
    )

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "still-alive" in data.get("liveop_html", "")

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_snapshot_uses_liveop_html_envelope_no_id(user, running_op):
    """§19.2: snapshot must use liveop_html key; must NOT have top-level id."""
    token = make_subscription_token(user, running_op)
    communicator = _make_communicator(user, token)

    connected, _ = await communicator.connect()
    assert connected

    response = await communicator.receive_from(timeout=2)
    data = json.loads(response)
    assert "liveop_html" in data
    assert "id" not in data  # no top-level id — would trigger ACK loop

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_ack_message_delegated_to_base_handler(
    user, running_op, monkeypatch
):
    """ack_message frames are delegated to NotificationsConsumer.receive()."""
    import asyncio

    from channels_broadcast.consumers import NotificationsConsumer

    delegated: list = []
    original_receive = NotificationsConsumer.receive

    def spy_receive(self, text_data):
        delegated.append(json.loads(text_data))
        return original_receive(self, text_data)

    monkeypatch.setattr(NotificationsConsumer, "receive", spy_receive)

    token = make_subscription_token(user, running_op)
    communicator = _make_communicator(user, token)
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_from(timeout=2)  # drain snapshot

    await communicator.send_to(
        text_data=json.dumps({"type": "ack_message", "id": 0})
    )
    await asyncio.sleep(0.05)

    assert len(delegated) == 1
    assert delegated[0]["type"] == "ack_message"

    await communicator.disconnect()
