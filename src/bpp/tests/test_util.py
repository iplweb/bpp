import pytest

from bpp.util import wytnij_isbn_z_uwag


@pytest.mark.django_db
def test_zaktualizuj_cache_ciagle(
    django_assert_num_queries,
    wydawnictwo_ciagle_z_dwoma_autorami,
    wydawnictwo_zwarte_z_autorem,
):
    with django_assert_num_queries(2):
        wydawnictwo_ciagle_z_dwoma_autorami.zaktualizuj_cache()


@pytest.mark.django_db
def test_zaktualizuj_cache_zwarte(
    django_assert_num_queries, wydawnictwo_zwarte_z_autorem
):
    with django_assert_num_queries(2):
        wydawnictwo_zwarte_z_autorem.zaktualizuj_cache()


@pytest.mark.parametrize(
    "input,output,rest",
    [
        ("ISBN 978-83-7374-091-4, ten tego", "978-83-7374-091-4", "ten tego"),
        ("ISBN 83-200-1817-X", "83-200-1817-X", ""),
        ("tu nie ma ISBNu", None, None),
        ("ISBN-10 978-83-7374-091-4; ISBN-13 958498498894, ten tego", None, None),
    ],
)
def test_wytnij_isbn_z_uwag(input, output, rest):
    res = wytnij_isbn_z_uwag(input)
    if output is None:
        assert res is None
        return

    isbn, reszta = res
    assert isbn == output
    assert reszta == rest
