"""Golden (charakteryzacyjne) testy byte-identyczności display-funkcji błędów.

Fixture ``data/error_record_golden.json`` zdjęto z kodu SPRZED unifikacji
(P4). Po przepisaniu display-funkcji na ``ErrorRecord``/``parse()`` te same
asercje muszą przejść → dowód, że unifikacja NIE zmienia widocznego outputu
dla realistycznych danych legacy.

Domeny wejścia pinujemy per-funkcja (patrz ``scratch_build_fixture.py`` /
spec §6): każda funkcja tylko na kształtach, którymi realnie jest wołana.
Świadome ulepszenia (crash na payload-liczbie, hack admina) są WYKLUCZONE
z tej siatki i testowane w ``test_error_record_improvements.py``.
"""

import json
from pathlib import Path

import pytest

from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error
from pbn_export_queue.views.utils import (
    extract_pbn_error_from_komunikat,
    parse_error_details,
    parse_pbn_api_error,
)

_GOLDEN = json.loads(
    (Path(__file__).parent / "data" / "error_record_golden.json").read_text("utf-8")
)
_INPUTS = _GOLDEN["inputs"]


class _FakeSent:
    def __init__(self, exception, api_response_status=None):
        self.exception = exception
        self.api_response_status = api_response_status


def _cases(fn_key):
    return [(k, _GOLDEN[fn_key][k]) for k in sorted(_GOLDEN[fn_key])]


@pytest.mark.parametrize("case,expected", _cases("format_none"))
def test_golden_format_pbn_error_no_rodzaj(case, expected):
    assert str(format_pbn_error(_INPUTS[case] or "")) == expected


@pytest.mark.parametrize("case,expected", _cases("format_meryt"))
def test_golden_format_pbn_error_meryt(case, expected):
    assert str(format_pbn_error(_INPUTS[case] or "", "MERYT")) == expected


@pytest.mark.parametrize("case,expected", _cases("format_tech"))
def test_golden_format_pbn_error_tech(case, expected):
    assert str(format_pbn_error(_INPUTS[case] or "", "TECH")) == expected


@pytest.mark.parametrize("case,expected", _cases("parse_pbn_api_error"))
def test_golden_parse_pbn_api_error(case, expected):
    assert parse_pbn_api_error(_INPUTS[case]) == expected


@pytest.mark.parametrize("case,expected", _cases("extract_from_komunikat"))
def test_golden_extract_from_komunikat(case, expected):
    assert extract_pbn_error_from_komunikat(_INPUTS[case]) == expected


@pytest.mark.parametrize("case,expected", _cases("parse_error_details"))
def test_golden_parse_error_details(case, expected):
    assert parse_error_details(_FakeSent(_INPUTS[case], None)) == expected


@pytest.mark.parametrize("case,expected", _cases("parse_error_details_with_status"))
def test_golden_parse_error_details_with_status(case, expected):
    assert parse_error_details(_FakeSent(_INPUTS[case], 404)) == expected
