import pytest

from bpp.templatetags.prace import close_tags


@pytest.mark.parametrize(
    "i,o",
    [
        ("test<", "test&lt;"),
        ("test<x", "test<x/>"),
        ("test<test", "test<test/>"),
        ("test<strong>", "test<strong/>"),
        (None, None),
        ("", ""),
    ],
)
def test_close_tags(i, o):
    assert close_tags(i) == o
