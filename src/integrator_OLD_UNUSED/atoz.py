# -*- encoding: utf-8 -*-
from django.db import transaction

from integrator2.models import ZrodloIntegrationRecord
from integrator2.util import ReadDataException, read_xls_data

ATOZ_IMPORT_COLUMNS = {
    'Title': "title",
    'URL': 'URL',
    'Publisher': 'publisher',
    'PrintISSN': 'issn',
    'OnlineISSN': 'e_issn'}


def read_atoz_import(file_contents):
    for data in read_xls_data(file_contents, wanted_columns=ATOZ_IMPORT_COLUMNS, header_row_name=u"LinkId"):
        if data['title'] and data['URL'] and data['publisher']:
            yield data


def read_atoz_xls_data(fobj):
    if fobj is None:
        raise ReadDataException("Brak pliku dla rekordu")

    for data in read_atoz_import(fobj.read()):
        yield data


@transaction.atomic
def atoz_import_data(parent, data):
    for record in data:
        ZrodloIntegrationRecord.objects.create(
            parent=parent,

            title=record['title'],
            www=record['URL'],
            publisher=record['publisher'],
            issn=record['issn'],
            e_issn=record['e_issn']
        )
