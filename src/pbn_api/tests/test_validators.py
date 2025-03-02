import pytest

from pbn_api.validators import check_mongoId


@pytest.mark.parametrize(
    "s, exp",
    [
        ("60e72cdf2467f01e93118d00", True),
        ("60E72CDF2467f01e93118d00", True),
        ("60e72cdf2467f01e93118d0X", False),
    ],
)
def test_check_mongoId(s, exp):
    assert check_mongoId(s) == exp
