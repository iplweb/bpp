# -*- encoding: utf-8 -*-
import os
import zipfile
from tempfile import mkdtemp, mkstemp

from django.core.files.base import File
from django.core.management import call_command
from django.core.urlresolvers import reverse
from lxml.etree import tostring

from bpp.models.system import Charakter_Formalny
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte
from bpp.util import remove_old_objects
from django_bpp.celery_tasks import app
from django_bpp.util import wait_for_object
from eksport_pbn.models import PlikEksportuPBN, DATE_CREATED_ON, DATE_UPDATED_ON


class ExportPBNException(Exception):
    pass


class BrakTakiegoRodzajuDatyException(ExportPBNException):
    pass


def data_kw(rodzaj_daty, od_daty, do_daty=None):
    if od_daty is None or rodzaj_daty is None:
        return {}

    flds = {DATE_CREATED_ON: 'utworzono',
            DATE_UPDATED_ON: 'ostatnio_zmieniony'}

    ret = {}

    try:
        ret['rekord__%s__gte' % flds[rodzaj_daty]] = od_daty
    except KeyError:
        raise BrakTakiegoRodzajuDatyException(rodzaj_daty)

    if do_daty:
        ret['rekord__%s__lte' % flds[rodzaj_daty]] = do_daty

    return ret


def id_ciaglych(wydzial, od_roku, do_roku, rodzaj_daty=None, od_daty=None, do_daty=None):
    return Wydawnictwo_Ciagle_Autor.objects.filter(
        jednostka__wydzial=wydzial,
        rekord__rok__gte=od_roku,
        rekord__rok__lte=do_roku,
        rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(artykul_pbn=True),
        **data_kw(rodzaj_daty, od_daty, do_daty)
    ).order_by("rekord_id").distinct("rekord_id").only("rekord_id").values_list("rekord_id", flat=True)


def id_zwartych(wydzial, od_roku, do_roku, ksiazki, rozdzialy, rodzaj_daty=None, od_daty=None, do_daty=None):
    if ksiazki:
        for rekord in Wydawnictwo_Zwarte_Autor.objects.filter(
                jednostka__wydzial=wydzial,
                rekord__rok__gte=od_roku,
                rekord__rok__lte=do_roku,
                rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(ksiazka_pbn=True),
                **data_kw(rodzaj_daty, od_daty, do_daty)
        ).order_by("rekord_id").distinct("rekord_id").only("rekord_id").values_list("rekord_id", flat=True):
            yield rekord

    if rozdzialy:
        for rekord in Wydawnictwo_Zwarte_Autor.objects.filter(
                jednostka__wydzial=wydzial,
                rekord__rok__gte=od_roku,
                rekord__rok__lte=do_roku,
                rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(rozdzial_pbn=True),
                **data_kw(rodzaj_daty, od_daty, do_daty)
        ).order_by("rekord_id").distinct("rekord_id").only("rekord_id").values_list("rekord_id", flat=True):
            yield rekord


def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), "pbn/metadata/%s" % file)


header = """<?xml version="1.0" encoding="UTF-8"?>
<works pbn-unit-id="%s"
    xmlns="http://pbn.nauka.gov.pl/-/ns/bibliography"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://pbn.nauka.gov.pl/-/ns/bibliography PBN-report.xsd ">
    """


@app.task
def eksport_pbn(pk):
    obj = wait_for_object(PlikEksportuPBN, pk)

    user = obj.owner
    wydzial = obj.wydzial
    od_roku = obj.od_roku
    do_roku = obj.do_roku

    artykuly = obj.artykuly
    ksiazki = obj.ksiazki
    rozdzialy = obj.rozdzialy

    od_daty = obj.od_daty
    do_daty = obj.do_daty
    rodzaj_daty = obj.rodzaj_daty

    rokstr = obj.get_rok_string()

    def informuj(msg, dont_persist=True):
        call_command('send_message', user, msg, no_persist=dont_persist)

    def gen_ser():
        if artykuly:
            for ic in id_ciaglych(wydzial, od_roku, do_roku, rodzaj_daty=rodzaj_daty, od_daty=od_daty, do_daty=do_daty):
                yield Wydawnictwo_Ciagle.objects.get(pk=ic).eksport_pbn_serializuj(wydzial)

        if ksiazki and rozdzialy:
            informuj(u"... generuję książki i rodziały dla %s - %s" % (wydzial.nazwa, rokstr))
        elif rozdzialy:
            informuj(u"... generuję rodziały dla %s - %s" % (wydzial.nazwa, rokstr))
        elif ksiazki:
            informuj(u"... generuję książki dla %s - %s" % (wydzial.nazwa, rokstr))

        for iz in id_zwartych(wydzial, od_roku, do_roku, ksiazki, rozdzialy, rodzaj_daty=rodzaj_daty, od_daty=od_daty, do_daty=do_daty):
            yield Wydawnictwo_Zwarte.objects.get(pk=iz).eksport_pbn_serializuj(wydzial)

    tmpdir = mkdtemp()

    count = 1
    cur_data_size = 1024 * 1024
    outfile = None

    def close_outfile(outfile):
        if outfile is None: return
        outfile.write('</works>')
        outfile.close()

    hdr = header % wydzial.pbn_id

    for element in gen_ser():

        if cur_data_size >= 1024 * 1024 - 4096:
            close_outfile(outfile)

            outfile = open(os.path.join(tmpdir, "%s.xml" % count), 'wb')
            outfile.write(hdr)
            cur_data_size = len(hdr)
            count += 1

        data = tostring(element, pretty_print=True)
        outfile.write(data)

        cur_data_size += len(data)

    close_outfile(outfile)

    fno, fn = mkstemp()
    zipf = zipfile.ZipFile(fn, 'w')
    zipdir(tmpdir, zipf)
    zipf.close()

    pep = obj
    pep.file.save(fn, File(open(fn)))
    pep.save()

    informuj(u"Zakończono. <a href=%s>Kliknij tutaj, aby pobrać eksport PBN dla %s - %s</a>. " %
             (reverse("eksport_pbn:pobierz", args=(pep.pk,)),
              wydzial.nazwa,
              rokstr),
             dont_persist=False)

    return pep.pk


@app.task
def remove_old_eksport_pbn_files():
    return remove_old_objects(PlikEksportuPBN)
