import itertools
from collections import OrderedDict
from decimal import Decimal
from enum import Enum
from typing import Any, List, Union

import openpyxl.worksheet.worksheet
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo
from unidecode import unidecode

from django.utils.functional import cached_property


def chunker(n, iterable):
    iterable = iter(iterable)
    while True:
        x = tuple(itertools.islice(iterable, n))
        if not x:
            return
        yield x


class SHUFFLE_TYPE(Enum):
    BEGIN = 1
    MIDDLE = 2
    END = 3
    RANDOM = 4


import random


def shuffle_array(
    array, start, length, no_shuffles=1, shuffle_type=SHUFFLE_TYPE.MIDDLE
):

    first = array[:start]
    second = array[start : start + length]
    third = array[start + length :]

    i = shuffle_type
    if shuffle_type == SHUFFLE_TYPE.RANDOM:
        i = random.randint(1, 3)

    if i == SHUFFLE_TYPE.BEGIN:
        for a in range(no_shuffles):
            random.shuffle(first)
    elif i == SHUFFLE_TYPE.MIDDLE:
        for a in range(no_shuffles):
            random.shuffle(second)
    elif i == SHUFFLE_TYPE.END:
        for a in range(no_shuffles):
            random.shuffle(third)

    return first + second + third


def output_table_to_xlsx(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    title: str,
    headers: List[str],
    dataset: List[List[Any]],
    totals: List[str] = None,
):
    ws.append(headers)

    table_columns = tuple(
        TableColumn(id=h, name=header) for h, header in enumerate(headers, start=1)
    )

    if totals:
        footer_row = []
        for no, elem in enumerate(table_columns):
            if no == 0:
                footer_row.append("Suma")
                total_column = table_columns[0]
                total_column.totalsRowLabel = footer_row[0]
                continue

            if elem.name in totals:
                count_column = table_columns[no]
                count_column.totalsRowFunction = "sum"
                footer_row.append(f"=SUBTOTAL(109,{title}[{elem.name}])")
                continue

            footer_row.append("")

    for cell in ws[ws.max_row : ws.max_row]:
        cell.font = openpyxl.styles.Font(bold=True)

    first_table_row = ws.max_row

    for row in dataset:
        ws.append(row)

    ws.append(footer_row)

    if dataset:
        max_column = ws.max_column
        max_column_letter = get_column_letter(max_column)
        max_row = ws.max_row

        style = TableStyleInfo(
            name="TableStyleMedium9",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=True,
        )
        tab = Table(
            displayName=title,
            ref=f"A{first_table_row}:{max_column_letter}{max_row}",
            autoFilter=AutoFilter(
                ref=f"A{first_table_row}:{max_column_letter}{max_row - 1}"
            ),
            totalsRowShown=True if totals else False,
            totalsRowCount=1 if totals else False,
            tableStyleInfo=style,
            tableColumns=table_columns,
        )

        ws.add_table(tab)

    for elem in totals:
        letter = get_column_letter(headers.index(elem) + 1)
        for row in range(2, ws.max_row):
            ws[f"{letter}{row}"].number_format = "#,####0.0000"

        # Ustaw automatyczny rozmiar
        ws.column_dimensions[letter].bestFit = True

    max_width = 55
    for ncol, col in enumerate(ws.columns):
        max_length = 0
        column = col[0].column_letter  # Get the column name

        # Nie ustawiaj szerokosci tym kolumnom, one będą jako auto-size
        if headers[ncol] in totals:
            continue

        for cell in col:
            try:  # Necessary to avoid error on empty cells
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except (ValueError, TypeError):
                pass
        adjusted_width = (max_length + 2) * 1.1
        if adjusted_width > max_width:
            adjusted_width = max_width
        ws.column_dimensions[column].width = adjusted_width


def autor2fn(autor):
    return (
        f"{autor.nazwisko}_{autor.imiona}".lower()
        .strip()
        .replace(" ", "_")
        .replace("*", "x")
        .replace("-", "_")
    )


def normalize_xlsx_header_column_name(s):
    if s is None:
        return
    s = str(s).replace(".", " ").replace("-", " ").replace("/", " ").strip()
    if not s:
        return

    while s.find("  ") >= 0:
        s = s.replace("  ", " ")

    return unidecode(s.strip()).replace(" ", "_").lower()


def find_header_row(
    worksheet: openpyxl.worksheet.worksheet.Worksheet,
    header_row: List[str],
    max_header_row=100,
) -> Union[None, int]:
    """
    Poszukuje wierwsza nagłówka w skoroszycie ``worksheet``.

    :param max_header_row: maksymalny wiersz, w którym poszukujemy nagłówka
    :return: wiersza nagłówkowego - jeżeli znaleziony
    """

    normalized_header_row = [normalize_xlsx_header_column_name(v) for v in header_row]
    max_header_row = min(worksheet.max_row, max_header_row)

    for nrow, row in enumerate(worksheet[1:max_header_row], start=1):
        normalized_cell_values = [
            normalize_xlsx_header_column_name(cell.value)
            for cell in row[: len(header_row)]
        ]
        if normalized_cell_values == normalized_header_row:
            return nrow


class InputXLSX:
    def __init__(self, fn, header_cols):
        self.fn = fn
        self.header_cols = header_cols

    @cached_property
    def workbook(self):
        return openpyxl.load_workbook(self.fn)

    @cached_property
    def worksheet(self):
        return self.workbook.worksheets[0]

    @cached_property
    def header_normalized(self):
        return [normalize_xlsx_header_column_name(col) for col in self.header_cols]

    @cached_property
    def header_row(self):
        return find_header_row(self.worksheet, self.header_cols)

    def rows_as_list(self):
        if self.header_row is None:
            raise ValueError("Brak wiersza nagłówka w pliku XLS.")

        min_row = self.header_row + 1
        max_row = self.worksheet.max_row
        for row in self.worksheet[min_row:max_row]:
            yield [cell.value for cell in row]

    def rows_as_dict(self):
        keys = self.header_normalized[:]
        keys.append("__nrow__")

        for nrow, row in enumerate(self.rows_as_list(), start=self.header_row + 1):
            row = OrderedDict(zip(keys, row))
            row["__nrow__"] = nrow
            yield row


def float_or_string_or_int_or_none_to_decimal(i, decimal_places=4):
    if i is None:
        return i
    if type(i) in [int, Decimal, str]:
        return Decimal(i)
    if isinstance(i, float):
        return Decimal(f"%.{decimal_places}f" % round(i, decimal_places))
    raise NotImplementedError(f"Type {type(i)} not supported.")