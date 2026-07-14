from unittest.mock import Mock

import pytest

from pbn_client.auth import OAuthMixin
from pbn_client.conf.settings import DEFAULT_HTTP_TIMEOUT, parse_timeout
from pbn_client.transport import RequestsTransport


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, DEFAULT_HTTP_TIMEOUT),
        ("5", 5.0),
        (5, 5.0),
        ("2.5,30", (2.5, 30.0)),
        ([1, 9], (1.0, 9.0)),
        ("", DEFAULT_HTTP_TIMEOUT),
        ("1,2,3", DEFAULT_HTTP_TIMEOUT),
    ],
)
def test_parse_timeout(raw, expected):
    assert parse_timeout(raw) == expected


def test_transport_uses_explicit_timeout_for_get(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"ok": True}
    request = Mock(return_value=response)
    monkeypatch.setattr("pbn_client.transport.requests.get", request)

    transport = RequestsTransport("app", "token", "https://pbn.example", timeout=(2, 7))

    assert transport.get("/resource") == {"ok": True}
    assert request.call_args.kwargs["timeout"] == (2.0, 7.0)


def test_transport_uses_explicit_timeout_for_post(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"ok": True}
    request = Mock(return_value=response)
    monkeypatch.setattr("pbn_client.transport.requests.post", request)

    transport = RequestsTransport(
        "app",
        "token",
        "https://pbn.example",
        "user-token",
        timeout="3,11",
    )

    assert transport.post("/resource", body={}) == {"ok": True}
    assert request.call_args.kwargs["timeout"] == (3.0, 11.0)


def test_oauth_token_exchange_accepts_explicit_timeout(monkeypatch):
    response = Mock(content=b"")
    response.json.return_value = {"X-User-Token": "user-token"}
    request = Mock(return_value=response)
    monkeypatch.setattr("pbn_client.auth.requests.post", request)

    result = OAuthMixin.get_user_token(
        "https://pbn.example",
        "app",
        "token",
        "one-time-token",
        timeout=4,
    )

    assert result == "user-token"
    assert request.call_args.kwargs["timeout"] == 4.0
