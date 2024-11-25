from django.core.exceptions import DisallowedHost

from django_bpp.sentry_support import global_stacktrace_filter


def test_global_stacktrace_filter():

    assert (
        global_stacktrace_filter(1, {"exc_info": [DisallowedHost, None, None]}) is None
    )

    assert (
        global_stacktrace_filter(
            1,
            {
                "exc_info": [
                    RuntimeError,
                    RuntimeError("Response content shorter than Content-Length"),
                    None,
                ]
            },
        )
        is None
    )

    assert (
        global_stacktrace_filter(
            1, {"exc_info": [RuntimeError, RuntimeError("inny blad"), None]}
        )
        == 1
    )

    assert (
        global_stacktrace_filter(
            1, {"exc_info": [Exception, Exception("koparka"), None]}
        )
        == 1
    )
