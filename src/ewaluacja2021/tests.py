# Create your tests here.
from ewaluacja2021.util import chunker


def test_chunker():
    assert list(
        chunker(
            3,
            [
                [0, 1, 2, 3],
                [0, 1, 2, 3],
                [0, 1, 2, 3],
                [3, 4, 5, 6],
                [3, 4, 5, 6],
                [3, 4, 5],
                [7, 8, 9],
            ],
        )
    ) == [
        ([0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]),
        ([3, 4, 5, 6], [3, 4, 5, 6], [3, 4, 5]),
        ([7, 8, 9],),
    ]
