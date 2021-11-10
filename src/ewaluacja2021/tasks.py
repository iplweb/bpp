import os
import shutil
from os.path import basename
from tempfile import mkdtemp

import celery
from django.core.files import File
from django.core.management import call_command

from ewaluacja2021.models import ZamowienieNaRaport
from ewaluacja2021.util import string2fn


@celery.task
def generuj_algorytm(pk, *args, **kw):
    zamowienie = ZamowienieNaRaport.objects.get(pk=pk)
    zamowienie.uid_zadania = generuj_algorytm.request.id
    zamowienie.save()

    outdir = mkdtemp()

    call_command(
        f"raport_3n_{zamowienie.rodzaj}",
        dyscyplina=zamowienie.dyscyplina_naukowa.nazwa,
        output_path=outdir,
    )

    json_file = os.path.join(
        outdir,
        f"{zamowienie.rodzaj}_{string2fn(zamowienie.dyscyplina_naukowa.nazwa)}.json",
    )

    call_command("raport_3n_to_xlsx", json_file)

    xls_output_dir = json_file.replace(".json", "_output")
    zip_path = os.path.join(outdir, "results.zip")

    cwd = os.getcwd()
    os.chdir(outdir)
    os.system(f'zip -r "{zip_path}" "{os.path.basename(xls_output_dir)}/"')
    os.chdir(cwd)

    zamowienie.plik_wyjsciowy.save(
        basename(xls_output_dir) + ".zip", content=File(open(zip_path, "rb"))
    )

    fitness_png = os.path.join(outdir, "fitness.png")

    if os.path.exists(fitness_png):
        zamowienie.wykres_wyjsciowy.save(
            basename(xls_output_dir), content=File(open(fitness_png, "rb"))
        )

    zamowienie.save()

    print("Przetwarzanie zakonczone")

    shutil.rmtree(outdir)
