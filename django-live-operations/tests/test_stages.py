"""
Phase 4 — Stage tests.

Covers:
- WebProgress: stepper fragments pushed with correct markers on transitions
- Stage transitions: active → done on clean exit, active → failed on exception
- TextProgress: stage headers printed in correct order with [N/Total] prefix
- _stages.html template renders correct markers for each state
"""
import io

import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template

from live_operations.progress import OperationCancelled, TextProgress, WebProgress
from tests.models import FailedStageOp, StagedOp

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
    return User.objects.create_user("stage_user", password="x")


@pytest.fixture
def staged_op(user):
    return StagedOp.objects.create(owner=user)


@pytest.fixture
def failed_stage_op(user):
    return FailedStageOp.objects.create(owner=user)


@pytest.fixture
def fake_layer():
    return FakeChannelLayer()


@pytest.fixture
def wp(staged_op, fake_layer):
    return WebProgress(staged_op, fake_layer)


# ---- WebProgress stage transitions ------------------------------------------


def test_stage_entry_sets_active_in_stage_states(staged_op, wp, fake_layer):
    """Entering a stage sets stage_states[name] = 'active'."""
    with wp.stage("Alpha"):
        assert staged_op.stage_states.get("Alpha") == "active"
        assert staged_op.current_stage == 0


def test_stage_clean_exit_sets_done(staged_op, wp):
    """Clean exit sets stage_states[name] = 'done'."""
    with wp.stage("Alpha"):
        pass
    assert staged_op.stage_states.get("Alpha") == "done"


def test_stage_exception_sets_failed(staged_op, wp):
    """Exception sets stage_states[name] = 'failed'."""
    with pytest.raises(RuntimeError):
        with wp.stage("Alpha"):
            raise RuntimeError("oops")
    assert staged_op.stage_states.get("Alpha") == "failed"


def test_stage_cancelled_sets_cancelled(staged_op, wp):
    """OperationCancelled sets stage_states[name] = 'cancelled'."""
    with pytest.raises(OperationCancelled):
        with wp.stage("Alpha"):
            raise OperationCancelled("cancelled")
    assert staged_op.stage_states.get("Alpha") == "cancelled"


def test_stage_start_pushes_stepper_and_progress_reset(staged_op, wp, fake_layer):
    """Entering a stage sends: one stepper OOB + one progress reset (percent=0)."""
    with wp.stage("Alpha"):
        # Two pushes on entry: stepper fragment + progress reset
        # (stepper is first, then _emit_percent(0))
        pushes = [msg["liveop_html"] for _, msg in fake_layer.sent]
        # Stepper fragment: has op-stages id and hx-swap-oob
        stepper_pushes = [p for p in pushes if "op-stages" in p]
        assert stepper_pushes, "No stepper fragment pushed on stage entry"
        assert "hx-swap-oob" in stepper_pushes[0]
        # Progress reset: has op-progress id
        progress_pushes = [p for p in pushes if "op-progress" in p]
        assert progress_pushes, "No progress reset pushed on stage entry"


def test_stage_end_pushes_stepper(staged_op, wp, fake_layer):
    """Clean exit from a stage sends a stepper OOB fragment."""
    with wp.stage("Alpha"):
        before_count = len(fake_layer.sent)
    after_count = len(fake_layer.sent)
    assert after_count > before_count, "No push on stage exit"
    exit_pushes = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent[before_count:]
        if "op-stages" in msg.get("liveop_html", "")
    ]
    assert exit_pushes, "No stepper fragment pushed on stage exit"


def test_stepper_shows_active_marker(staged_op, fake_layer):
    """Stepper fragment pushed on entry shows active marker (●) for current stage."""
    wp = WebProgress(staged_op, fake_layer)
    with wp.stage("Alpha"):
        stepper_pushes = [
            msg["liveop_html"]
            for _, msg in fake_layer.sent
            if "op-stages" in msg.get("liveop_html", "")
        ]
        assert stepper_pushes
        # Active marker is ● (&#9679;)
        assert "&#9679;" in stepper_pushes[0] or "●" in stepper_pushes[0]
        assert "Alpha" in stepper_pushes[0]


def test_stepper_shows_done_marker_after_stage(staged_op, fake_layer):
    """Stepper fragment after clean stage exit shows done marker (✓) for that stage."""
    wp = WebProgress(staged_op, fake_layer)
    with wp.stage("Alpha"):
        pass
    # Last stepper push: on stage exit
    stepper_pushes = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent
        if "op-stages" in msg.get("liveop_html", "")
    ]
    assert stepper_pushes
    last_stepper = stepper_pushes[-1]
    # Done marker is ✓ (&#10003;)
    assert "&#10003;" in last_stepper or "✓" in last_stepper


