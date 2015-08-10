# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
import xlrd
from django_bpp.util import wait_for_object
from integrator.models import AutorIntegrationFile, AUTOR_IMPORT_COLUMNS

logger = get_task_logger(__name__)
from django_bpp.celery import app


def find_header_row(sheet, first_column_value):
    for a in range(sheet.nrows):
        if sheet.row(a)[0].value.upper() == first_column_value.upper():
            return a


class ReadDataException(Exception):
    pass

def build_mapping(xls_columns, wanted_columns):
    ret = []
    upper_wanted_columns = dict([(x.upper(), wanted_columns[x]) for x in wanted_columns.keys()])
    for elem in xls_columns:
        val = elem.value.upper()
        if val in upper_wanted_columns:
            ret.append(upper_wanted_columns[val])
            continue
        ret.append(None)

    return ret



def read_xls_data(file_contents, wanted_columns):
    book = xlrd.open_workbook(file_contents=file_contents)
    for sheet in book.sheets():
        header_row_no = find_header_row(sheet, u"Tytuł/Stopień")
        if header_row_no is None:
            raise ReadDataException("Brak wiersza nagłówka")
        header_row_values = sheet.row(header_row_no)
        read_data_mapping = list(enumerate(build_mapping(header_row_values, wanted_columns)))

        for row in range(header_row_no+1, sheet.nrows):
            dct = {}
            for no, elem in read_data_mapping:
                dct[elem] = sheet.row(row)[no].value
            yield dct

def read_autor_import(file_contents):
    for data in read_xls_data(file_contents, wanted_columns=AUTOR_IMPORT_COLUMNS):
        if data['nazwisko'] and data['imie'] and data['nazwa_jednostki'] and data['pbn_id']:
            yield data

def real_analyze_file(fobj):

    if fobj is None:
        raise ReadDataException("Brak pliku dla rekordu z PK %i" % pk)

    for data in read_autor_import(fobj.read()):
        print data

@app.task
def analyze_file(pk):
    obj = wait_for_object(AutorIntegrationFile, pk)
    try:
        real_analyze_file(obj.file)
    except Exception, e:
        obj.extra_info = str(e)
        obj.save()

        raise e