import itertools
from enum import Enum
from typing import Any, List

import openpyxl.worksheet.worksheet
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo


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
