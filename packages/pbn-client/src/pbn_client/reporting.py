"""Optional error-reporting hooks for :mod:`pbn_client`.

The client reports enough metadata to diagnose failed PBN calls, but it does
not choose or configure an external monitoring service. Applications can pass
an :class:`ErrorReporter` to a transport or set a process-wide default.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Protocol


class ErrorReporter(Protocol):
    """Minimal interface used by transports and statement synchronization."""

    def report_message(
        self,
        message: str,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Any:
        """Report a diagnostic message."""

    def report_exc_info(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Any:
        """Report an exception represented by ``sys.exc_info()``."""


class NullReporter:
    """Reporter used by default when an application provides no integration."""

    def report_message(
        self,
        message: str,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        return None

    def report_exc_info(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        return None


class LoggingReporter:
    """Reporter that emits diagnostics through the standard logging module."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("pbn_client")

    def report_message(
        self,
        message: str,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        log = getattr(self.logger, level or "error", self.logger.error)
        log("%s extra_data=%r", message, extra_data)

    def report_exc_info(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        log = getattr(self.logger, level or "error", self.logger.error)
        log("PBN client failure extra_data=%r", extra_data, exc_info=exc_info)


_default_reporter: ErrorReporter = NullReporter()


def get_default_reporter() -> ErrorReporter:
    """Return the reporter inherited by newly created transports."""

    return _default_reporter


def set_default_reporter(reporter: ErrorReporter | None) -> None:
    """Set the process-wide reporter; ``None`` restores the no-op default."""

    global _default_reporter
    _default_reporter = reporter if reporter is not None else NullReporter()


class _DefaultReporterProxy:
    """Resolve the default lazily so already-created transports see updates."""

    def report_message(
        self,
        message: str,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Any:
        return get_default_reporter().report_message(
            message, level=level, extra_data=extra_data
        )

    def report_exc_info(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
        *,
        level: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Any:
        return get_default_reporter().report_exc_info(
            exc_info, level=level, extra_data=extra_data
        )


default_reporter: ErrorReporter = _DefaultReporterProxy()
