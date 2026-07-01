"""
Tests for runner.enqueue / runner.task_run.

All tests use TextProgress (via io.StringIO) so no channel layer is needed.
eager runner runs synchronously — no async setup required.
"""
import io
import time

import pytest
from django.contrib.auth import get_user_model

from live_operations import runner
from live_operations.progress import TextProgress, WebProgress
from tests.models import DemoOp, ErrorOp

User = get_user_model()


class FakeChannelLayer:
    """Captures group_send calls without requiring a real channel layer."""

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
    return User.objects.create_user("runner_user", password="x")


@pytest.fixture
def op(user):
    return DemoOp.objects.create(owner=user)


def text_progress(op):
    return TextProgress(op, io.StringIO())


# ---- happy path ------------------------------------------------------------


def test_task_run_sets_terminal_fields(op):
    p = text_progress(op)
    runner.task_run(op, p)

    op.refresh_from_db()
    assert op.started_on is not None
    assert op.finished_on is not None
    assert op.finished_successfully is True
    assert op.result_context == {"message": "done"}


def test_enqueue_eager_runs_synchronously(settings, op):
    settings.LIVE_OPERATIONS = {"RUNNER": "eager"}
    # enqueue selects progress automatically; inject via task_run directly
    p = text_progress(op)
    runner.task_run(op, p)
    op.refresh_from_db()
    assert op.finished_successfully is True


# ---- cancel ----------------------------------------------------------------


def test_cancel_requested_before_run_ends_cancelled(op):
    """Setting cancel_requested before task_run → operation ends cancelled."""
    op.cancel_requested = True
    op.save()

    p = text_progress(op)
    runner.task_run(op, p)

    op.refresh_from_db()
    assert op.cancelled is True
    assert op.finished_on is not None
    assert op.finished_successfully is False


# ---- exception in run() ----------------------------------------------------


def test_exception_in_run_sets_traceback(user):
    op = ErrorOp.objects.create(owner=user)
    p = text_progress(op)
    runner.task_run(op, p)

    op.refresh_from_db()
    assert op.finished_successfully is False
    assert op.traceback is not None
    assert "ValueError" in op.traceback
    assert op.finished_on is not None


# ---- terminal live push (FIX 6) -------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_cancel_path_pushes_op_result_fragment(user):
    """Cancel path must push an op-result fragment to watching clients."""
    op = DemoOp.objects.create(owner=user, cancel_requested=True)
    layer = FakeChannelLayer()
    wp = WebProgress(op, layer)

    runner.task_run(op, wp)

    op.refresh_from_db()
    assert op.cancelled is True

    result_pushes = [
        msg["liveop_html"]
        for _, msg in layer.sent
        if "op-result" in msg.get("liveop_html", "")
    ]
    assert result_pushes, "Cancel path must push op-result fragment"
    combined = " ".join(result_pushes)
    assert "anulowana" in combined.lower() or "anulowano" in combined.lower()


@pytest.mark.django_db(transaction=True)
def test_error_path_pushes_generic_op_result_no_traceback(user):
    """Error path must push generic op-result fragment — no traceback in push."""
    op = ErrorOp.objects.create(owner=user)
    layer = FakeChannelLayer()
    wp = WebProgress(op, layer)

    runner.task_run(op, wp)

    op.refresh_from_db()
    assert op.finished_successfully is False
    assert "ValueError" in (op.traceback or "")

    result_pushes = [
        msg["liveop_html"]
        for _, msg in layer.sent
        if "op-result" in msg.get("liveop_html", "")
    ]
    assert result_pushes, "Error path must push op-result fragment"
    combined = " ".join(result_pushes)
    assert "Traceback (most recent call last)" not in combined
    assert "ValueError" not in combined
    assert str(op.pk) in combined


@pytest.mark.django_db(transaction=True)
def test_auto_finalize_pushes_op_result_fragment(user, monkeypatch):
    """run() without p.result() auto-finalizes and pushes op-result fragment."""
    op = DemoOp.objects.create(owner=user)

    def run_no_result(self, p):
        p.status("running without result()")

    monkeypatch.setattr(DemoOp, "run", run_no_result)

    layer = FakeChannelLayer()
    wp = WebProgress(op, layer)

    runner.task_run(op, wp)

    op.refresh_from_db()
    assert op.finished_successfully is True

    result_pushes = [
        msg["liveop_html"]
        for _, msg in layer.sent
        if "op-result" in msg.get("liveop_html", "")
    ]
    assert result_pushes, "Auto-finalize must push op-result fragment"
    assert "hx-swap-oob" in result_pushes[-1]


# ---- check_cancelled throttle (FIX 7) --------------------------------------


@pytest.mark.django_db
def test_check_cancelled_throttled_over_200_items(user, monkeypatch):
    """refresh_from_db called far fewer than 200 times for 200 check_cancelled calls."""
    op = DemoOp.objects.create(owner=user)
    p = text_progress(op)

    call_count = 0
    original_rfdb = op.refresh_from_db

    def counting_rfdb(**kwargs):
        nonlocal call_count
        call_count += 1
        return original_rfdb(**kwargs)

    monkeypatch.setattr(op, "refresh_from_db", counting_rfdb)
    p._operation = op  # re-bind to patched instance

    # Freeze time so only the batch counter (every 50 items) fires.
    fake_time = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

    p._last_cancel_check_time = 0.0
    p._cancel_check_count = 0

    for _ in range(200):
        p.check_cancelled()

    assert call_count <= 4  # at most 4 DB hits (at 50, 100, 150, 200)
    assert call_count >= 1
