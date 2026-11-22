"""BPP error-reporting adapter for the standalone PBN client.

Przekazuje diagnostykę klienta PBN do :mod:`bpp.zglaszanie_bledow`, czyli do
każdego skonfigurowanego backendu (Rollbar i/lub Sentry/GlitchTip).
"""

from bpp.zglaszanie_bledow import capture_exception, capture_message


class ZglaszanieBledowReporter:
    """Implementacja ``pbn_client.reporting.ErrorReporter`` dla BPP."""

    def report_message(self, message, *, level=None, extra_data=None):
        # `rollbar.report_message` bez poziomu zgłaszał "error" — zachowujemy to.
        return capture_message(
            message,
            level=level if level is not None else "error",
            extra=extra_data,
        )

    def report_exc_info(self, exc_info=None, *, level=None, extra_data=None):
        return capture_exception(
            exc_info,
            level=level,
            extra=extra_data,
        )


bpp_reporter = ZglaszanieBledowReporter()
