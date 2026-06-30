"""Tests for the {% live_operation %} templatetag and render_op_result."""
import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template

from tests.models import DemoOp

User = get_user_model()


@pytest.mark.django_db
def test_live_operation_tag_renders_channel():
    user = User.objects.create_user(username="taguser", password="pass")
    op = DemoOp.objects.create(owner=user)

    tpl = Template("{% load live_operations %}{% live_operation op %}")
    output = tpl.render(Context({"op": op}))

    assert f'data-liveop-channel="liveop.{op.pk}"' in output
    assert 'data-liveop-token="' in output
    assert len(op.subscription_token) > 20


@pytest.mark.django_db
def test_live_operation_tag_renders_region_ids():
    user = User.objects.create_user(username="taguser2", password="pass")
    op = DemoOp.objects.create(owner=user)

    tpl = Template("{% load live_operations %}{% live_operation op %}")
    output = tpl.render(Context({"op": op}))

    for region_id in ("op-status", "op-progress", "op-log", "op-result"):
        assert region_id in output, f"region id {region_id!r} missing from tag output"


@pytest.mark.django_db
def test_render_op_result_finished_op():
    from django.utils import timezone

    user = User.objects.create_user(username="taguser3", password="pass")
    op = DemoOp.objects.create(
        owner=user,
        finished_on=timezone.now(),
        finished_successfully=True,
        result_context={"answer": "42"},
    )

    tpl = Template("{% load live_operations %}{% render_op_result op %}")
    output = tpl.render(Context({"op": op}))

    assert "answer=42" in output


@pytest.mark.django_db
def test_render_op_result_fallback_escapes_values_no_xss():
    """SECURITY: key=value fallback must escape data-controlled values."""
    from django.utils import timezone

    user = User.objects.create_user(username="taguser_xss", password="pass")
    op = DemoOp.objects.create(
        owner=user,
        finished_on=timezone.now(),
        finished_successfully=True,
        result_context={"evil": "<script>alert('xss')</script>"},
    )

    tpl = Template("{% load live_operations %}{% render_op_result op %}")
    output = tpl.render(Context({"op": op}))

    assert "<script>" not in output
    assert "&lt;script&gt;" in output


@pytest.mark.django_db
def test_render_op_result_running_op_returns_empty():
    user = User.objects.create_user(username="taguser4", password="pass")
    op = DemoOp.objects.create(owner=user)

    tpl = Template("{% load live_operations %}{% render_op_result op %}")
    output = tpl.render(Context({"op": op}))

    assert output.strip() == ""
