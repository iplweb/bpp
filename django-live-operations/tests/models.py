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


class StagedOp(LiveOperation):
    """Multi-stage operation for Phase 4 stage tests."""

    stages = ["Alpha", "Beta", "Gamma"]

    class Meta:
        app_label = "tests"

    def run(self, p):
        with p.stage("Alpha"):
            p.log("alpha step")
        with p.stage("Beta"):
            p.log("beta step")
        with p.stage("Gamma"):
            p.result({"stage_result": "complete"})


class FailedStageOp(LiveOperation):
    """Stage that raises an exception — tests failed state transition."""

    stages = ["Setup", "Explode"]

    class Meta:
        app_label = "tests"

    def run(self, p):
        with p.stage("Setup"):
            p.log("setup ok")
        with p.stage("Explode"):
            raise RuntimeError("boom")


class NextOp(LiveOperation):
    """A successor operation used to test chain_to."""

    class Meta:
        app_label = "tests"

    def run(self, p):
        p.result({"next": "done"})


class ChainOpA(LiveOperation):
    """First link in a chain — chains to NextOp on completion."""

    class Meta:
        app_label = "tests"

    def run(self, p):
        p.log("chain A running")
        next_op = NextOp.objects.create(owner=self.owner)
        p.chain_to(next_op)
