# -*- encoding: utf-8 -*-
import xlrd

def find_header_row(sheet, first_column_value):
    for a in range(sheet.nrows):
        f = sheet.row(a)[0].value
        if hasattr(f, 'upper') and f.upper() == first_column_value.upper():
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



def read_xls_data(file_contents, wanted_columns, header_row_name):
    book = xlrd.open_workbook(file_contents=file_contents)
    for sheet in book.sheets():
        header_row_no = find_header_row(sheet, header_row_name)
        if header_row_no is None:
            raise ReadDataException("Brak wiersza nagłówka")
        header_row_values = sheet.row(header_row_no)
        read_data_mapping = list(enumerate(build_mapping(header_row_values, wanted_columns)))

        for row in range(header_row_no + 1, sheet.nrows):
            dct = {}
            for no, elem in read_data_mapping:
                dct[elem] = sheet.row(row)[no].value
            yield dct

