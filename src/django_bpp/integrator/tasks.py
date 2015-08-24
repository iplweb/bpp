# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.core.management import call_command
from django.core.urlresolvers import reverse
from django.db import transaction
import xlrd
from bpp.models.autor import Autor, Tytul
from django_bpp.util import wait_for_object
from integrator.models import AutorIntegrationFile, AUTOR_IMPORT_COLUMNS, AutorIntegrationRecord

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

        for row in range(header_row_no + 1, sheet.nrows):
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
        yield data


@transaction.atomic
def import_data(parent, data):
    for record in data:
        AutorIntegrationRecord.objects.create(
            parent=parent,

            tytul_skrot=record['tytul_skrot'],
            nazwisko=record['nazwisko'],
            imie=record['imie'],
            nazwa_jednostki=record['nazwa_jednostki'],
            pbn_id=record['pbn_id'],
        )


@transaction.atomic
def analyze_data(parent):
    for air in AutorIntegrationRecord.objects.filter(parent=parent):

        czy_jest_taki_autor = air.sprobuj_zlokalizowac_autora()
        if czy_jest_taki_autor != True:
            air.extra_info = "Brak takiego autora"
            air.zanalizowano = True
            air.save()
            continue

        czy_jest_taka_jednostka = air.sprobuj_zlokalizowac_jednostke()
        if czy_jest_taka_jednostka != True:
            air.extra_info = "Brak takiej jednostki (%r)" % czy_jest_taka_jednostka
            air.zanalizowano = True
            air.save()
            continue

        # Można integrować automatycznie?
        # Sprawdz tytul_skrot, sprawdz PBN_ID czy do integera sie da zrobic
        try:
            Tytul.objects.get(skrot=air.tytul_skrot)
        except Tytul.DoesNotExist:
            air.extra_info = "Brak takiego tytulu"
            air.save()
            continue

        try:
            int(air.pbn_id.strip(".0"))
        except (TypeError, ValueError):
            air.extra_info = "PBN_ID nie jest cyfra"
            air.save()
            continue

        air.moze_byc_zintegrowany_automatycznie = True
        air.zanalizowano = True
        air.save()


@transaction.atomic
def integrate_data(parent):
    for air in AutorIntegrationRecord.objects.filter(parent=parent, moze_byc_zintegrowany_automatycznie=True):
        air.matching_autor.pbn_id = int(air.pbn_id.strip(".0"))
        air.matching_autor.tytul = Tytul.objects.get(skrot=air.tytul_skrot)
        air.matching_autor.save()
        air.zintegrowano = True
        air.save()


@app.task
def analyze_file(pk):
    obj = wait_for_object(AutorIntegrationFile, pk)

    def informuj(komunikat, dont_persist=True):
        try:
            msg = u'<a href="%s">Integracja pliku "%s": %s</a>. '
            url = reverse("integrator:detail", args=(obj.pk, ))
            call_command('send_message', obj.owner, msg % (url, obj.filename(), komunikat), dont_persist=dont_persist)
        except Exception, e:
            obj.extra_info = str(e)
            obj.status = 3
            obj.save()
            raise

    obj.status = 1
    obj.save()

    try:
        import_data(obj, real_analyze_file(obj.file))
    except Exception, e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj(u"wystąpił błąd")
        raise

    informuj(u"zaimportowano, trwa analiza danych")

    try:
        analyze_data(obj)
    except Exception, e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj(u"wystąpił błąd")
        raise

    informuj(u"rozpoczęto integrację")

    integrate_data(obj)
    obj.status = 2
    obj.save()

    informuj(u"zakończono integrację", dont_persist=False)

