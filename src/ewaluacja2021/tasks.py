import os
import shutil
from os.path import basename
from tempfile import mkdtemp

import denorm
from django.core.files import File
from django.core.management import call_command
from django.db.models import Sum

from ewaluacja2021.models import ZamowienieNaRaport
from ewaluacja2021.reports import load_data, rekordy
from ewaluacja2021.util import create_zip_archive, string2fn
from snapshot_odpiec.models import SnapshotOdpiec

from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

from django_bpp import celery_tasks


def suma_odpietych_dyscyplin():
    return (
        Wydawnictwo_Ciagle_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
        + Wydawnictwo_Zwarte_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
        + Patent_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
    )


def suma_przypietych_dyscyplin():
    return (
        Wydawnictwo_Ciagle_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
        + Wydawnictwo_Zwarte_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
        + Patent_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
    )


def suma_pkdaut_json(fn):
    dane = load_data(open(fn))
    rec = rekordy(dane)
    suma_pkdaut = rec.filter(do_ewaluacji=True).aggregate(x=Sum("pkdaut"))
    return suma_pkdaut["x"]


KLASY = Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor, Patent_Autor


def zrob_liste_odpietych():
    ret = {}
    for klass in KLASY:
        ret[klass] = set(
            klass.objects.exclude(dyscyplina_naukowa=None)
            .exclude(przypieta=True)
            .values_list("id", flat=True)
        )
    return ret


def przywroc_przypiecia(odpiete_przed, odpiete_po):
    for klass in KLASY:
        przed = odpiete_przed[klass]
        po = odpiete_po[klass]
        klass.objects.filter(pk__in=po.difference(przed)).update(przypieta=True)


@celery_tasks.app.task
def generuj_algorytm(pk, *args, **kw):
    try:
        zamowienie = ZamowienieNaRaport.objects.get(pk=pk)
    except ZamowienieNaRaport.DoesNotExist:
        return

    zamowienie.uid_zadania = generuj_algorytm.request.id
    zamowienie.status = "Przetwarzanie"
    zamowienie.save()

    odpinaj_dyscypliny = False

    kwargs = {}
    if zamowienie.rodzaj == "plecakowy":
        rodzaj_zamowienia = "plecakowy"
    elif zamowienie.rodzaj == "plecakowy_bez_limitu":
        rodzaj_zamowienia = "plecakowy"
        kwargs["bez_limitu_uczelni"] = True
    elif zamowienie.rodzaj == "genetyczny":
        rodzaj_zamowienia = "genetyczny"
    elif zamowienie.rodzaj == "genetyczny_z_odpinaniem":
        rodzaj_zamowienia = "genetyczny"
        odpinaj_dyscypliny = True
    else:
        raise NotImplementedError(
            f"Nie mam kodu dla rodzaju zamowienia {zamowienie.rodzaj}"
        )

    poprzedni_wynik = 0
    rekordy_odpiete_przed = set()
    rekordy_odpiete_po = set()
    ilosc_nieudanych_odpiec = 0

    def odpal_raport(rodzaj_zamowienia, nazwa_dyscypliny):
        outdir = mkdtemp()

        call_command(
            f"raport_3n_{rodzaj_zamowienia}",
            dyscyplina=nazwa_dyscypliny,
            output_path=outdir,
            **kwargs,
        )

        json_file = os.path.join(
            outdir,
            f"{rodzaj_zamowienia}_{string2fn(nazwa_dyscypliny)}.json",
        )

        suma_pkdaut = suma_pkdaut_json(json_file) or 0

        return json_file, suma_pkdaut, outdir

    while True:

        json_file, suma_pkdaut, outdir = odpal_raport(
            rodzaj_zamowienia=rodzaj_zamowienia,
            nazwa_dyscypliny=zamowienie.dyscyplina_naukowa.nazwa,
        )

        if suma_pkdaut <= poprzedni_wynik:
            # poprzendi wynik był lepszy (lub identyczny), przywracam przypięcia, wychodze z programu
            odpinaj_dyscypliny = False
            przywroc_przypiecia(rekordy_odpiete_przed, rekordy_odpiete_po)
            denorm.flush()
            suma_pkdaut = poprzedni_wynik

        else:
            poprzedni_wynik = suma_pkdaut
            zamowienie.status = "Przetwarzanie! Osiagnieto %s PKD" % suma_pkdaut
            # zamowienie.save()

            call_command("raport_3n_to_xlsx", json_file)

            xls_output_dir = json_file.replace(".json", "_output")
            zip_path = os.path.join(outdir, "results.zip")

            create_zip_archive(output_fn=zip_path, input_dir=xls_output_dir)

            zamowienie.plik_wyjsciowy.save(
                basename(xls_output_dir) + ".zip", content=File(open(zip_path, "rb"))
            )

            fitness_png = os.path.join(outdir, "fitness.png")

            if os.path.exists(fitness_png):
                zamowienie.wykres_wyjsciowy.save(
                    basename(xls_output_dir), content=File(open(fitness_png, "rb"))
                )

            zamowienie.save()

        jeszcze_jedna_petla = False

        if odpinaj_dyscypliny:
            rekordy_odpiete_przed = zrob_liste_odpietych()
            odpiete_przed = suma_odpietych_dyscyplin()

            call_command("odepnij_dyscypliny", json_file)

            rekordy_odpiete_po = zrob_liste_odpietych()
            odpiete_po = suma_odpietych_dyscyplin()

            if odpiete_przed != odpiete_po:
                # Jezeli ilosc punktow przed i po odpieciu sie rozni, to dzialaj dalej
                zamowienie.status = (
                    f"Przetwarzanie! Odpieto kolejne {odpiete_po-odpiete_przed} dyscyplin. Osiagnieto %s PKD"
                    % suma_pkdaut
                )
                zamowienie.save()

            else:
                ilosc_nieudanych_odpiec += 1

            if ilosc_nieudanych_odpiec < 4:
                jeszcze_jedna_petla = True

        if not jeszcze_jedna_petla:
            if zamowienie.rodzaj == "genetyczny_z_odpinaniem":
                print("Wychodze z generowania, robie snapshot odpiec.")

                SnapshotOdpiec.objects.create(
                    owner=None,
                    comment=f"{zamowienie.dyscyplina_naukowa.nazwa}: PKD {suma_pkdaut}",
                )

                if odpinaj_dyscypliny:
                    print("Odpinam ostateczne dyscypliny")
                    call_command("odepnij_dyscypliny", json_file, ostatecznie=True)

                shutil.rmtree(outdir)

                if odpinaj_dyscypliny:
                    print("Przeliczam genetycznie ostateczne dyscypliny")
                    json_file, suma_pkdaut, outdir = odpal_raport(
                        rodzaj_zamowienia, zamowienie.dyscyplina_naukowa.nazwa
                    )
            else:
                shutil.rmtree(outdir)

            break

    zamowienie.status = f"Zakonczono! Osiagnieto {suma_pkdaut}"
    zamowienie.save()
