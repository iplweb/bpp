"""Świadome ulepszenia unifikacji P4 (wykluczone z golden byte-identyczności).

1. ``format_pbn_error`` nie może już rzucać ``TypeError`` na payloadzie-liczbie
   (stary bug: ``"message" in 42``).
2. Admin ``exception_details`` przestaje używać hacka
   ``split('"details":')[1][:-3]`` — zwraca czytelny komunikat z ``ErrorRecord``.
"""

import pytest
from django.contrib import admin

from pbn_api.admin.sentdata import SentDataAdmin
from pbn_api.models import SentData
from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error


class _FakeSent:
    def __init__(self, exception, pk=1):
        self.exception = exception
        self.pk = pk


NUMBER_PAYLOAD = "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '42')"


@pytest.mark.django_db
def test_format_pbn_error_number_payload_does_not_raise():
    # Stary kod rzucał TypeError; nowy renderuje bezpieczny HTML.
    result = format_pbn_error(NUMBER_PAYLOAD)
    assert isinstance(str(result), str)
    assert "<script>" not in str(result)


@pytest.mark.django_db
def test_format_pbn_error_number_payload_shows_endpoint():
    result = str(format_pbn_error(NUMBER_PAYLOAD, "TECH"))
    assert "HttpException: HTTP 400" in result
    assert "/api/v1/publications" in result


def _admin():
    return SentDataAdmin(SentData, admin.site)


def test_admin_exception_details_returns_validation_message():
    obj = _FakeSent(
        '(400, \'/api/v1/publications\', \'{"details":{"isbn":"ISBN zajęty"}}\')'
    )
    assert _admin().exception_details(obj) == "ISBN zajęty"


def test_admin_exception_details_no_double_brace_bug_on_traceback():
    # Stary hack split('"details":')[1][:-3] dawał na tracebacku wiszące "}}".
    traceback = (
        "Traceback (most recent call last):\n"
        "pbn_api.exceptions.HttpException: (400, '/x', "
        '\'{"details":{"isbn":"ISBN zajęty"}}\')\n'
    )
    out = _admin().exception_details(_FakeSent(traceback))
    assert out == "ISBN zajęty"
    assert "}}" not in out


def test_admin_exception_details_prefixed_validation():
    obj = _FakeSent(
        "pbn_client.exceptions.PBNValidationError: "
        '(400, \'/x\', \'{"details":{"doi":"Duplicate"}}\')'
    )
    assert _admin().exception_details(obj) == "Duplicate"


def test_admin_exception_details_plaintext_passthrough():
    assert _admin().exception_details(_FakeSent("zwykły błąd")) == "zwykły błąd"


def test_admin_exception_details_empty_is_none():
    assert _admin().exception_details(_FakeSent("")) is None
    assert _admin().exception_details(_FakeSent(None)) is None
