# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.db import transaction

from bpp.models.autor import Tytul, Autor_Jednostka
from integrator.models import AUTOR_BEZ_PBN_IMPORT_COLUMNS, AutorIntegrationRecord
from integrator.util import read_xls_data, ReadDataException

logger = get_task_logger(__name__)


def read_autor_import(file_contents):
    for data in read_xls_data(file_contents, wanted_columns=AUTOR_BEZ_PBN_IMPORT_COLUMNS,
                              header_row_name=u"Tytuł/Stopień", ignored_sheet_names=['zbiorczy']):
        if data['nazwisko'] and data['imie'] and data['nazwa_jednostki']:
            yield data


def real_autorzy_bez_pbn_analyze_file(fobj):
    if fobj is None:
        raise ReadDataException("Brak pliku dla rekordu z PK %i" % pk)

    for data in read_autor_import(fobj.read()):
        yield data


@transaction.atomic
def autorzy_bez_pbn_import_data(parent, data):
    for record in data:
        AutorIntegrationRecord.objects.create(
            parent=parent,

            tytul_skrot=record['tytul_skrot'],
            nazwisko=record['nazwisko'],
            imie=record['imie'],
            nazwa_jednostki=record['nazwa_jednostki'],
        )


@transaction.atomic
def autorzy_bez_pbn_analyze_data(parent):
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

        air.moze_byc_zintegrowany_automatycznie = True
        air.zanalizowano = True
        air.save()


@transaction.atomic
def autorzy_bez_pbn_integrate_data(parent):
    for air in AutorIntegrationRecord.objects.filter(parent=parent, moze_byc_zintegrowany_automatycznie=True):

        aut = air.matching_autor

        aut.pbn_id = int(float(air.pbn_id))
        aut.tytul = Tytul.objects.get(skrot=air.tytul_skrot)

        if air.matching_jednostka not in aut.jednostki.all():
            Autor_Jednostka.objects.create(autor=aut, jednostka=air.matching_jednostka)
        aut.save()

        air.zintegrowano = True
        air.save()
