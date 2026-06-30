"""
Concrete LiveOperation subclasses used only in the test suite.
"""
from live_operations.models import LiveOperation


class DemoOp(LiveOperation):
    """Minimal concrete operation for the test suite."""

    class Meta:
        app_label = "tests"

    def run(self, p):
        p.status("Running DemoOp")
        p.percent(50)
        p.log("step 1")
        p.result({"message": "done"})


class ErrorOp(LiveOperation):
    """Always raises an exception — used to test error handling in runner."""

    class Meta:
        app_label = "tests"

    def run(self, p):
        raise ValueError("intentional error")
