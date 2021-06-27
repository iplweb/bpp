import csv
import sys

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

wb = Workbook()
ws = wb.active
for row in csv.reader(sys.stdin):
    new_row = map(lambda elem: ILLEGAL_CHARACTERS_RE.sub(r"", elem), row)
    ws.append(list(new_row))
wb.save(sys.stdout.buffer)
