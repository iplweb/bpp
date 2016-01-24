# -*- encoding: utf-8 -*-

#
# 'Journal URL': 'http://www.scielo.br/scielo.php?pid=0001-3765&script=sci_serial',
# 'Journal EISSN (online version)': '',
# 'Journal ISSN (print version)': '0001-3765',
# 'Publisher': 'Academia Brasileira de Ci\xc3\xaancias',
# 'Journal title': 'Anais da Academia Brasileira de Ci\xc3\xaancias',
# 'Journal license': 'CC BY-NC',
import csv
from django.db import transaction
from bpp.models.openaccess import Licencja_OpenAccess
from integrator2.models import ZrodloIntegrationRecord


def read_doaj_csv_data(fobj):
    r = csv.reader(fobj)

    keys = r.next()

    while True:
        try:
            values = r.next()
        except StopIteration:
            break

        yield dict(zip(keys, values))


def doaj_import_data(parent, data):
    for elem in data:
        if elem.get("Journal title", None):

            license = elem['Journal license']

            if license:
                license = license.replace("CC BY", "CC-BY")

            ZrodloIntegrationRecord.objects.create(
                parent=parent,

                title=elem['Journal title'],
                www=elem['Journal URL'],
                publisher=elem['Publisher'],
                issn=elem['Journal ISSN (print version)'],
                e_issn=elem['Journal EISSN (online version)'],
                license=license
            )


def zrodlo_analyze_data(parent):
    for elem in ZrodloIntegrationRecord.objects.filter(parent=parent):
        res = elem.sprobuj_znalezc_zrodlo()
        if not res:
            elem.extra_info = "Brak takiego zrodla"
            elem.zanalizowano = True
            elem.save()
            continue

        if elem.license:
            try:
                Licencja_OpenAccess.objects.get(skrot=elem.license)
            except Licencja_OpenAccess.DoesNotExist:
                elem.extra_info = "Brak takiej licencji OpenAccess w BPP (%r)" % elem.license
                elem.zanalizowano = True
                elem.save()
                continue

        elem.matching_zrodlo = res
        elem.moze_byc_zintegrowany_automatycznie = True
        elem.zanalizowano = True
        elem.save()

@transaction.atomic
def zrodlo_integrate_data(parent):
    for elem in ZrodloIntegrationRecord.objects.filter(moze_byc_zintegrowany_automatycznie=True, parent=parent):
        zrodlo = elem.matching_zrodlo

        changed = False

        if elem.www:
            zrodlo.www = elem.www
            changed = True

        if elem.license:
            zrodlo.openaccess_licencja = Licencja_OpenAccess.objects.get(skrot=elem.license)
            changed = True

        if elem.issn:
            zrodlo.issn = elem.issn
            changed = True

        if elem.e_issn:
            zrodlo.e_issn = elem.e_issn
            changed = True

        if elem.publisher:
            zrodlo.wydawca = elem.publisher
            changed = True

        if changed:
            elem.zintegrowano = True
            elem.save()
            zrodlo.save()
