"""
Tests for LiveOperation model: get_state transitions, abstract run raises,
naming resolvers delegate correctly.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from tests.models import DemoOp

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user("testuser", password="testpass")


@pytest.fixture
def op(user):
    return DemoOp.objects.create(owner=user)


class TestGetState:
    def test_not_started(self, op):
        assert op.get_state() == "NOT_STARTED"

    def test_started(self, op):
        op.started_on = timezone.now()
        op.save()
        assert op.get_state() == "STARTED"

    def test_finished_ok(self, op):
        op.started_on = timezone.now()
        op.finished_on = timezone.now()
        op.finished_successfully = True
        op.save()
        assert op.get_state() == "FINISHED_OK"

    def test_finished_error(self, op):
        op.started_on = timezone.now()
        op.finished_on = timezone.now()
        op.finished_successfully = False
        op.save()
        assert op.get_state() == "FINISHED_ERROR"

    def test_cancelled(self, op):
        op.cancelled = True
        op.save()
        assert op.get_state() == "CANCELLED"


class TestNamingResolvers:
    def test_channel_name(self, op):
        assert op.get_channel_name() == f"liveop.{op.pk}"

    def test_host_template_name(self, op):
        assert op.get_host_template_name() == "tests/demo_op.html"

    def test_result_template_name(self, op):
        assert op.get_result_template_name() == "tests/demo_op_result.html"


class TestAbstractRun:
    def test_base_run_raises(self, user):
        from live_operations.models import LiveOperation

        class Concrete(LiveOperation):
            class Meta:
                app_label = "tests"
                abstract = True

        instance = Concrete.__new__(Concrete)
        with pytest.raises(NotImplementedError):
            LiveOperation.run(instance, None)


class TestErrorSnapshotNoTraceback:
    """FIX 5: FINISHED_ERROR snapshot must not leak traceback to the browser."""

    @pytest.mark.django_db
    def test_error_snapshot_does_not_contain_traceback(self, user):
        from django.utils import timezone

        op = DemoOp.objects.create(
            owner=user,
            started_on=timezone.now(),
            finished_on=timezone.now(),
            finished_successfully=False,
            traceback=(
                "Traceback (most recent call last):\n"
                "  File '/app/foo.py', line 42\n"
                "ValueError: boom"
            ),
        )
        html = op._render_snapshot_html()
        assert "Traceback (most recent call last)" not in html
        assert "/app/foo.py" not in html
        assert str(op.pk) in html

    @pytest.mark.django_db
    def test_error_snapshot_contains_op_pk(self, user):
        from django.utils import timezone

        op = DemoOp.objects.create(
            owner=user,
            started_on=timezone.now(),
            finished_on=timezone.now(),
            finished_successfully=False,
            traceback="ValueError: secret error details",
        )
        html = op._render_snapshot_html()
        assert str(op.pk) in html
        assert "secret error details" not in html
