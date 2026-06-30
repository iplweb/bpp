"""
Tests for the run_liveop management command.

Run a multi-stage operation synchronously via TextProgress — no Redis/ASGI.
"""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from tests.models import StagedOp

User = get_user_model()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin_liveop", password="x")


@pytest.mark.django_db
def test_run_liveop_staged_op_completes(superuser, settings):
    """run_liveop runs StagedOp to completion: prints stage headers + result."""
    settings.LIVE_OPERATIONS = {"RUNNER": "eager"}

    out = io.StringIO()
    call_command("run_liveop", "tests.StagedOp", stdout=out)

    output = out.getvalue()
    # Stage headers are printed by TextProgress._on_stage_start
    assert "Alpha" in output
    assert "Beta" in output
    assert "Gamma" in output
    # Result should be present (key=value dump)
    assert "stage_result=complete" in output
    # Final status line
    assert "FINISHED_OK" in output


@pytest.mark.django_db
def test_run_liveop_creates_superuser_when_none_exists(db, settings):
    """If no superuser exists, run_liveop creates admin/admin automatically."""
    settings.LIVE_OPERATIONS = {"RUNNER": "eager"}

    # Ensure no superuser present
    User.objects.filter(is_superuser=True).delete()

    out = io.StringIO()
    call_command("run_liveop", "tests.StagedOp", stdout=out)

    output = out.getvalue()
    # Warning about auto-created user
    assert "admin" in output.lower()
    assert "FINISHED_OK" in output


@pytest.mark.django_db
def test_run_liveop_uses_owner_flag(superuser, db, settings):
    """--owner resolves to specified username."""
    settings.LIVE_OPERATIONS = {"RUNNER": "eager"}

    out = io.StringIO()
    call_command("run_liveop", "tests.StagedOp", owner=superuser.username, stdout=out)

    output = out.getvalue()
    assert superuser.username in output
    assert "FINISHED_OK" in output


@pytest.mark.django_db
def test_run_liveop_persists_result(superuser, settings):
    """After run_liveop, the op's result_context is saved to DB."""
    settings.LIVE_OPERATIONS = {"RUNNER": "eager"}

    out = io.StringIO()
    call_command("run_liveop", "tests.StagedOp", stdout=out)

    op = StagedOp.objects.filter(owner=superuser).last()
    assert op is not None
    assert op.finished_successfully is True
    assert op.result_context == {"stage_result": "complete"}
