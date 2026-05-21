from unittest.mock import MagicMock

import pytest
import requests

from importer_publikacji.progress import (
    CREATE_STAGES,
    FETCH_STAGES,
    ProviderReturnedNothing,
    report_progress,
    user_safe_message,
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


def test_user_safe_message_for_provider_returned_nothing():
    msg = user_safe_message(ProviderReturnedNothing(), task_kind="fetch")
    assert "dostawcy" in msg.lower()
    assert "spróbuj" in msg.lower()


def test_user_safe_message_for_http_error():
    exc = requests.exceptions.HTTPError("500 server error")
    msg = user_safe_message(exc, task_kind="fetch")
    assert "nie odpowiada" in msg.lower() or "spróbuj" in msg.lower()


def test_user_safe_message_for_timeout():
    exc = requests.exceptions.Timeout("read timeout")
    msg = user_safe_message(exc, task_kind="fetch")
    assert "spróbuj" in msg.lower() or "czas" in msg.lower()


def test_user_safe_message_for_validation_error_uses_messages():
    from django.core.exceptions import ValidationError

    exc = ValidationError(["Pierwszy", "Drugi"])
    msg = user_safe_message(exc, task_kind="create")
    assert "Pierwszy" in msg
    assert "Drugi" in msg


def test_user_safe_message_unknown_fallback_for_fetch():
    msg = user_safe_message(RuntimeError("internal"), task_kind="fetch")
    assert "pobierania" in msg.lower() or "fetch" in msg.lower()
    assert "administrator" in msg.lower()


def test_user_safe_message_unknown_fallback_for_create():
    msg = user_safe_message(RuntimeError("internal"), task_kind="create")
    assert "tworzenia" in msg.lower() or "create" in msg.lower()
    assert "administrator" in msg.lower()
