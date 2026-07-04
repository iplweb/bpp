"""Tests for ImportStepBase / TqdmSessionProgress progress_data writes."""

import pytest
from model_bakery import baker

from pbn_import.models import ImportSession
from pbn_import.utils.base import ImportStepBase, TqdmSessionProgress


class _Step(ImportStepBase):
    step_name = "author_import"
    step_description = "Test step"


@pytest.mark.django_db
def test_progress_data_writes_do_not_clobber(django_user_model):
    """Two independent stale writers on the same ImportSession row must not
    clobber each other's progress_data keys.

    Writer A drives ImportStepBase.update_progress (writes
    progress_data["steps"]). Writer B is a *separately fetched*, stale
    in-memory copy driving TqdmSessionProgress.update (writes
    progress_data["current_subtask"]). After both persist, BOTH keys must
    survive a fresh reload from the database.
    """
    user = baker.make(django_user_model)
    row = baker.make(ImportSession, user=user, progress_data={})

    # Two independent in-memory copies of the SAME row (stale w.r.t.
    # each other) — simulates the step thread vs the throttled tqdm
    # callback both holding their own ImportSession instance.
    session_a = ImportSession.objects.get(pk=row.pk)
    session_b = ImportSession.objects.get(pk=row.pk)

    # Writer A: real ImportStepBase code path → progress_data["steps"].
    step = _Step(session_a)
    step.update_progress(current=5, total=10, message="processing")

    # Writer B: real TqdmSessionProgress code path → current_subtask.
    # session_b never saw A's "steps" write (stale in-memory copy).
    callback = TqdmSessionProgress(session_b, subtask_name="sub")
    callback.last_update_time = 0  # ensure not throttled
    callback.update(current=3, total=6, desc="subtask")

    # Reload fresh from DB; both keys must be present.
    reloaded = ImportSession.objects.get(pk=row.pk)
    assert "steps" in reloaded.progress_data, reloaded.progress_data
    assert "author_import" in reloaded.progress_data["steps"]
    assert "current_subtask" in reloaded.progress_data, reloaded.progress_data
    assert reloaded.progress_data["current_subtask"]["name"] == "sub"
