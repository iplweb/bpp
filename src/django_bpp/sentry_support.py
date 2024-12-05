import logging

from django.core.exceptions import DisallowedHost


def global_stacktrace_filter(event, hint):
    if "exc_info" in hint:
        exc_info = hint["exc_info"]

        # Ignorujemy DissalowedHosts -- pojawia się przy wejściu na "cyfrowe" IP zazwyczaj
        # przez boty skanujące:
        if exc_info[0] == DisallowedHost:
            return

        # Response content shorter than Content-Length: namiętnie pojawia się przy serwowaniu
        # favicon. https://github.com/encode/starlette/issues/1764
        if (
            exc_info[0] == RuntimeError
            and str(exc_info[1]) == "Response content shorter than Content-Length"
        ):
            return

    return event


class RequireUSING_SENTRYSDKFalse(logging.Filter):
    def filter(self, record):
        from django.conf import settings

        return not getattr(settings, "USING_SENTRYSDK", False)
