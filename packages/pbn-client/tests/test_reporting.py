import sys

import pytest

from pbn_client import PBNClient, RequestsTransport
from pbn_client.exceptions import HttpException, StatementsResendFailedException
from pbn_client.reporting import (
    NullReporter,
    get_default_reporter,
    set_default_reporter,
)


class RecordingReporter:
    def __init__(self):
        self.messages = []
        self.exceptions = []

    def report_message(self, message, *, level=None, extra_data=None):
        self.messages.append((message, level, extra_data))

    def report_exc_info(self, exc_info=None, *, level=None, extra_data=None):
        self.exceptions.append((exc_info, level, extra_data))


class _FakeResponse:
    status_code = 500
    headers = {"Content-Type": "application/json"}
    content = b'{"message":"failure"}'


def test_transport_uses_injected_reporter():
    reporter = RecordingReporter()
    transport = RequestsTransport(
        "app", "token", "https://pbn.example", reporter=reporter
    )

    with pytest.raises(HttpException):
        transport._check_error_response(_FakeResponse(), "/resource")

    assert reporter.messages[0][0] == "PBN 500 on /resource"
    assert reporter.messages[0][1] == "error"


def test_existing_transport_follows_process_default():
    original = get_default_reporter()
    transport = RequestsTransport("app", "token", "https://pbn.example")
    reporter = RecordingReporter()
    try:
        set_default_reporter(reporter)
        with pytest.raises(HttpException):
            transport._check_error_response(_FakeResponse(), "/resource")
    finally:
        set_default_reporter(original)

    assert len(reporter.messages) == 1


def test_none_restores_noop_default():
    original = get_default_reporter()
    try:
        set_default_reporter(None)
        assert isinstance(get_default_reporter(), NullReporter)
    finally:
        set_default_reporter(original)


def test_statement_failure_uses_transport_reporter():
    reporter = RecordingReporter()
    transport = RequestsTransport(
        "app", "token", "https://pbn.example", reporter=reporter
    )
    client = PBNClient(transport)
    last_error = RuntimeError("PBN unavailable")

    with pytest.raises(StatementsResendFailedException):
        client._report_statements_failure_and_raise(123, "pbn-uid", last_error)

    exc_info, level, extra_data = reporter.exceptions[0]
    assert exc_info[0] is StatementsResendFailedException
    assert isinstance(exc_info[1], StatementsResendFailedException)
    assert exc_info[2] is not None
    assert level == "warning"
    assert extra_data["publication_pk"] == 123
    assert sys.exc_info() == (None, None, None)
