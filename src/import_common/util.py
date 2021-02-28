import xlrd

from .exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)


def znajdz_naglowek(
    sciezka,
    try_names=[
        "imię",
        "imie",
        "imiona",
        "nazwisko",
        "nazwiska",
        "orcid",
        "pesel",
        "pbn-id",
        "pbn_id",
        "pbn id",
        "stanowisko",
        "wydział",
        "jednostka",
    ],
    min_points=3,
):
    """
    :return: ([str, str...], no_row)
    """
    try:
        f = xlrd.open_workbook(sciezka)
    except xlrd.XLRDError as e:
        raise ImproperFileException(e)

    # Sprawdź, ile jest skoroszytów
    if len(f.sheets()) != 1:
        raise BadNoOfSheetsException()

    s = f.sheet_by_index(0)

    for n in range(s.nrows):
        r = [str(elem.value).lower() for elem in s.row(n)]
        points = 0
        for elem in try_names:
            if elem in r:
                points += 1
        if points >= min_points:
            return r, n

    raise HeaderNotFoundException()
