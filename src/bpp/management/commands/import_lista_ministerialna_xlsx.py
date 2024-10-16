import logging
from pathlib import Path

import numpy
import pandas
import requests
from django.core.management import BaseCommand
from django.db import transaction

from import_common.core import matchuj_zrodlo

from bpp.models import Dyscyplina_Naukowa

logger = logging.getLogger("console.always")


class Command(BaseCommand):
    help = "Importuje Listę Ministerialną w formacie XLSX do systemu"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="https://www.gov.pl/attachment/7f0051cc-9ff4-4ef1-9b69-a5dc0ead1927",
            help="Adres URL pliku XLSX",
        )
        parser.add_argument(
            "--fn",
            default="lista-ministerialna-2023.xlsx",
            help="nazwa pliku do zapisu listy/analizy",
        )
        parser.add_argument("--rok", default=2023, type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--download", action="store_true")
        parser.add_argument("--force-download", action="store_true")

    @transaction.atomic
    def handle(self, url, fn, rok, dry_run, download, force_download, *args, **options):
        # Usuń zbędne spacje z systemowego słownika dyscyplin BPP,
        # napraw literówki

        for elem in Dyscyplina_Naukowa.objects.all():
            nowa_nazwa = elem.nazwa.strip()
            if nowa_nazwa == "językoznastwo":
                nowa_nazwa = "językoznawstwo"
            if nowa_nazwa == "literaturoznastwo":
                nowa_nazwa = "literaturoznawstwo"
            if elem.nazwa != nowa_nazwa:
                elem.nazwa = nowa_nazwa
                elem.save(update_fields=["nazwa"])

        # Pobierz plik z listą z URLa

        if not Path(fn).exists() or force_download:
            if download or force_download:
                print("Downloading", fn)
                response = requests.get(url)
                open(fn, "wb").write(response.content)
                print("done")
            else:
                raise ValueError(
                    f"Brak pliku {fn}. Podaj parametr --download aby pobrac"
                )

        data = pandas.read_excel(fn, header=1).replace({numpy.nan: None})

        # Problem polega na tym, że numerki w XLSie to nie sa kody dyscyplin. Oczko wyżej są ich
        # nazwy, które zakładam, że są prawidłowe; moglibyśmy wczytać tylko jeden plik ale wówczas
        # musielibysmy skorzystac z multi-indexu. Zatem wczytamy dwa wiersze pliku XLS jeszcze
        # raz i użyjemy ich zeby pozamieniac nazwy z pojedynczego indeksu dataframe'u data

        labels = pandas.read_excel(fn, header=[0, 1], nrows=0)

        # labels.axes[1] zawiera pary tytułów kolumn.
        for nazwa, zly_kod in labels.axes[1][9:]:
            data = data.rename({zly_kod: nazwa}, axis=1, errors="raise")

        try:
            data = data.rename(
                {
                    "stosunki międzynaropdowe": "stosunki międzynarodowe",
                },
                axis=1,
                errors="raise",
            )
        except KeyError:
            pass

        data = data.to_dict("record")

        # Dane z XLSa będą miały klucze z nazwami dyscyplin czyli np { 'archeologia': 'x' }

        for elem in data:
            tytul_zrodla = elem["Tytuł 1"] or elem["Tytuł 2"]
            zrodlo = matchuj_zrodlo(
                tytul_zrodla,
                # alt_nazwa=elem["Tytuł 2"],
                issn=elem["issn"] or elem["issn.1"],
                e_issn=elem["e-issn"] or elem["e-issn.1"],
                disable_fuzzy=True,
                disable_skrot=True,
            )
            if zrodlo is None:
                logger.info(f"{tytul_zrodla}; PKT-5; brak dopasowania w BPP")
                continue

            try:
                punktacja = elem["Punkty"]
            except KeyError:
                punktacja = elem["Punktacja"]

            # Jest źródło.
            # Sprawdźmy, czy ma punkty za 2023:
            if zrodlo.punktacja_zrodla_set.filter(rok=rok).exists():
                # Istnieje, sprawdźmy, czy różna:
                pz = zrodlo.punktacja_zrodla_set.get(rok=rok)
                if pz.punkty_kbn != punktacja:
                    logger.info(
                        f"{zrodlo.nazwa}; PKT-0; różna punktacja; {rok};  "
                        f"BPP {pz.punkty_kbn}; "
                        f"XLS {punktacja}; Ustawiam na XLS."
                    )
                    pz.punkty_kbn = punktacja
                    pz.save(update_fields=["punkty_kbn"])
            else:
                logger.info(
                    f"{zrodlo.nazwa}; PKT-4; ustawiam; {punktacja}; "
                    f"za rok {rok}; (w XLS: {elem['Tytuł 1']}) "
                )
                zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=punktacja)

            # Aktualne dyscypliny:
            aktualne_dyscypliny_zrodla = {
                x.dyscyplina.nazwa for x in zrodlo.dyscyplina_zrodla_set.filter(rok=rok)
            }

            # Ustawmy mu wszystkie dyscypliny wg pliku XLS.

            # W tym celu: kasujemy dyscypliny z danego roku
            zrodlo.dyscyplina_zrodla_set.filter(rok=rok).delete()

            for nazwa_dyscypliny in list(elem.keys())[9:]:
                if elem[nazwa_dyscypliny] == "x":
                    try:
                        dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(
                            nazwa=nazwa_dyscypliny
                        )
                    except Dyscyplina_Naukowa.DoesNotExist:
                        raise ValueError(
                            f"ERROR: brak dyscypliny naukowej '{nazwa_dyscypliny}' w systemie"
                        )

                    zrodlo.dyscyplina_zrodla_set.create(
                        dyscyplina=dyscyplina_naukowa, rok=rok
                    )

            # Nowe dyscypliny:
            nowe_dyscypliny_zrodla = {
                x.dyscyplina.nazwa for x in zrodlo.dyscyplina_zrodla_set.filter(rok=rok)
            }

            # Roznica:
            dodane = nowe_dyscypliny_zrodla.difference(aktualne_dyscypliny_zrodla)
            usuniete = aktualne_dyscypliny_zrodla.difference(nowe_dyscypliny_zrodla)

            if dodane:
                logger.info(
                    f"{zrodlo.nazwa}; PKT-1; +++   DODANE; {rok}; {sorted(dodane)}"
                )

            if usuniete:
                logger.info(
                    f"{zrodlo.nazwa}; PKT-2; --- USUNIETE; {rok}; {sorted(usuniete)}"
                )

        if dry_run:
            transaction.rollback()
