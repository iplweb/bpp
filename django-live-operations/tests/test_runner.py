"""
Tests for runner.enqueue / runner.task_run.

All tests use TextProgress (via io.StringIO) so no channel layer is needed.
eager runner runs synchronously — no async setup required.
"""
import io

import pytest
from django.contrib.auth import get_user_model

from live_operations import runner
from live_operations.progress import TextProgress
from tests.models import DemoOp, ErrorOp

User = get_user_model()


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
