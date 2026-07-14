"""BPP error-reporting adapter for the standalone PBN client."""

import rollbar


class RollbarReporter:
    """Forward scrubbed PBN diagnostics to BPP's configured Rollbar client."""

    def report_message(self, message, *, level=None, extra_data=None):
        return rollbar.report_message(
            message,
            level=level,
            extra_data=extra_data,
        )

    def report_exc_info(self, exc_info=None, *, level=None, extra_data=None):
        return rollbar.report_exc_info(
            exc_info,
            level=level,
            extra_data=extra_data,
        )


rollbar_reporter = RollbarReporter()
