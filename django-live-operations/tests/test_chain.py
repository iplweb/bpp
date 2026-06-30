"""
Phase 4 — Chain tests.

Covers:
- WebProgress.chain_to: current op finalized + liveop_chain envelope sent
  + OOB container swap + next_op enqueued
- TextProgress.chain_to: next op's run executed inline (side effect assert)
- Eager runner: ChainOpA chains to NextOp, both run to completion
"""
import io

import pytest
from django.contrib.auth import get_user_model

from live_operations.progress import TextProgress, WebProgress
from live_operations.runner import enqueue, task_run
from tests.models import ChainOpA, DemoOp, NextOp

User = get_user_model()


# ---- fixtures ---------------------------------------------------------------


class FakeChannelLayer:
    def __init__(self):
        self.sent: list[tuple[str, dict]] = []

    async def group_send(self, group: str, message: dict) -> None:
        self.sent.append((group, message))

    async def group_add(self, group: str, channel: str) -> None:
        pass

    async def group_discard(self, group: str, channel: str) -> None:
        pass


@pytest.fixture
def user(db):
    return User.objects.create_user("chain_user", password="x")


@pytest.fixture
def op_a(user):
    return DemoOp.objects.create(owner=user)


@pytest.fixture
def op_b(user):
    return NextOp.objects.create(owner=user)


@pytest.fixture
def fake_layer():
    return FakeChannelLayer()


# ---- WebProgress.chain_to ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_chain_to_finalizes_current_op(op_a, op_b, fake_layer):
    """chain_to commits finished_on + finished_successfully on current op."""
    wp = WebProgress(op_a, fake_layer)
    wp.chain_to(op_b)

    op_a.refresh_from_db()
    assert op_a.finished_successfully is True
    assert op_a.finished_on is not None
    assert wp._finalized is True


@pytest.mark.django_db(transaction=True)
def test_chain_to_pushes_liveop_chain_envelope(op_a, op_b, fake_layer):
    """chain_to sends a liveop_chain envelope with channel + token."""
    wp = WebProgress(op_a, fake_layer)
    wp.chain_to(op_b)

    chain_msgs = [
        msg
        for _, msg in fake_layer.sent
        if "liveop_chain" in msg
    ]
    assert chain_msgs, "No liveop_chain message sent"
    chain_data = chain_msgs[0]["liveop_chain"]
    assert "channel" in chain_data
    assert "token" in chain_data
    assert chain_data["channel"] == op_b.get_channel_name()
    assert len(chain_data["token"]) > 10


@pytest.mark.django_db(transaction=True)
def test_chain_to_pushes_container_oob_swap(op_a, op_b, fake_layer):
    """chain_to pushes an OOB HTML fragment replacing the current container."""
    wp = WebProgress(op_a, fake_layer)
    wp.chain_to(op_b)

    html_msgs = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent
        if "liveop_html" in msg
    ]
    assert html_msgs, "No liveop_html OOB push found"

    # The OOB HTML must carry hx-swap-oob with outerHTML targeting the
    # current op's container (#op-<current_pk>).
    combined = " ".join(html_msgs)
    assert f"op-{op_a.pk}" in combined
    assert "outerHTML" in combined

    # The new container for next_op must be embedded
    assert f"op-{op_b.pk}" in combined
    assert op_b.get_channel_name() in combined


@pytest.mark.django_db(transaction=True)
def test_chain_to_does_not_double_finalize(op_a, op_b, fake_layer):
    """chain_to is idempotent when _finalized is already True."""
    from django.utils import timezone

    op_a.finished_on = timezone.now()
    op_a.finished_successfully = True
    op_a.save()

    wp = WebProgress(op_a, fake_layer)
    wp._finalized = True
    wp.chain_to(op_b)

    # Should still send chain envelope without re-saving terminal state
    chain_msgs = [m for _, m in fake_layer.sent if "liveop_chain" in m]
    assert chain_msgs


@pytest.mark.django_db(transaction=True)
def test_chain_to_enqueues_next_op(op_a, fake_layer, user):
    """chain_to calls enqueue() so next_op runs and reaches terminal state."""
    # NextOp.run calls p.result() so it reaches finished_successfully=True
    op_b = NextOp.objects.create(owner=user)
    wp = WebProgress(op_a, fake_layer)
    wp.chain_to(op_b)

    op_b.refresh_from_db()
    assert op_b.finished_successfully is True


# ---- TextProgress.chain_to ---------------------------------------------------


def test_text_chain_to_runs_next_op_inline(user):
    """TextProgress.chain_to runs next_op using task_run (sets terminal state)."""
    op_a = DemoOp.objects.create(owner=user)
    op_b = NextOp.objects.create(owner=user)
    stream = io.StringIO()
    p = TextProgress(op_a, stream)

    p.chain_to(op_b)

    op_b.refresh_from_db()
    assert op_b.finished_successfully is True
    assert op_b.started_on is not None


def test_text_chain_to_uses_same_stream(user):
    """TextProgress.chain_to shares the stream with the next operation."""
    op_a = DemoOp.objects.create(owner=user)
    op_b = NextOp.objects.create(owner=user)
    stream = io.StringIO()
    p = TextProgress(op_a, stream)

    p.chain_to(op_b)

    # NextOp.run calls p.result({"next": "done"}) → prints next=done
    output = stream.getvalue()
    assert "next=done" in output


# ---- Eager runner chain: ChainOpA → NextOp ----------------------------------


@pytest.mark.django_db(transaction=True)
def test_eager_chain_both_ops_complete(user):
    """Eager runner: ChainOpA chains to NextOp; both reach finished_successfully."""
    op_a = ChainOpA.objects.create(owner=user)
    # eager runner auto-selects TextProgress (no channel layer in test context)
    enqueue(op_a)

    op_a.refresh_from_db()
    assert op_a.finished_successfully is True

    # ChainOpA.run creates NextOp and chains to it; find that NextOp
    next_ops = NextOp.objects.filter(owner=user)
    assert next_ops.exists(), "ChainOpA should have created a NextOp"
    next_op = next_ops.first()
    next_op.refresh_from_db()
    assert next_op.finished_successfully is True


@pytest.mark.django_db(transaction=True)
def test_web_chain_sequential_with_fake_layer(user, fake_layer):
    """WebProgress chain: op_a chains to op_b, liveop_chain signal sent."""
    op_a = ChainOpA.objects.create(owner=user)
    # Run chain manually with WebProgress + fake layer
    wp = WebProgress(op_a, fake_layer)
    task_run(op_a, wp)

    op_a.refresh_from_db()
    assert op_a.finished_successfully is True

    chain_msgs = [m for _, m in fake_layer.sent if "liveop_chain" in m]
    assert chain_msgs, "Expected liveop_chain signal from chain_to"

    # The next op (created inside ChainOpA.run) should also be finished
    next_ops = NextOp.objects.filter(owner=user)
    assert next_ops.exists()
    next_op = next_ops.first()
    next_op.refresh_from_db()
    assert next_op.finished_successfully is True
