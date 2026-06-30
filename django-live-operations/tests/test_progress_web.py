"""
Tests for WebProgress — uses a fake async channel layer.

§19.2: HTML travels in {"type":"chat_message","liveop_html":"<html>"}.
No top-level "id" key (would be auto-ACKed as Notification).
Fragment contains region id + hx-swap-oob.
"""
import pytest
from django.contrib.auth import get_user_model

from live_operations.progress import WebProgress
from tests.models import DemoOp

User = get_user_model()


class FakeChannelLayer:
    """Captures group_send calls for assertions."""

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
    return User.objects.create_user("web_user", password="x")


@pytest.fixture
def op(user):
    return DemoOp.objects.create(owner=user)


@pytest.fixture
def fake_layer():
    return FakeChannelLayer()


@pytest.fixture
def wp(op, fake_layer):
    return WebProgress(op, fake_layer)


# ---- envelope shape --------------------------------------------------------


def test_status_sends_liveop_html_envelope(wp, fake_layer):
    wp.status("Starting…")
    assert len(fake_layer.sent) == 1
    group, msg = fake_layer.sent[0]
    assert group == f"liveop.{wp._operation.pk}"
    assert "liveop_html" in msg
    assert "id" not in msg  # §19.2 — no top-level id


def test_status_fragment_has_region_id_and_oob(wp, fake_layer):
    wp.status("hello")
    html = fake_layer.sent[0][1]["liveop_html"]
    assert "op-status" in html
    assert "hx-swap-oob" in html


def test_log_fragment_has_oob(wp, fake_layer):
    wp.log("a log line")
    html = fake_layer.sent[0][1]["liveop_html"]
    assert "op-log" in html
    assert "hx-swap-oob" in html
    assert "a log line" in html


def test_percent_sends_progress_fragment(wp, fake_layer):
    # Reset throttle state so first call goes through
    wp._last_percent_send_time = 0.0
    wp._last_percent_value = -1
    wp._emit_percent(42)
    assert len(fake_layer.sent) == 1
    html = fake_layer.sent[0][1]["liveop_html"]
    assert "op-progress" in html
    assert "hx-swap-oob" in html
    assert "42" in html


def test_throttle_coalesces_rapid_same_value(wp, fake_layer, monkeypatch):
    """100 rapid calls with same value → only 1 send (time-throttled)."""
    import time

    fixed_time = [0.0]

    def fake_monotonic():
        return fixed_time[0]  # time never advances → always throttled

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    wp._last_percent_send_time = 0.0
    wp._last_percent_value = -1  # first call goes through (delta = 51 ≥ 1)

    for _ in range(100):
        wp.percent(50)

    # First call: delta = |50 - (-1)| = 51 ≥ 1 → sends.
    # Subsequent: delta = 0, time frozen → throttled.
    assert len(fake_layer.sent) == 1


def test_swap_sends_liveop_html(wp, fake_layer):
    wp.swap("#my-section", html_raw="<p>hello</p>")
    assert len(fake_layer.sent) == 1
    msg = fake_layer.sent[0][1]
    assert "liveop_html" in msg
    assert "id" not in msg  # §19.2


def test_html_sends_liveop_html(wp, fake_layer):
    wp.html("#my-id", "<span>raw</span>")
    assert len(fake_layer.sent) == 1
    msg = fake_layer.sent[0][1]
    assert "liveop_html" in msg
    assert "id" not in msg  # §19.2
    assert "my-id" in msg["liveop_html"]
    assert "hx-swap-oob" in msg["liveop_html"]


def test_track_yields_all_items(wp, op):
    items = list(range(5))
    result = list(wp.track(items))
    assert result == items


# ---- result / §19.4 commit ordering ----------------------------------------


@pytest.mark.django_db(transaction=True)
def test_result_commits_before_push(op, fake_layer):
    """
    §19.4: finished_* must be committed BEFORE liveop_html is pushed.
    With transaction=True, on_commit fires after the real commit.
    """
    wp = WebProgress(op, fake_layer)
    wp.result({"x": 1})

    op.refresh_from_db()
    assert op.finished_successfully is True
    assert op.result_context == {"x": 1}
    assert op.finished_on is not None
    # on_commit fired → result push happened
    result_messages = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent
        if "op-result" in msg.get("liveop_html", "")
    ]
    assert result_messages, "No op-result push found"
    assert "hx-swap-oob" in result_messages[0]


@pytest.mark.django_db(transaction=True)
def test_error_escapes_message_no_xss(op, fake_layer):
    """SECURITY: error() must escape the message — no raw markup/JS injection."""
    wp = WebProgress(op, fake_layer)
    wp.error("<script>alert('xss')</script>")

    pushes = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent
        if "op-result" in msg.get("liveop_html", "")
    ]
    assert pushes, "No error push found"
    frag = pushes[0]
    # The raw script tag must NOT appear; it must be HTML-escaped.
    assert "<script>" not in frag
    assert "&lt;script&gt;" in frag
    # The wrapper markup itself is still real HTML (oob swap works).
    assert 'id="op-result"' in frag
    assert "hx-swap-oob" in frag
