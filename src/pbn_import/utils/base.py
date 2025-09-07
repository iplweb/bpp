"""Base class for import utilities"""

import logging
import time
import traceback
from typing import Any, Dict, Optional

from django.db import transaction
from sentry_sdk import capture_exception

from ..models import ImportLog, ImportSession

logger = logging.getLogger(__name__)


class CancelledException(Exception):
    """Raised when import is cancelled"""


class TqdmSessionProgress:
    """Custom TQDM wrapper that reports progress to ImportSession"""

    def __init__(self, session: ImportSession, subtask_name: str):
        self.session = session
        self.subtask_name = subtask_name
        self.last_update_time = 0
        self.update_interval = 0.5  # Update every 0.5 seconds max

    def update(self, current: int, total: int, desc: str = ""):
        """Update subtask progress in session"""
        current_time = time.time()
        # Throttle updates to avoid too many database writes
        if (
            current_time - self.last_update_time < self.update_interval
            and current < total
        ):
            return

        progress = int((current / total) * 100) if total > 0 else 0

        # Update session progress data
        if "current_subtask" not in self.session.progress_data:
            self.session.progress_data["current_subtask"] = {}

        self.session.progress_data["current_subtask"] = {
            "name": self.subtask_name,
            "description": desc,
            "current": current,
            "total": total,
            "percentage": progress,
        }

        # Save only the progress_data field to minimize DB load
        self.session.save(update_fields=["progress_data"])
        self.last_update_time = current_time

    def clear(self):
        """Clear subtask progress"""
        if "current_subtask" in self.session.progress_data:
            del self.session.progress_data["current_subtask"]
            self.session.save(update_fields=["progress_data"])


def pbar_with_callback(iterator, total, desc, callback=None, check_cancel_func=None):
    """Wrapper for pbar that includes callback support and cancellation checking"""
    from tqdm import tqdm

    with tqdm(iterator, total=total, desc=desc, unit="items") as pbar_obj:
        for i, item in enumerate(pbar_obj):
            # Check for cancellation periodically (every 10 items)
            if check_cancel_func and i % 10 == 0:
                if check_cancel_func():
                    raise CancelledException("Import został anulowany")

            if callback:
                callback.update(i + 1, total, desc)
            yield item

    # Clear subtask when done
    if callback:
        callback.clear()


class ImportStepBase:
    """Base class for import step implementations"""

    step_name: str = "Unknown Step"
    step_description: str = "Przetwarzanie..."

    def __init__(self, session: ImportSession, client=None):
        self.session = session
        self.client = client
        self.start_time = None
        self.processed_count = 0
        self.total_count = 0
        self.errors = []

    def log(self, level: str, message: str, details: Optional[Dict[Any, Any]] = None):
        """Create a log entry for this session"""
        ImportLog.objects.create(
            session=self.session,
            level=level,
            step=self.step_name,
            message=message,
            details=details or {},
        )

        # Also log to standard logger
        log_method = getattr(logger, level, logger.info)
        log_method(f"[{self.step_name}] {message}")

    def update_progress(self, current: int, total: int, message: str = ""):
        """Update session progress"""
        self.processed_count = current
        self.total_count = total

        if total > 0:
            progress_percent = int((current / total) * 100)
        else:
            progress_percent = 0

        self.session.update_progress(
            step_name=f"{self.step_name}: {message}" if message else self.step_name,
            progress_percent=progress_percent,
        )

        # Store detailed progress in session data
        if "steps" not in self.session.progress_data:
            self.session.progress_data["steps"] = {}

        self.session.progress_data["steps"][self.step_name] = {
            "processed": current,
            "total": total,
            "progress": progress_percent,
            "message": message,
            "errors": len(self.errors),
        }
        self.session.save()

    def start(self):
        """Called when step starts"""
        self.start_time = time.time()
        self.log("info", f"Rozpoczynanie: {self.step_description}")
        self.session.current_step = self.step_name
        self.session.save()

    def finish(self):
        """Called when step completes"""
        elapsed = time.time() - self.start_time if self.start_time else 0

        if self.errors:
            self.log(
                "warning",
                f"Zakończono z {len(self.errors)} błędami w {elapsed:.2f}s",
                {"errors": self.errors[:10]},
            )  # Log first 10 errors
        else:
            self.log("success", f"Zakończono pomyślnie w {elapsed:.2f}s")

        # Update statistics if available
        if hasattr(self.session, "statistics"):
            self._update_statistics()

    def _update_statistics(self):
        """Override in subclasses to update statistics"""

    def check_cancelled(self) -> bool:
        """Check if import has been cancelled"""
        self.session.refresh_from_db()
        if self.session.status == "cancelled":
            self.log("warning", "Import został anulowany przez użytkownika")
            return True
        return False

    def raise_if_cancelled(self):
        """Check cancellation and raise exception if cancelled"""
        if self.check_cancelled():
            raise CancelledException("Import został anulowany")

    def create_subtask_progress(self, subtask_name: str) -> TqdmSessionProgress:
        """Create a progress callback for subtasks"""
        return TqdmSessionProgress(self.session, subtask_name)

    def update_subtask_progress(self, current: int, total: int, desc: str = ""):
        """Update subtask progress directly"""
        callback = TqdmSessionProgress(self.session, self.step_name)
        callback.update(current, total, desc)

    def clear_subtask_progress(self):
        """Clear any subtask progress"""
        if "current_subtask" in self.session.progress_data:
            del self.session.progress_data["current_subtask"]
            self.session.save(update_fields=["progress_data"])

    def handle_error(self, error: Exception, context: str = ""):
        """Handle and log an error"""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.errors.append(error_msg)

        # Log full traceback to console and send to Sentry
        print(f"Błąd w {self.step_name}: {error_msg}")
        traceback.print_exc()
        capture_exception(error)

    def handle_pbn_error(self, error: Exception, context: str = ""):
        """Handle PBN-specific errors, raising on authorization issues"""
        error_str = str(error)
        if (
            "403" in error_str
            or "Forbidden" in error_str
            or "authorization" in error_str.lower()
        ):
            # This is an authorization error - should stop the import
            self.log("critical", f"{context}: Błąd autoryzacji PBN")
            raise
        else:
            # Non-critical error, just log it
            self.handle_error(error, context)

        self.log(
            "error",
            error_str,
            {
                "exception": str(type(error).__name__),
                "traceback": traceback.format_exc(),
            },
        )

    def is_authorization_error(self, error: Exception) -> bool:
        """Check if an error is related to PBN authorization"""
        error_msg = str(error)
        return (
            "autoryzację w PBN" in error_msg
            or "autoryzacji PBN" in error_msg
            or "autoryzacja" in error_msg.lower()
        )

    @transaction.atomic
    def run(self):
        """Execute the import step - override in subclasses"""
        raise NotImplementedError("Subclasses must implement run()")

    def __call__(self):
        """Make the class callable for easier use"""
        self.start()
        try:
            result = self.run()
            self.finish()
            return result
        except Exception as e:
            self.handle_error(e, f"Krytyczny błąd w {self.step_name}")
            # Additional console logging for critical failures
            print(f"Krytyczny błąd w {self.step_name}: {str(e)}")
            traceback.print_exc()
            capture_exception(e)
            self.session.mark_failed(str(e), traceback.format_exc())
            raise
