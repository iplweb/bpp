"""
Runner — dispatch LiveOperation instances to execution backends.

RUNNER choices (conf.LIVE_OPERATIONS["RUNNER"]):
  "eager"     — run synchronously in the calling thread (test/degradation).
                group_send hits an empty group → only terminal snapshot visible.
  "threading" — background daemon thread (dev, no Redis required).
  "celery"    — Celery shared_task (production; requires celery extra).

task_run(operation, progress):
  1. Check cancel_requested before starting.
  2. Mark started_on.
  3. Call operation.run(progress).
  4. On OperationCancelled → set cancelled + finished_on.
  5. On other Exception → set traceback + error state.
  6. Auto-finalize if run() returned without calling p.result().
"""
from __future__ import annotations

import sys
import traceback as tb
from typing import Any, Optional


def enqueue(operation: Any, progress: Optional[Any] = None) -> None:
    """
    Dispatch *operation* according to the configured RUNNER.

    *progress* is auto-selected if not supplied:
    WebProgress when a channel layer is available, TextProgress otherwise.
    """
    from live_operations.conf import get_setting

    runner_name = get_setting("RUNNER") or "eager"

    if runner_name == "eager":
        p = progress or _make_progress(operation)
        task_run(operation, p)

    elif runner_name == "threading":
        import threading

        p = progress or _make_progress(operation)
        t = threading.Thread(target=task_run, args=(operation, p), daemon=True)
        t.start()

    elif runner_name == "celery":
        _celery_enqueue(operation)

    else:
        raise ValueError(f"Unknown LIVE_OPERATIONS RUNNER: {runner_name!r}")


def _make_progress(operation: Any) -> Any:
    """Auto-select WebProgress or TextProgress based on channel layer availability."""
    try:
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is not None:
            from live_operations.progress import WebProgress

            return WebProgress(operation, layer)
    except Exception:
        pass

    from live_operations.progress import TextProgress

    return TextProgress(operation, sys.stdout)


def _celery_enqueue(operation: Any) -> None:
    try:
        _celery_task.delay(  # type: ignore[name-defined]
            operation._meta.app_label,
            operation.__class__.__name__,
            str(operation.pk),
        )
    except Exception as exc:
        raise RuntimeError(
            "RUNNER='celery' but Celery is not available. "
            "Install django-live-operations[celery]."
        ) from exc


try:
    from celery import shared_task  # type: ignore[import-untyped]

    @shared_task
    def _celery_task(app_label: str, model_name: str, pk: str) -> None:
        from django.apps import apps

        model_cls = apps.get_model(app_label, model_name)
        operation = model_cls.objects.get(pk=pk)
        task_run(operation, _make_progress(operation))

except ImportError:
    pass  # celery extra not installed; "celery" runner raises at dispatch time


def task_run(operation: Any, progress: Any) -> None:
    """
    Core execution loop. Called by all runner backends.

    Checks cancel_requested before starting — if already set, marks cancelled
    without calling run(). Then calls run(), handling OperationCancelled and
    arbitrary exceptions. Auto-finalizes as success if p.result() was not called.
    """
    from django.utils import timezone

    # Pre-flight cancel check: skip run() if already cancelled.
    operation.refresh_from_db(fields=["cancel_requested"])
    if operation.cancel_requested:
        operation.started_on = timezone.now()
        operation.save(update_fields=["started_on"])
        _handle_cancelled(operation)
        return

    # Mark started
    operation.started_on = timezone.now()
    operation.save(update_fields=["started_on"])

    try:
        operation.run(progress)

        # Auto-finalize if p.result() / p.error() was not called inside run()
        if not progress._finalized:
            operation.finished_on = timezone.now()
            operation.finished_successfully = True
            operation.save(update_fields=["finished_on", "finished_successfully"])
            progress._finalized = True

    except _get_cancelled_class():
        _handle_cancelled(operation)

    except Exception:
        _handle_error(operation, tb.format_exc())


def _get_cancelled_class() -> type:
    from live_operations.progress import OperationCancelled

    return OperationCancelled


def _handle_cancelled(operation: Any) -> None:
    from django.utils import timezone

    operation.cancelled = True
    operation.finished_on = timezone.now()
    operation.finished_successfully = False
    operation.save(update_fields=["cancelled", "finished_on", "finished_successfully"])


def _handle_error(operation: Any, traceback_str: str) -> None:
    from django.utils import timezone

    operation.finished_on = timezone.now()
    operation.finished_successfully = False
    operation.traceback = traceback_str
    operation.save(
        update_fields=["finished_on", "finished_successfully", "traceback"]
    )
