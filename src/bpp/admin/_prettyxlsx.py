""" Tablib - XLSX Support.
"""

from io import BytesIO

from openpyxl.workbook import Workbook
from tablib.formats._xlsx import XLSXFormat

from bpp.util import worksheet_columns_autosize, worksheet_create_table


class PrettyXLSXFormat(XLSXFormat):
    @classmethod
    def export_set(cls, dataset, freeze_panes=True):
        """Returns XLSX representation of Dataset."""

        wb = Workbook()
        ws = wb.worksheets[0]
        ws.title = dataset.title if dataset.title else "Eksport z BPP"

        cls.dset_sheet(dataset, ws, freeze_panes=freeze_panes)

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws)

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()
