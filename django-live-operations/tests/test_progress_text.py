"""
Tests for TextProgress — captures stdout/StringIO, no channel layer.
"""
import io

import pytest
from django.contrib.auth import get_user_model

from live_operations.progress import OperationCancelled, TextProgress
from tests.models import DemoOp

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user("text_user", password="x")


@pytest.fixture
def op(user):
    return DemoOp.objects.create(owner=user)


def make_progress(op):
    stream = io.StringIO()
    return TextProgress(op, stream), stream


def test_status_prints(op):
    p, stream = make_progress(op)
    p.status("hello world")
    assert "hello world" in stream.getvalue()


def test_log_prints(op):
    p, stream = make_progress(op)
    p.log("log line here")
    assert "log line here" in stream.getvalue()


def test_track_yields_all_items(op):
    p, stream = make_progress(op)
    items = list(range(10))
    result = list(p.track(items))
    assert result == items


def test_track_with_total(op):
    p, stream = make_progress(op)

    def gen():
        yield from range(5)

    result = list(p.track(gen(), total=5))
    assert result == list(range(5))


def test_result_saves_terminal_state(op):
    p, stream = make_progress(op)
    p.result({"key": "value", "count": 42})

    op.refresh_from_db()
    assert op.finished_successfully is True
    assert op.finished_on is not None
    assert op.result_context == {"key": "value", "count": 42}


def test_result_prints_key_value_dump(op):
    p, stream = make_progress(op)
    p.result({"answer": 42})
    output = stream.getvalue()
    assert "answer=42" in output or "answer" in output


def test_result_kwargs_merge(op):
    p, stream = make_progress(op)
    p.result(extra_param="hello")
    op.refresh_from_db()
    assert op.result_context.get("extra_param") == "hello"


def test_swap_raises_not_implemented(op):
    p, stream = make_progress(op)
    with pytest.raises(NotImplementedError, match="webowe"):
        p.swap("#some-id", name="foo")


def test_html_raises_not_implemented(op):
    p, stream = make_progress(op)
    with pytest.raises(NotImplementedError, match="webowe"):
        p.html("#some-id", "<p>raw</p>")


def test_check_cancelled_raises_when_requested(op):
    op.cancel_requested = True
    op.save()
    p, _ = make_progress(op)
    with pytest.raises(OperationCancelled):
        p.check_cancelled()


def test_check_cancelled_ok_when_not_requested(op):
    p, _ = make_progress(op)
    p.check_cancelled()  # should not raise
