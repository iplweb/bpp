# -*- encoding: utf-8 -*-
import os
import zipfile
from tempfile import mkdtemp, mkstemp

from django.core.files.base import File
from django.core.management import call_command

from bpp.models import Uczelnia

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from lxml.etree import tostring

from bpp.models.system import Charakter_Formalny
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte
from bpp.util import remove_old_objects
from django_bpp.celery_tasks import app
from django_bpp.util import wait_for_object
from eksport_pbn.models import (
    PlikEksportuPBN,
    DATE_CREATED_ON,
    DATE_UPDATED_ON,
    DATE_UPDATED_ON_PBN,
)
from eksport_pbn.util import id_ciaglych, id_zwartych


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
def eksport_pbn(pk, max_file_size=1024 * 1024):
    obj = wait_for_object(PlikEksportuPBN, pk)

    user = obj.owner
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
        call_command("send_message", user, msg, dont_persist=dont_persist)

    def gen_ser():
        if artykuly:
            for ic in id_ciaglych(
                od_roku,
                do_roku,
                rodzaj_daty=rodzaj_daty,
                od_daty=od_daty,
                do_daty=do_daty,
            ):
                yield Wydawnictwo_Ciagle.objects.get(pk=ic).eksport_pbn_serializuj()

        if ksiazki and rozdzialy:
            informuj(f"... generuję książki i rodziały dla {rokstr}")
        elif rozdzialy:
            informuj(f"... generuję rodziały dla {rokstr}")
        elif ksiazki:
            informuj(f"... generuję książki dla {rokstr}")

        for iz in id_zwartych(
            od_roku,
            do_roku,
            ksiazki,
            rozdzialy,
            rodzaj_daty=rodzaj_daty,
            od_daty=od_daty,
            do_daty=do_daty,
        ):
            yield Wydawnictwo_Zwarte.objects.get(pk=iz).eksport_pbn_serializuj()

    tmpdir = mkdtemp()

    count = 1
    cur_data_size = max_file_size
    outfile = None

    def close_outfile(outfile):
        if outfile is None:
            return
        outfile.write("</works>")
        outfile.close()

    class FakeUczelnia:
        pbn_id = "Ustaw PBN ID dla uczelni w module redagowania"

    hdr = (
        header % (Uczelnia.objects.first() or FakeUczelnia).pbn_id
        or FakeUczelnia.pbn_id
    )

    for element in list(gen_ser()):

        if cur_data_size >= max_file_size - 4096:
            close_outfile(outfile)

            outfile = open(
                os.path.join(tmpdir, "%s.xml" % count), "w", encoding="utf-8"
            )
            outfile.write(hdr)
            cur_data_size = len(hdr)
            count += 1

        data = tostring(element, pretty_print=True, encoding="utf-8")
        outfile.write(data.decode("utf-8"))

        cur_data_size += len(data)

    close_outfile(outfile)

    fno, fn = mkstemp()
    zipf = zipfile.ZipFile(fn, "w")
    zipdir(tmpdir, zipf)
    zipf.close()

    pep = obj
    pep.file.save(os.path.basename(fn), File(open(fn, "rb")))
    pep.save()

    informuj(
        "Zakończono. <a href=%s>Kliknij tutaj, aby pobrać eksport PBN dla %s</a>. "
        % (reverse("eksport_pbn:pobierz", args=(pep.pk,)), rokstr),
        dont_persist=False,
    )

    return pep.pk


@app.task
def remove_old_eksport_pbn_files():
    return remove_old_objects(PlikEksportuPBN)
