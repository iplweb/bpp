# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.db import transaction

from bpp.models.autor import Tytul, Autor_Jednostka
from integrator2.models import AUTOR_IMPORT_COLUMNS, AutorIntegrationRecord
from integrator2.util import read_xls_data, ReadDataException

logger = get_task_logger(__name__)


def read_autor_import(file_contents):
    for data in read_xls_data(file_contents, wanted_columns=AUTOR_IMPORT_COLUMNS, header_row_name=u"Tytuł/Stopień"):
        if data['nazwisko'] and data['imie'] and data['nazwa_jednostki'] and data['pbn_id']:
            yield data


def real_autorzy_analyze_file(fobj):
    if fobj is None:
        raise ReadDataException("Brak pliku dla rekordu z PK %i" % pk)

    for data in read_autor_import(fobj.read()):
        yield data


@transaction.atomic
def autorzy_import_data(parent, data):
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
def autorzy_analyze_data(parent):
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
        if air.tytul_skrot and air.tytul_skrot.strip():
            try:
                Tytul.objects.get(skrot=air.tytul_skrot)
            except Tytul.DoesNotExist:
                air.extra_info = "Brak takiego tytulu"
                air.save()
                continue

        try:
            int(float(air.pbn_id))
        except (TypeError, ValueError):
            air.extra_info = "PBN_ID nie jest cyfra"
            air.save()
            continue

        air.moze_byc_zintegrowany_automatycznie = True
        air.zanalizowano = True
        air.save()


@transaction.atomic
def autorzy_integrate_data(parent):
    for air in AutorIntegrationRecord.objects.filter(parent=parent, moze_byc_zintegrowany_automatycznie=True):

        aut = air.matching_autor

        aut.pbn_id = int(float(air.pbn_id))
        if air.tytul_skrot and air.tytul_skrot.strip():
            aut.tytul = Tytul.objects.get(skrot=air.tytul_skrot)

        if air.matching_jednostka not in aut.jednostki.all():
            Autor_Jednostka.objects.create(autor=aut, jednostka=air.matching_jednostka)
        aut.save()

        air.zintegrowano = True
        air.save()
