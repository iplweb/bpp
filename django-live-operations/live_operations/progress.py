"""
Progress API for LiveOperation.

Progress (abstract core):
    status, percent, track, log, stage, result, error,
    check_cancelled, chain_to, swap (web-only), html (web-only)

WebProgress: emits via async_to_sync(channel_layer.group_send) in JSON
    envelope {"type":"chat_message","liveop_html":"<html>"}.
    swap/html implemented here.

TextProgress: renders to a stream (stdout). tqdm if available, else print.
    swap/html raise NotImplementedError (web-only, §19.5).
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Any, Generator, Optional


class OperationCancelled(Exception):
    """Raised by check_cancelled() when the operation was cancelled."""


class Progress:
    """
    Transport-neutral Progress API. Subclasses implement the send hooks.

    Throttling: percent() is throttled by THROTTLE_HZ (default 10/s).
    First call per value-change (delta ≥ 1) always goes through; same-value
    rapid calls are coalesced by time gate.
    """

    def __init__(self, operation: Any) -> None:
        self._operation = operation
        self._last_percent_send_time: float = 0.0
        self._last_percent_value: int = -1
        self._finalized: bool = False

    # ------------------------------------------------------------------ #
    # Core API                                                             #
    # ------------------------------------------------------------------ #

    def status(self, text: str, level: str = "info") -> None:
        raise NotImplementedError

    def percent(self, value: int) -> None:
        """Throttled percent update. Delegates to _emit_percent after gate."""
        from live_operations.conf import get_setting

        throttle_hz = get_setting("THROTTLE_HZ") or 10
        min_interval = 1.0 / throttle_hz
        now = time.monotonic()
        delta = abs(value - self._last_percent_value)
        if now - self._last_percent_send_time >= min_interval or delta >= 1:
            self._last_percent_send_time = now
            self._last_percent_value = value
            self._emit_percent(value)

    def _emit_percent(self, value: int) -> None:
        raise NotImplementedError

    def track(
        self,
        iterable: Any,
        total: Optional[int] = None,
        label: Optional[str] = None,
        unit: str = "szt.",
    ) -> Generator:
        """
        Generator that yields items and updates percent (throttled).
        Calls check_cancelled() before each item.
        """
        if total is None:
            items = list(iterable)
            total = len(items)
            iterable = items
        n = 0
        for item in iterable:
            self.check_cancelled()
            yield item
            n += 1
            pct = int(n * 100 / total) if total > 0 else 100
            self.percent(pct)

    def log(self, line: str) -> None:
        raise NotImplementedError

    @contextmanager
    def stage(self, name: str) -> Generator:
        """
        Context manager for a named stage.
        Updates current_stage and stage_states on the operation object.
        """
        op = self._operation
        stages = list(op.stages) if op.stages else []
        idx = stages.index(name) if name in stages else -1

        if idx >= 0:
            op.current_stage = idx
            if not isinstance(op.stage_states, dict):
                op.stage_states = {}
            op.stage_states[str(idx)] = "active"

        self._on_stage_start(name, idx)
        try:
            yield
            if idx >= 0:
                op.stage_states[str(idx)] = "done"
            self._on_stage_end(name, idx, success=True)
        except OperationCancelled:
            if idx >= 0:
                op.stage_states[str(idx)] = "cancelled"
            self._on_stage_end(name, idx, success=False)
            raise
        except Exception:
            if idx >= 0:
                op.stage_states[str(idx)] = "error"
            self._on_stage_end(name, idx, success=False)
            raise

    def _on_stage_start(self, name: str, idx: int) -> None:
        """Hook called on stage entry. Override in subclasses."""

    def _on_stage_end(self, name: str, idx: int, success: bool) -> None:
        """Hook called on stage exit. Override in subclasses."""

    def result(self, context: Optional[dict] = None, **extra: Any) -> None:
        raise NotImplementedError

    def error(self, message: str) -> None:
        raise NotImplementedError

    def check_cancelled(self) -> None:
        """Re-read cancel_requested from DB; raise OperationCancelled if set."""
        self._operation.refresh_from_db(fields=["cancel_requested"])
        if self._operation.cancel_requested:
            raise OperationCancelled(
                f"Operation {self._operation.pk} was cancelled"
            )

    def chain_to(self, next_op: Any) -> None:
        """Chain to next_op. Web: re-init socket. Text: run inline. (Phase 4)"""
        raise NotImplementedError("chain_to not implemented in v1 (Phase 4)")

    # ------------------------------------------------------------------ #
    # Web-only (NotImplementedError on base + TextProgress)               #
    # ------------------------------------------------------------------ #

    def swap(self, selector: str, name: Optional[str] = None, **ctx: Any) -> None:
        raise NotImplementedError(
            "swap/html są webowe; użyj log/status/result"
        )

    def html(self, selector: str, raw: str, mode: str = "innerHTML") -> None:
        raise NotImplementedError(
            "swap/html są webowe; użyj log/status/result"
        )


# --------------------------------------------------------------------------- #
# WebProgress                                                                  #
# --------------------------------------------------------------------------- #


class WebProgress(Progress):
    """
    Sends HTML fragments in JSON envelope via Channels group_send.

    Envelope (§19.2): {"type": "chat_message", "liveop_html": "<html>"}
    No top-level "id" key — that would be auto-ACKed as a Notification.
    """

    def __init__(self, operation: Any, channel_layer: Any) -> None:
        super().__init__(operation)
        self._channel_layer = channel_layer
        self._channel = operation.get_channel_name()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _push(self, html: str) -> None:
        """Send HTML fragment wrapped in JSON envelope to the operation group."""
        from asgiref.sync import async_to_sync

        async_to_sync(self._channel_layer.group_send)(
            self._channel,
            {"type": "chat_message", "liveop_html": html},
        )

    def _render(self, template_name: str, context: dict) -> str:
        from django.template.loader import render_to_string

        return render_to_string(template_name, context)

    # ------------------------------------------------------------------ #
    # Core API                                                             #
    # ------------------------------------------------------------------ #

    def status(self, text: str, level: str = "info") -> None:
        html = self._render(
            "live_operations/_status.html",
            {"text": text, "level": level},
        )
        self._push(html)

    def _emit_percent(self, value: int) -> None:
        html = self._render(
            "live_operations/_progress.html",
            {"percent": value},
        )
        self._push(html)

    def log(self, line: str) -> None:
        html = self._render(
            "live_operations/_log_line.html",
            {"line": line},
        )
        self._push(html)

    def result(self, context: Optional[dict] = None, **extra: Any) -> None:
        """
        §19.4: commit terminal state BEFORE pushing result fragment.
        save() runs immediately (commits in autocommit); push is deferred via
        transaction.on_commit so any consumer connecting after the push sees
        committed data even when called inside a transaction.atomic() block.
        """
        from django.db import transaction
        from django.utils import timezone

        # storage_ctx: JSON-serialisable subset stored in result_context.
        # render_ctx: adds "operation" (model instance) for template use only.
        storage_ctx: dict = {} if context is None else dict(context)
        storage_ctx.update(extra)
        render_ctx = dict(storage_ctx)
        render_ctx.setdefault("operation", self._operation)

        op = self._operation
        op.finished_on = timezone.now()
        op.finished_successfully = True
        op.result_context = storage_ctx
        op.save(
            update_fields=["finished_on", "finished_successfully", "result_context"]
        )
        self._finalized = True

        # Capture names for the closure (op may be mutated later)
        result_template = op.get_result_template_name()
        push_fn = self._push

        def _push_result() -> None:
            try:
                from django.template.loader import render_to_string

                inner = render_to_string(result_template, render_ctx)
            except Exception:
                inner = ""
            push_fn(f'<div id="op-result" hx-swap-oob="true">{inner}</div>')

        transaction.on_commit(_push_result)

    def error(self, message: str) -> None:
        """Commit error terminal state, then push error fragment via on_commit."""
        from django.db import transaction
        from django.utils import timezone

        op = self._operation
        op.finished_on = timezone.now()
        op.finished_successfully = False
        op.traceback = message
        op.save(update_fields=["finished_on", "finished_successfully", "traceback"])
        self._finalized = True

        push_fn = self._push

        def _push_error() -> None:
            # SECURITY: ``message`` may carry untrusted content (exception
            # text echoing user input, file names, parsed data). Escape it via
            # format_html so it can never inject markup/JS into the page (XSS).
            from django.utils.html import format_html

            push_fn(
                format_html(
                    '<div id="op-result" hx-swap-oob="true">'
                    '<div class="error">{}</div></div>',
                    message,
                )
            )

        transaction.on_commit(_push_error)

    # ------------------------------------------------------------------ #
    # Web-only                                                             #
    # ------------------------------------------------------------------ #

    def swap(
        self, selector: str, name: Optional[str] = None, **ctx: Any
    ) -> None:
        """
        Render a fragment and push it OOB to *selector*.

        Pass ``html_raw=`` in ctx to use raw HTML directly.
        Otherwise derive template name from the *name* kwarg.
        """
        raw = ctx.pop("html_raw", None)
        if raw is not None:
            inner = raw
        elif name is not None:
            from live_operations.naming import class_to_snake

            op = self._operation
            app = op._meta.app_label
            snake = class_to_snake(op.__class__.__name__)
            template = f"{app}/{snake}_{name}.html"
            ctx.setdefault("operation", op)
            inner = self._render(template, ctx)
        else:
            inner = ""

        elem_id = selector.lstrip("#")
        self._push(f'<div id="{elem_id}" hx-swap-oob="true">{inner}</div>')

    def html(self, selector: str, raw: str, mode: str = "innerHTML") -> None:
        """Push raw HTML to *selector* OOB.

        SECURITY: this is a trusted-HTML escape hatch (like ``mark_safe``).
        ``raw`` is sent verbatim and NOT escaped — never pass untrusted /
        user-derived content here. For data-bearing regions use ``status``,
        ``log``, ``result`` or ``swap(name=...)`` (template-rendered, escaped).
        """
        elem_id = selector.lstrip("#")
        if mode == "beforeend":
            self._push(f'<div hx-swap-oob="beforeend:#{elem_id}">{raw}</div>')
        else:
            self._push(f'<div id="{elem_id}" hx-swap-oob="true">{raw}</div>')

    def _on_stage_start(self, name: str, idx: int) -> None:
        pass  # Phase 4: push stepper fragment

    def _on_stage_end(self, name: str, idx: int, success: bool) -> None:
        pass  # Phase 4: update stepper


# --------------------------------------------------------------------------- #
# TextProgress                                                                 #
# --------------------------------------------------------------------------- #


class TextProgress(Progress):
    """
    Renders progress to a text stream (stdout).
    tqdm used if available, else plain print fallback.
    swap/html raise NotImplementedError (web-only, §19.5).
    """

    def __init__(self, operation: Any, stream: Any = None) -> None:
        super().__init__(operation)
        self._stream = stream if stream is not None else sys.stdout
        try:
            import tqdm as _tqdm_mod

            self._tqdm = _tqdm_mod
        except ImportError:
            self._tqdm = None

    # ------------------------------------------------------------------ #
    # Core API                                                             #
    # ------------------------------------------------------------------ #

    def status(self, text: str, level: str = "info") -> None:
        if self._tqdm:
            self._tqdm.tqdm.write(text, file=self._stream)
        else:
            print(text, file=self._stream)

    def _emit_percent(self, value: int) -> None:
        if not self._tqdm:
            print(f"{value}%", file=self._stream)

    def track(
        self,
        iterable: Any,
        total: Optional[int] = None,
        label: Optional[str] = None,
        unit: str = "szt.",
    ) -> Generator:
        """Use tqdm natively if available; else plain print at intervals."""
        if total is None:
            items = list(iterable)
            total = len(items)
            iterable = items

        if self._tqdm:
            bar = self._tqdm.tqdm(
                iterable,
                total=total,
                desc=label,
                unit=unit,
                file=self._stream,
            )
            for item in bar:
                self.check_cancelled()
                yield item
        else:
            n = 0
            for item in iterable:
                self.check_cancelled()
                yield item
                n += 1
                pct = int(n * 100 / total) if total > 0 else 100
                if n == 1 or n == total or pct % 10 == 0:
                    print(f"{pct}% ({n}/{total})", file=self._stream)

    def log(self, line: str) -> None:
        if self._tqdm:
            self._tqdm.tqdm.write(line, file=self._stream)
        else:
            print(line, file=self._stream)

    def result(self, context: Optional[dict] = None, **extra: Any) -> None:
        """Save terminal state and render key=value dump (or *_result.txt)."""
        from django.utils import timezone

        ctx: dict = {} if context is None else dict(context)
        ctx.update(extra)

        op = self._operation
        op.finished_on = timezone.now()
        op.finished_successfully = True
        op.result_context = ctx
        op.save(
            update_fields=["finished_on", "finished_successfully", "result_context"]
        )
        self._finalized = True

        # Try *_result.txt template first
        from live_operations.naming import class_to_snake

        app = op._meta.app_label
        snake = class_to_snake(op.__class__.__name__)
        txt_template = f"{app}/{snake}_result.txt"
        try:
            from django.template.loader import render_to_string

            output = render_to_string(txt_template, ctx)
            print(output, file=self._stream)
            return
        except Exception:
            pass

        # Fallback: key=value dump (skip "operation" key — not human-readable)
        for key, value in ctx.items():
            if key == "operation":
                continue
            print(f"{key}={value}", file=self._stream)

    def error(self, message: str) -> None:
        from django.utils import timezone

        op = self._operation
        op.finished_on = timezone.now()
        op.finished_successfully = False
        op.traceback = message
        op.save(update_fields=["finished_on", "finished_successfully", "traceback"])
        self._finalized = True
        print(f"ERROR: {message}", file=self._stream)

    def _on_stage_start(self, name: str, idx: int) -> None:
        print(f"\n=== {name} ===", file=self._stream)

    def _on_stage_end(self, name: str, idx: int, success: bool) -> None:
        pass

    def chain_to(self, next_op: Any) -> None:
        """In text mode, run the next operation inline with the same stream."""
        p = TextProgress(next_op, self._stream)
        next_op.run(p)
