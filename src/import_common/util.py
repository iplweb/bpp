from collections import defaultdict
from typing import Generator, List

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet

from .exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)

from django.utils.functional import cached_property

DEFAULT_COL_NAMES = [
    "imię",
    "imie",
    "imiona",
    "nazwisko",
    "nazwiska",
    "orcid",
    "pesel",
    "pbn_id",
    "stanowisko",
    "wydział",
    "jednostka",
    "numer",
]

DEFAULT_MIN_POINTS = 3


def normalize_cell_header(elem: openpyxl.cell.cell.Cell):
    s = str(elem.value).lower().split("\n")[0]

    s = s.replace(".", " ")
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()

    return s.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("-", "_")


def find_similar_row(
    sheet: Worksheet, try_names=None, min_points=None, max_row_length=128
):
    if try_names is None:
        try_names = DEFAULT_COL_NAMES

    if min_points is None:
        min_points = DEFAULT_MIN_POINTS

    for n, row in enumerate(sheet.rows, start=1):
        r = [normalize_cell_header(elem) for elem in row[:max_row_length]]
        points = 0
        for elem in try_names:
            if elem in r:
                points += 1
        if points >= min_points:
            return r, n


def znajdz_naglowek(
    sciezka,
    try_names=None,
    min_points=None,
):
    """
    :return: ([str, str...], no_row)
    """
    try:
        f: openpyxl.workbook.workbook.Workbook = openpyxl.load_workbook(sciezka)
    except InvalidFileException as e:
        raise ImproperFileException(e)

    # Sprawdź, ile jest skoroszytów
    if len(f.worksheets) != 1:
        raise BadNoOfSheetsException()

    s = f.worksheets[0]

    res = find_similar_row(s, try_names, min_points)

    if res is None:
        raise HeaderNotFoundException()

    return res


DEFAULT_BANNED_NAMES = ["pesel", "pesel_md5", "peselmd5"]


class XLSImportFile:
    def __init__(
        self,
        xls_path,
        try_names=None,
        min_points=None,
        banned_names=None,
        only_first_sheet=False,
    ):
        """
        :param xls_path: ścieżka do pliku
        :param try_names: nazwy które będą poszukiwane jako nagłówek
        :param min_points: ile z nazw nagłówka musi się odnaleźć w wierszu, żeby był tak potraktowany
        :param banned_names: niedozwolone nazwy nagłówków - te kolumny nie będą importowane (np PESEL)
        """

        self.xls_path = xls_path
        self.try_names = try_names
        self.min_points = min_points

        if banned_names is None:
            banned_names = DEFAULT_BANNED_NAMES
        self.banned_names = banned_names

        self.only_first_sheet = only_first_sheet

    @cached_property
    def xl_workbook(self) -> openpyxl.workbook.workbook.Workbook:
        return openpyxl.load_workbook(self.xls_path)

    @cached_property
    def sheet_limit_range_end(self):
        limit = None
        if self.only_first_sheet:
            limit = 1
        return limit

    @cached_property
    def sheet_row_cache(self):
        _cache = {}

        for n_sheet, sheet in enumerate(
            self.xl_workbook.worksheets[: self.sheet_limit_range_end]
        ):
            res = find_similar_row(
                sheet, try_names=self.try_names, min_points=self.min_points
            )
            if res is None:
                continue
            _cache[sheet] = res
        return _cache

    def count(self) -> int:
        """
        Zwraca całkowitą liczbę wierszy do analizy
        """
        total = 0
        for n_sheet, sheet in enumerate(self.xl_workbook.worksheets):
            res = self.sheet_row_cache.get(sheet)
            if res is None:
                continue
            labels, no = res
            total += sheet.max_row - no

        return total

    def data(self) -> Generator[dict, None, None]:
        """
        Ta funkcja dla każdego arkusza:
        1) znajduje nagłówek za pomoca funkcji `find_similar_row`,
        2) wczytuje poniższe wiersze do końca arkusza,
        3) dla każdego wiersza przypisuje nazwy kolumn z wiersza nagłówkowego
        4) zwraca słowniki.
        """

        for n_sheet, sheet in enumerate(self.xl_workbook.worksheets):

            res = self.sheet_row_cache.get(sheet)
            if res is None:
                continue

            colnames, no = res

            colnames = rename_duplicate_columns(colnames)

            colnames.append("__xls_loc_sheet__")
            colnames.append("__xls_loc_row__")

            for n_row, row in enumerate(sheet.rows):
                if n_row < res[1]:
                    continue
                data = [x.value for x in row[: len(colnames) - 2]]
                data.append(n_sheet)
                data.append(n_row)

                yld = dict(zip(colnames, data))

                for banned_name in self.banned_names:
                    if banned_name in yld:
                        del yld[banned_name]

                yield yld


def rename_duplicate_columns(s: List[str], marker: str = "_") -> List[str]:
    seen = defaultdict(lambda: 1)
    ret = []
    for elem in s:
        no_seen = seen[elem]
        if no_seen == 1:
            ret.append(elem)
        else:
            ret.append(f"{elem}{marker}{no_seen}")
        seen[elem] += 1
    return ret
