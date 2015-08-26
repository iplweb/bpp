# -*- encoding: utf-8 -*-
from tempfile import mkdtemp, mkstemp
import zipfile
from django.core.files.base import File
from django.core.management import call_command
from django.core.urlresolvers import reverse
from lxml.etree import Element, tostring
import os
from bpp.models.cache import Autorzy
from bpp.models.profile import BppUser
from bpp.models.struktura import Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte

from django_bpp.celery import app
from eksport_pbn.models import PlikEksportuPBN


def id_ciaglych(wydzial, rok):
    return Wydawnictwo_Ciagle_Autor.objects.filter(
        jednostka__wydzial=wydzial,
        rekord__rok=rok).only("rekord_id").values_list("rekord_id", flat=True).distinct()


def id_zwartych(wydzial, rok):
    return Wydawnictwo_Zwarte_Autor.objects.filter(
        jednostka__wydzial=wydzial,
        rekord__rok=rok).only("rekord_id").values_list("rekord_id", flat=True).distinct()


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
def eksport_pbn(user_id, wydzial_id, rok):
    user = BppUser.objects.get(pk=user_id)
    wydzial = Wydzial.objects.get(pk=wydzial_id)

    def informuj(msg, dont_persist=True):
        call_command('send_message', user, msg, no_persist=dont_persist)

    def gen_ser():
        for ic in id_ciaglych(wydzial, rok):
            yield Wydawnictwo_Ciagle.objects.get(pk=ic).serializuj_dla_pbn(wydzial)

        informuj(u"... generuję książki i rozdziały dla %s, rok %s" % (wydzial.nazwa, rok))

        for iz in id_zwartych(wydzial, rok):
            yield Wydawnictwo_Zwarte.objects.get(pk=iz).serializuj_dla_pbn(wydzial)

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

    pep = PlikEksportuPBN.objects.create(owner=user, wydzial=wydzial, rok=rok)
    pep.file.save(fn, File(open(fn)))
    pep.save()

    informuj(u"Zakończono. <a href=%s>Kliknij tutaj, aby pobrać eksport PBN dla %s, rok: %s</a>. " %
             (reverse("eksport_pbn:pobierz", args=(pep.pk,)),
              wydzial.nazwa,
              rok),
             dont_persist=False)

    return pep.pk
