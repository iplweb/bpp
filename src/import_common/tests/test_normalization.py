import pytest

from import_common.normalization import normalize_doi, normalize_kod_dyscypliny


@pytest.mark.parametrize(
    "i,o",
    [
        ("101_0", "1.1"),
        ("111_0", "1.11"),
        ("407", "4.7"),
        ("411", "4.11"),
        ("4.1", "4.1"),
    ],
)
def test_normalize_kod_dyscypliny(i, o):
    assert normalize_kod_dyscypliny(i) == o


@pytest.mark.parametrize(
    "i,o",
    [
        (
            "http://dx.doi.org/10.1097/meg.0000000000000237",
            "10.1097/meg.0000000000000237",
        ),
        (
            "https://dx.doi.org/10.1097/meg.0000000000000237",
            "10.1097/meg.0000000000000237",
        ),
        ("DX.DOI.ORG/10.1097/MEG.0000000000000237", "10.1097/meg.0000000000000237"),
        (
            "   DX.DOI.ORG/10.1097/MEG.0000000000000237   ",
            "10.1097/meg.0000000000000237",
        ),
        (None, None),
        ("", None),
    ],
)
def test_normalize_doi(i, o):
    assert normalize_doi(i) == o
