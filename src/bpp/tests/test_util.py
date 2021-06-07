import pytest

from bpp.util import knapsack, wytnij_isbn_z_uwag


@pytest.mark.django_db
def test_zaktualizuj_cache_ciagle(
    django_assert_max_num_queries,
    wydawnictwo_ciagle_z_dwoma_autorami,
    wydawnictwo_zwarte_z_autorem,
):
    with django_assert_max_num_queries(4):
        wydawnictwo_ciagle_z_dwoma_autorami.zaktualizuj_cache()


@pytest.mark.django_db
def test_zaktualizuj_cache_zwarte(
    django_assert_max_num_queries, wydawnictwo_zwarte_z_autorem
):
    with django_assert_max_num_queries(4):
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


def test_knapsack_empty():
    assert knapsack(10, [], [], []) == (0, [])


@pytest.mark.timeout(3)
def test_knapsack_very_long():
    # Test na optymalizacje sytuacji gdy chcemy dostac znacznie wiecej punktow niz wychdozi z danej listy,
    knapsack(99900, [1] * 99800, [1] * 99800, [1] * 99800)


def test_knapsack_zwracaj_liste():
    assert (
        knapsack(
            10,
            [1, 2, 3, 4, 5],
            [1, 2, 3, 4, 5],
            [
                "a",
                "b",
                "c",
                "d",
                "e",
            ],
            True,
        )
        == (10, ["d", "c", "b", "a"])
    )


def test_knapsack_nie_zwracaj_listy():
    assert (
        knapsack(
            10,
            [1, 2, 3, 4, 5],
            [1, 2, 3, 4, 5],
            [
                "a",
                "b",
                "c",
                "d",
                "e",
            ],
            zwracaj_liste_przedmiotow=False,
        )
        == (10, [])
    )