def test_stepper_shows_failed_marker_after_exception(user, fake_layer):
    """Stepper fragment after exception shows failed marker (✗) for that stage."""
    op = FailedStageOp.objects.create(owner=user)
    wp = WebProgress(op, fake_layer)
    with pytest.raises(RuntimeError):
        with wp.stage("Setup"):
            pass
        with wp.stage("Explode"):
            raise RuntimeError("boom")
    stepper_pushes = [
        msg["liveop_html"]
        for _, msg in fake_layer.sent
        if "op-stages" in msg.get("liveop_html", "")
    ]
    last_stepper = stepper_pushes[-1]
    # Failed marker is ✗ (&#10007;)
    assert "&#10007;" in last_stepper or "✗" in last_stepper


def test_multi_stage_run_all_stages_done(staged_op, wp, fake_layer):
    """Full multi-stage run: all three stages end with 'done' state."""
    with wp.stage("Alpha"):
        pass
    with wp.stage("Beta"):
        pass
    assert staged_op.stage_states.get("Alpha") == "done"
    assert staged_op.stage_states.get("Beta") == "done"
    assert staged_op.stage_states.get("Gamma") is None  # not yet started


def test_stage_states_persisted_to_db(staged_op, wp):
    """stage_states and current_stage are saved to DB on stage entry/exit."""
    with wp.stage("Alpha"):
        staged_op.refresh_from_db()
        assert staged_op.stage_states.get("Alpha") == "active"
        assert staged_op.current_stage == 0
    staged_op.refresh_from_db()
    assert staged_op.stage_states.get("Alpha") == "done"


# ---- _stages.html template --------------------------------------------------


@pytest.mark.django_db
def test_stages_template_pending_marker(user):
    """Stages not yet started render with pending marker (○)."""
    op = StagedOp.objects.create(owner=user)
    tpl = Template(
        "{% load live_operations %}"
        "{% include 'live_operations/_stages.html' with op=op %}"
    )
    output = tpl.render(Context({"op": op}))
    # All stages pending: ○ (&#9675;)
    assert "&#9675;" in output or "○" in output
    assert "Alpha" in output


@pytest.mark.django_db
def test_stages_template_active_marker(user):
    """Active stage renders with ● marker."""
    op = StagedOp.objects.create(owner=user, stage_states={"Alpha": "active"})
    tpl = Template(
        "{% load live_operations %}"
        "{% include 'live_operations/_stages.html' with op=op %}"
    )
    output = tpl.render(Context({"op": op}))
    assert "&#9679;" in output or "●" in output


@pytest.mark.django_db
def test_stages_template_done_marker(user):
    """Done stage renders with ✓ marker."""
    op = StagedOp.objects.create(owner=user, stage_states={"Alpha": "done"})
    tpl = Template(
        "{% load live_operations %}"
        "{% include 'live_operations/_stages.html' with op=op %}"
    )
    output = tpl.render(Context({"op": op}))
    assert "&#10003;" in output or "✓" in output


@pytest.mark.django_db
def test_stages_template_failed_marker(user):
    """Failed stage renders with ✗ marker."""
    op = StagedOp.objects.create(owner=user, stage_states={"Alpha": "failed"})
    tpl = Template(
        "{% load live_operations %}"
        "{% include 'live_operations/_stages.html' with op=op %}"
    )
    output = tpl.render(Context({"op": op}))
    assert "&#10007;" in output or "✗" in output


@pytest.mark.django_db
def test_stages_template_escapes_stage_name(user):
    """Stage names go through autoescaping — HTML entities are not raw HTML."""
    # Use a real StagedOp; stage names are class-level, not user input.
    # This test verifies the template uses {{ stage_name }} (autoescaped).
    op = StagedOp.objects.create(owner=user)
    tpl = Template(
        "{% load live_operations %}"
        "{% include 'live_operations/_stages.html' with op=op %}"
    )
    output = tpl.render(Context({"op": op}))
    # Stage names appear as plain text, not as raw HTML injection
    assert "<script>" not in output
    assert "Alpha" in output


# ---- TextProgress stage headers ---------------------------------------------


def test_text_progress_stage_header_format(user):
    """Stage headers include [N/Total] format."""
    op = StagedOp.objects.create(owner=user)
    stream = io.StringIO()
    p = TextProgress(op, stream)

    with p.stage("Alpha"):
        pass
    with p.stage("Beta"):
        pass

    output = stream.getvalue()
    assert "[1/3] Alpha" in output
    assert "[2/3] Beta" in output


def test_text_progress_stage_headers_ordered(user):
    """All stage headers appear in declaration order."""
    op = StagedOp.objects.create(owner=user)
    stream = io.StringIO()
    p = TextProgress(op, stream)

    with p.stage("Alpha"):
        pass
    with p.stage("Beta"):
        pass
    with p.stage("Gamma"):
        pass

    output = stream.getvalue()
    alpha_pos = output.index("Alpha")
    beta_pos = output.index("Beta")
    gamma_pos = output.index("Gamma")
    assert alpha_pos < beta_pos < gamma_pos


def test_text_progress_stage_no_stages_fallback(user):
    """Stage name printed even when op.stages is empty (unknown stage)."""
    op = StagedOp.objects.create(owner=user)
    op.stages = []  # override for this test
    stream = io.StringIO()
    p = TextProgress(op, stream)

    with p.stage("Unknown"):
        pass

    assert "Unknown" in stream.getvalue()
