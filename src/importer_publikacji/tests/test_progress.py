from unittest.mock import MagicMock

import pytest

from importer_publikacji.progress import (
    CREATE_STAGES,
    FETCH_STAGES,
    report_progress,
)


def test_fetch_stages_weights_sum_to_100():
    total = sum(weight for _, _, weight in FETCH_STAGES)
    assert total == 100


def test_create_stages_weights_sum_to_100():
    total = sum(weight for _, _, weight in CREATE_STAGES)
    assert total == 100


def test_report_progress_first_stage_no_counter():
    task = MagicMock()
    report_progress(task, "provider_fetch", stages=FETCH_STAGES)

    task.update_state.assert_called_once()
    args, kwargs = task.update_state.call_args
    assert kwargs["state"] == "PROGRESS"
    meta = kwargs["meta"]
    assert meta["stage_code"] == "provider_fetch"
    assert meta["label"] == "Pobieram dane z dostawcy..."
    assert meta["current"] == 0
    assert meta["total"] == 0
    assert meta["progress"] == 0


def test_report_progress_middle_stage_with_counter():
    task = MagicMock()
    report_progress(
        task,
        "match_authors",
        sub_current=25,
        sub_total=50,
        stages=FETCH_STAGES,
    )

    meta = task.update_state.call_args.kwargs["meta"]
    assert meta["stage_code"] == "match_authors"
    assert meta["current"] == 25
    assert meta["total"] == 50
    assert meta["progress"] == 50


def test_report_progress_last_stage_at_end():
    task = MagicMock()
    report_progress(task, "prefill_zgl", stages=FETCH_STAGES)

    meta = task.update_state.call_args.kwargs["meta"]
    assert meta["progress"] == 80


def test_report_progress_unknown_stage_raises():
    task = MagicMock()
    with pytest.raises(ValueError, match="Unknown stage"):
        report_progress(task, "nonexistent_stage", stages=FETCH_STAGES)


def test_report_progress_label_contains_counter_when_total_gt_1():
    task = MagicMock()
    report_progress(
        task,
        "match_authors",
        sub_current=12,
        sub_total=50,
        stages=FETCH_STAGES,
    )
    meta = task.update_state.call_args.kwargs["meta"]
    assert "12/50" in meta["label"] or meta["counter_display"] == "12/50"
