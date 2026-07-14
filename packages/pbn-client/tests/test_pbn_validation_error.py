from unittest.mock import Mock

import pytest
from fakes import MockTransport

from pbn_client.exceptions import (
    HttpException,
    PBNValidationError,
    parse_pbn_validation_details,
)


def test_parse_format1_values_dedup_preserve_order():
    j = {"details": {"a": "Wymagane!", "b": "Wymagane!", "c": "Inne!"}}
    assert parse_pbn_validation_details(j) == ["Wymagane!", "Inne!"]


def test_parse_format2_description_fallback():
    # Realny Format 2 (migracja 0006): element ma "code" i "description",
    # NIE ma "message" — czytelny tekst musi pochodzić z description.
    j = [
        {
            "requestPosition": 0,
            "code": "NOT_UNIQUE_PUBLICATION_ISBN_ISMN",
            "description": "Publikacja o identycznym ISBN już istnieje.",
        }
    ]
    assert parse_pbn_validation_details(j) == [
        "Publikacja o identycznym ISBN już istnieje."
    ]


def test_parse_format2_message_wins_over_description():
    j = [{"message": "M", "description": "D", "code": "C"}]
    assert parse_pbn_validation_details(j) == ["M"]


def test_parse_hostile_list_value_does_not_crash():
    # PBN potrafi zwrócić listę jako wartość details — naiwny dict.fromkeys
    # rzuciłby TypeError: unhashable type: 'list'.
    j = {"details": {"x": ["a", "b"]}}
    assert parse_pbn_validation_details(j) == ["a, b"]


def test_parse_hostile_dict_and_none_values():
    j = {"details": {"x": {"k": "v"}, "y": None}}
    # Nie wybucha; wartości skoercowane do str.
    result = parse_pbn_validation_details(j)
    assert result is not None
    assert len(result) == 2


def test_parse_format2_nondict_element_skipped():
    j = ["goły string", {"code": "C"}]
    assert parse_pbn_validation_details(j) == ["C"]


def test_parse_non_validation_returns_none():
    assert parse_pbn_validation_details({"message": "Forbidden"}) is None
    assert parse_pbn_validation_details({"details": {}}) is None
    assert parse_pbn_validation_details(None) is None
    assert parse_pbn_validation_details("jakis string") is None
    assert parse_pbn_validation_details([]) is None


def test_pbnvalidationerror_user_messages():
    e = PBNValidationError(
        400,
        "/api/v1/publications",
        '{"details": {"openAccess.releaseDate": "Data ... wymagana!"}}',
    )
    assert e.user_messages() == ["Data ... wymagana!"]


def test_pbnvalidationerror_str_is_tuple_not_overridden():
    # KRYTYCZNE: str() musi dawać tuplę (kolejka parsuje SentData.exception).
    e = PBNValidationError(400, "/api/v1/publications", '{"details": {"a": "b"}}')
    s = str(e)
    assert s.startswith("(")
    assert "/api/v1/publications" in s
    assert '"details"' in s  # surowy JSON body zachowany w tracebacku
    assert isinstance(e, HttpException)  # podklasa — wsteczna zgodność


class _FakeResponse:
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self.content = content.encode() if isinstance(content, str) else content
        self.headers = headers or {}


def _patch_reporter(monkeypatch):
    report = Mock()
    monkeypatch.setattr("pbn_client.transport.rollbar.report_message", report)
    return report


def test_transport_validation_400_raises_pbnvalidationerror_no_rollbar(monkeypatch):
    report = _patch_reporter(monkeypatch)
    t = MockTransport()
    ret = _FakeResponse(
        400,
        '{"code":400,"message":"Bad Request","description":"Validation failed.",'
        '"details":{"openAccess.releaseDate":"Data ... wymagana!"}}',
    )
    with pytest.raises(PBNValidationError) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert ei.value.user_messages() == ["Data ... wymagana!"]
    report.assert_not_called()


def test_transport_validation_409_format2_no_rollbar(monkeypatch):
    report = _patch_reporter(monkeypatch)
    t = MockTransport()
    ret = _FakeResponse(
        409,
        '[{"requestPosition":0,"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN",'
        '"description":"Publikacja o identycznym ISBN już istnieje."}]',
    )
    with pytest.raises(PBNValidationError) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert ei.value.user_messages() == ["Publikacja o identycznym ISBN już istnieje."]
    report.assert_not_called()


def test_transport_400_without_details_is_plain_httpexception(monkeypatch):
    report = _patch_reporter(monkeypatch)
    t = MockTransport()
    ret = _FakeResponse(400, '{"message":"Bad Request"}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()


def test_transport_500_with_details_shape_still_reports_rollbar(monkeypatch):
    report = _patch_reporter(monkeypatch)
    t = MockTransport()
    ret = _FakeResponse(500, '{"details":{"x":"y"}}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()


@pytest.mark.parametrize("status", [401, 403, 423])
def test_transport_auth_and_locked_not_validation(monkeypatch, status):
    report = _patch_reporter(monkeypatch)
    t = MockTransport()
    ret = _FakeResponse(status, '{"details":{"x":"y"}}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()
