from pbn_client.reporting import default_reporter

from pbn_api.client import BppPBNClient
from pbn_api.reporting import ZglaszanieBledowReporter, bpp_reporter


def test_bpp_reporter_forwards_message(mocker):
    report = mocker.patch("pbn_api.reporting.capture_message")
    reporter = ZglaszanieBledowReporter()
    extra_data = {"status_code": 500}

    reporter.report_message("PBN 500", level="error", extra_data=extra_data)

    report.assert_called_once_with(
        "PBN 500",
        level="error",
        extra=extra_data,
    )


def test_bpp_reporter_message_bez_poziomu_to_error(mocker):
    """``rollbar.report_message`` bez poziomu zgłaszał "error" — tak zostaje."""
    report = mocker.patch("pbn_api.reporting.capture_message")

    ZglaszanieBledowReporter().report_message("PBN 500")

    report.assert_called_once_with("PBN 500", level="error", extra=None)


def test_bpp_reporter_forwards_exception(mocker):
    report = mocker.patch("pbn_api.reporting.capture_exception")
    reporter = ZglaszanieBledowReporter()
    exc_info = (RuntimeError, RuntimeError("PBN failed"), None)
    extra_data = {"pbn_uid": "abc"}

    reporter.report_exc_info(
        exc_info,
        level="warning",
        extra_data=extra_data,
    )

    report.assert_called_once_with(
        exc_info,
        level="warning",
        extra=extra_data,
    )


def test_bpp_client_applies_rollbar_policy_to_transport_without_reporter():
    class Transport:
        pass

    transport = Transport()

    BppPBNClient(transport, uczelnia=None)

    assert transport.reporter is bpp_reporter


def test_bpp_client_replaces_standalone_default_but_preserves_custom_reporter():
    class Transport:
        reporter = default_reporter

    transport = Transport()
    BppPBNClient(transport, uczelnia=None)
    assert transport.reporter is bpp_reporter

    custom_reporter = object()
    transport = Transport()
    transport.reporter = custom_reporter
    BppPBNClient(transport, uczelnia=None)
    assert transport.reporter is custom_reporter
