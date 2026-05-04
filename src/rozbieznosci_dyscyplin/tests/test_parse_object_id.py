"""Testy funkcji `parse_object_id` (parsowanie PK krotek z modeli widoków)."""

import pytest

from rozbieznosci_dyscyplin.admin import parse_object_id


@pytest.mark.parametrize(
    "i,o",
    [
        ("(1,1,1)", [1, 1, 1]),
        ("asdf", None),
        ("(389489,34893489,4893398489)", [389489, 34893489, 4893398489]),
        ("(1,2,3,4)", None),
        ("[1,2,3]", [1, 2, 3]),
        ("{1:1,2:2,3:3}", None),
    ],
)
def test_parse_object_id(i, o):
    assert parse_object_id(i) == o


@pytest.mark.parametrize(
    "i,o",
    [
        ("(1,2,3,4)", [1, 2, 3, 4]),
        ("(1,2,3)", None),  # za malo elementow
        ("(1,2,3,4,5)", None),  # za duzo
        ("[1,2,3,4]", [1, 2, 3, 4]),
        ("(100,200,300,400)", [100, 200, 300, 400]),
    ],
)
def test_parse_object_id_max_len_4(i, o):
    """Test parse_object_id with max_len=4 for RozbieznosciZrodelView."""
    assert parse_object_id(i, max_len=4) == o
