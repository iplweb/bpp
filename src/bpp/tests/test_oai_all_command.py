"""Testy naprawionej komendy ``oai_all`` (#9 security review)."""

from io import StringIO
from unittest.mock import Mock

import pytest
import requests
from django.core.management import CommandError, call_command

_NS = 'xmlns="http://www.openarchives.org/OAI/2.0/"'


def _page(records_ids, token=""):
    records = "".join(
        f"<record><header><identifier>oai:{i}</identifier></header></record>"
        for i in records_ids
    )
    return (
        f'<?xml version="1.0"?>'
        f"<OAI-PMH {_NS}>"
        f'<responseDate>2026-01-01T00:00:00Z</responseDate>'
        f'<request verb="ListRecords">http://x</request>'
        f"<ListRecords>{records}"
        f"<resumptionToken>{token}</resumptionToken>"
        f"</ListRecords></OAI-PMH>"
    ).encode()


def _mock_response(content):
    res = Mock()
    res.content = content
    res.raise_for_status = Mock()
    return res


def _mock_session(responses, mocker):
    session = Mock()
    session.get = Mock(side_effect=responses)
    mocker.patch(
        "bpp.management.commands.oai_all.requests.Session", return_value=session
    )
    return session


def test_oai_all_harvestuje_wszystkie_strony(mocker):
    session = _mock_session(
        [
            _mock_response(_page([1, 2], token="TOK1")),
            _mock_response(_page([3], token="")),  # brak tokenu → koniec
        ],
        mocker,
    )
    out = StringIO()
    call_command("oai_all", url="http://x", stdout=out)

    assert session.get.call_count == 2
    assert "3 rekordów w 2 żądaniach" in out.getvalue()
    # Drugie żądanie to przewijanie: verb + resumptionToken.
    _, kwargs = session.get.call_args
    assert kwargs["params"] == {"verb": "ListRecords", "resumptionToken": "TOK1"}
    assert kwargs["timeout"] == 60.0


def test_oai_all_wykrywa_petle_resumptiontoken(mocker):
    # Ten sam token w kółko — bezpiecznik musi przerwać.
    _mock_session(
        [
            _mock_response(_page([1], token="STUCK")),
            _mock_response(_page([2], token="STUCK")),
        ],
        mocker,
    )
    with pytest.raises(CommandError, match="powtórzył się"):
        call_command("oai_all", url="http://x", stdout=StringIO())


def test_oai_all_max_requests_bezpiecznik(mocker):
    # Każda strona ma nowy token — bez limitu leciałoby w nieskończoność.
    tokens = iter(range(1000))
    session = Mock()
    session.get = Mock(
        side_effect=lambda *a, **k: _mock_response(_page([1], token=f"t{next(tokens)}"))
    )
    mocker.patch(
        "bpp.management.commands.oai_all.requests.Session", return_value=session
    )
    with pytest.raises(CommandError, match="limit"):
        call_command("oai_all", url="http://x", max_requests=3, stdout=StringIO())


def test_oai_all_propaguje_blad_http(mocker):
    res = Mock()
    res.content = b""
    res.raise_for_status = Mock(side_effect=requests.HTTPError("500"))
    session = Mock()
    session.get = Mock(return_value=res)
    mocker.patch(
        "bpp.management.commands.oai_all.requests.Session", return_value=session
    )
    with pytest.raises(requests.HTTPError):
        call_command("oai_all", url="http://x", stdout=StringIO())


def test_oai_all_zglasza_blad_oai(mocker):
    err = (
        f'<?xml version="1.0"?><OAI-PMH {_NS}>'
        f'<error code="badArgument">zły argument</error></OAI-PMH>'
    ).encode()
    _mock_session([_mock_response(err)], mocker)
    with pytest.raises(CommandError, match="badArgument"):
        call_command("oai_all", url="http://x", stdout=StringIO())
