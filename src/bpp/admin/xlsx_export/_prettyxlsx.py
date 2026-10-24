"""Tablib - XLSX Support."""

from io import BytesIO

from openpyxl.workbook import Workbook
from tablib.formats._xlsx import XLSXFormat

from bpp.util import (
    sanitize_tablib_dataset,
    worksheet_columns_autosize,
    worksheet_create_table,
    worksheet_create_urls,
)


class PrettyXLSXFormat(XLSXFormat):
    @classmethod
    def export_set(cls, dataset, freeze_panes=True):
        """Returns XLSX representation of Dataset."""

        wb = Workbook()
        ws = wb.worksheets[0]
        ws.title = dataset.title if dataset.title else "Eksport z BPP"

        # Tekst zaczynający się od =, +, -, @ itd. zapisujemy jako tekst, nie
        # formułę. Kolumny *_url zamieniamy na HYPERLINK dopiero niżej.
        sanitize_tablib_dataset(dataset)
        cls.dset_sheet(dataset, ws, freeze_panes=freeze_panes)

        worksheet_create_urls(ws)
        worksheet_columns_autosize(ws)
        worksheet_create_table(ws)

        if freeze_panes:
            freeze_panes_cell = getattr(dataset, "prettyxlsx_freeze_panes", "F2")
            if freeze_panes_cell:
                ws.freeze_panes = ws[freeze_panes_cell]

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()
