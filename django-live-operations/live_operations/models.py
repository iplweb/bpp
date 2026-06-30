"""
LiveOperation — abstract base model for long-running operations.

State machine (get_state):
  NOT_STARTED  → STARTED (started_on set)
               → FINISHED_OK (finished_on + finished_successfully=True)
               → FINISHED_ERROR (finished_on + finished_successfully=False)
               → CANCELLED (cancelled=True)

§19.3: only terminal state is persisted to DB in v1 (no PERSIST_PROGRESS).
status_text/percent/log/log_seq are placeholder fields; in v1 default they
are written only by p.result() / p.error() (via result_context), not during
live progress.
"""
from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models


class LiveOperation(models.Model):
    """Abstract base. Concrete subclasses must implement ``run(self, p)``."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )

    # Timestamps
    created_on = models.DateTimeField(auto_now_add=True)
    started_on = models.DateTimeField(null=True, blank=True)
    finished_on = models.DateTimeField(null=True, blank=True)

    # Terminal state (§19.3 source of truth)
    finished_successfully = models.BooleanField(default=False)
    cancel_requested = models.BooleanField(default=False)  # set by cancel view
    cancelled = models.BooleanField(default=False)
    traceback = models.TextField(null=True, blank=True)
    result_context = models.JSONField(null=True, blank=True)

    # Placeholder progress fields — v1: not written during live run
    status_text = models.CharField(max_length=255, blank=True, default="")
    percent = models.PositiveSmallIntegerField(default=0)
    log = models.JSONField(default=list)
    log_seq = models.PositiveIntegerField(default=0)

    # Stage support (§16)
    stages: list[str] = []  # class-level declaration, not a DB field
    current_stage = models.IntegerField(default=-1)
    stage_states = models.JSONField(default=dict)

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    # ------------------------------------------------------------------ #
    # Developer API                                                        #
    # ------------------------------------------------------------------ #

    def run(self, p) -> None:  # noqa: ANN001
        """Override in concrete subclasses to implement the operation logic."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.run() is not implemented"
        )

    # ------------------------------------------------------------------ #
    # State machine                                                        #
    # ------------------------------------------------------------------ #

    def get_state(self) -> str:
        """Return the current state as a string constant."""
        if self.cancelled:
            return "CANCELLED"
        if self.finished_on is not None:
            return "FINISHED_OK" if self.finished_successfully else "FINISHED_ERROR"
        if self.started_on is not None:
            return "STARTED"
        return "NOT_STARTED"

    # ------------------------------------------------------------------ #
    # Naming resolvers — delegate to live_operations.naming               #
    # ------------------------------------------------------------------ #

    def get_host_template_name(self) -> str:
        from live_operations import naming

        return naming.host_template_name(self.__class__)

    def get_result_template_name(self) -> str:
        from live_operations import naming

        return naming.result_template_name(self.__class__)

    def get_channel_name(self) -> str:
        from live_operations import naming

        return naming.channel_name(self)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def enqueue(self) -> None:
        """Dispatch this operation via the configured runner."""
        from live_operations import runner

        return runner.enqueue(self)

    # ------------------------------------------------------------------ #
    # Phase 2: subscription token + snapshot                              #
    # ------------------------------------------------------------------ #

    @property
    def subscription_token(self) -> str:
        """Signed token authorising self.owner to subscribe to this channel."""
        from live_operations.security import make_subscription_token

        return make_subscription_token(self.owner, self)

    def _render_snapshot_html(self) -> str:
        """Render the appropriate HTML fragment for the current state.

        §19.3: only terminal state is in DB; running ops get a generic
        status fragment.
        """
        from django.template.loader import render_to_string

        state = self.get_state()

        if state == "FINISHED_OK":
            render_ctx: dict = dict(self.result_context or {})
            render_ctx.setdefault("operation", self)
            try:
                inner = render_to_string(self.get_result_template_name(), render_ctx)
            except Exception:
                inner = ""
            return f'<div id="op-result" hx-swap-oob="true">{inner}</div>'

        if state == "FINISHED_ERROR":
            from django.utils.html import format_html

            return format_html(
                '<div id="op-result" hx-swap-oob="true">'
                '<div class="error">{}</div></div>',
                self.traceback or "",
            )

        if state == "CANCELLED":
            return (
                '<div id="op-result" hx-swap-oob="true">'
                '<div class="cancelled">Operation was cancelled.</div>'
                "</div>"
            )

        # STARTED or NOT_STARTED — send running status
        return render_to_string(
            "live_operations/_status.html",
            {"text": "Operation in progress…", "level": "info"},
        )

    def send_snapshot(self) -> None:
        """Push current state as an HTML fragment to this operation's channel group.

        Called by LiveOperationConsumer.connect() so a freshly connected
        client immediately sees the latest state (§7.3 / §19.3).

        Uses channels_broadcast.core._send (same async/sync helper as
        channels_broadcast itself) so the send works from both sync
        workers and async consumers.
        """
        from channels_broadcast.core import _send

        html = self._render_snapshot_html()
        channel = self.get_channel_name()
        _send(channel, {"liveop_html": html})
