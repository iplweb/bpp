import pytest

from import_common.normalization import normalize_kod_dyscypliny


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
