# -*- encoding: utf-8 -*-
from hashlib import md5

import xlrd
from django.db import transaction

from .egeria_2012 import dopasuj_autora


def importuj_wiersz(dct, row, sheet, row_no, sheet_no):
    autor = dopasuj_autora(dct['IMIĘ'].value, dct['NAZWISKO'].value, dct['NAZWA JEDNOSTKI'].value, dct['Stanowisko'].value)
    if autor:
        autor.pesel_md5 = md5(dct['PESEL'].value).hexdigest()
        autor.pbn_id = dct['PBN ID'].value
        autor.save()
    # import pdb; pdb.set_trace()


def import_sheet(sheet, sheet_no, label_row_no=3):
    labels = [x.value for x in sheet.row(label_row_no-1)]
    for a in range(len(labels)):
        if labels[a] == '':
            labels[a] = str(a)

    for nrow in range(label_row_no, sheet.nrows):
        row = sheet.row(nrow)
        dct = dict(list(zip(labels, row)))
        importuj_wiersz(dct, row, sheet, nrow, sheet_no)


@transaction.atomic
def importuj_pbn_ids(plik_xls):
    # Tytuł/Stopień	NAZWISKO	IMIĘ	Wydział	Stanowisko	NAZWA JEDNOSTKI	PESEL	PBN ID

    book = xlrd.open_workbook(plik_xls)

    arkusze_ignorowane = ['zbiorczy', ]

    for cnt in range(book.nsheets):
        sheet = book.sheet_by_index(cnt)
        if sheet.name in arkusze_ignorowane:
            continue
        import_sheet(sheet, cnt)


if __name__ == "__main__":
    import sys

    import django; django.setup()
    importuj_pbn_ids(sys.argv[1])