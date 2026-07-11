"""PBN nie wynosi surowego body ani sekretnych nagłówków do Rollbara (#5).

Body błędu z PBN może zawierać dane osobowe (PESEL, dane publikacji), a
nagłówki odpowiedzi — identyfikatory i cookies. To świadomy kanał
diagnostyczny, ale zbyt szeroki: lokalny log może zostać, ale do zewnętrznego
Rollbara nie wysyłamy surowego body, a nagłówki redagujemy u źródła.
"""

import pytest

from pbn_client.exceptions import HttpException
from pbn_client.transport import RequestsTransport


class _FakeResp:
    def __init__(self, status_code, headers, content):
        self.status_code = status_code
        self.headers = headers
        self.content = content


def test_rollbar_nie_wysyla_surowego_body_ani_sekretnych_naglowkow(monkeypatch):
    captured = {}

    def fake_report(msg, level=None, extra_data=None):
        captured["extra_data"] = extra_data

    monkeypatch.setattr("pbn_client.transport.rollbar.report_message", fake_report)

    t = RequestsTransport("app", "apptok", "https://pbn.example", "usertok")
    resp = _FakeResp(
        500,
        {
            "Authorization": "Bearer SEKRET",
            "Set-Cookie": "sid=poufne",
            "X-User-Token": "USERTOK",
            "Content-Type": "application/json",
        },
        b'{"pesel": "44051401359"}',
    )

    with pytest.raises(HttpException):
        t._check_error_response(resp, "/x")

    extra = captured["extra_data"]
    # Surowe body NIE wychodzi do Rollbara (może zawierać PESEL/dane osobowe).
    assert "body" not in extra
    # Sekretne nagłówki zredagowane u źródła.
    assert "SEKRET" not in str(extra["headers"].get("Authorization"))
    assert "poufne" not in str(extra["headers"].get("Set-Cookie"))
    assert "USERTOK" not in str(extra["headers"].get("X-User-Token"))
    # Nagłówek benign zachowany — diagnostyka nie ginie.
    assert extra["headers"]["Content-Type"] == "application/json"
    # Metadane diagnostyczne (bez treści) zostają.
    assert extra["status_code"] == 500
    assert extra["body_len"] == len(resp.content)
