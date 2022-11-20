import logging

import openpyxl
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jednostka,
    Jednostka_Wydzial,
    Jezyk,
    Rodzaj_Zrodla,
    Status_Korekty,
    Typ_KBN,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
    Zrodlo,
)

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Importuje dane w formacie XLSX z SGSP"

    def add_arguments(self, parser):
        parser.add_argument("plik")

    @transaction.atomic
    def handle(
        self,
        plik,
        verbosity,
        *args,
        **options,
    ):
        logger.setLevel(logging.WARNING)
        if verbosity > 1:
            logger.setLevel(logging.INFO)

        uczelnia = Uczelnia.objects.get_or_create(
            nazwa="Szkoła Główna Służby Pożarniczej",
            skrot="SGSP",
            nazwa_dopelniacz_field="Szkoły Głównej Służby Pożarniczej",
        )[0]

        inz = Dyscyplina_Naukowa.objects.get(nazwa__istartswith="inżynieria środowiska")
        nauki_o_bezp = Dyscyplina_Naukowa.objects.get_or_create(
            nazwa="nauki o bezpieczeństwie", kod="5.3"
        )[0]

        wydzial = Wydzial.objects.get_or_create(
            nazwa="Wydział Inżynierii Bezpieczeństwa i Ochrony Ludności",
            skrot="WIBiOL",
            uczelnia=uczelnia,
        )[0]

        wb: openpyxl.workbook.workbook.Workbook = openpyxl.load_workbook(plik)
        ws = wb.worksheets[0]

        def get_data():

            header = None
            for row in ws.rows:
                if header is None:
                    header = [x.value.strip().lower() for x in row]
                    continue

                def strip(s):
                    if isinstance(s, str):
                        return s.strip()
                    return s

                values = [strip(x.value) for x in row]
                yield dict(zip(header, values))

        for row in get_data():
            if row["nname"].find(" ") < 0 and row["oname"].find(" ") < 0:
                autor = None

            else:
                nazwisko, imiona = (row["nname"] or row["oname"]).split(" ", 1)
                orcid = row["orcid"].strip() or None
                id_autora = row["id_autora"]
                if row["oname"]:
                    # Autorzy obcy mają jak gdyby zdublowane numery ID... ?
                    id_autora = id_autora + 1000000

                autor = Autor.objects.get_or_create(
                    pk=id_autora,
                    orcid=orcid,
                    defaults={"nazwisko": nazwisko, "imiona": imiona},
                )[0]

            # PBNID nie wiem co to

            punkty_kbn = row["xpkt"] or 0
            if isinstance(punkty_kbn, str):
                punkty_kbn = punkty_kbn.strip()
                if not punkty_kbn:
                    punkty_kbn = 0

            if row["kind"] == "artykuł":

                zrodlo = Zrodlo.objects.get_or_create(
                    nazwa=row["journal"],
                    skrot=row["journal"],
                    rodzaj=Rodzaj_Zrodla.objects.get(pk=1),
                )[0]

                rekord = Wydawnictwo_Ciagle.objects.get_or_create(
                    pk=row["id_artykulu"],
                    defaults=dict(
                        tytul_oryginalny=row["full_tytul"],
                        rok=row["rok_publikacji"],
                        jezyk=Jezyk.objects.get(skrot="pol."),
                        doi=row["doi"],
                        punkty_kbn=punkty_kbn,
                        zrodlo=zrodlo,
                        charakter_formalny=Charakter_Formalny.objects.get(skrot="AC"),
                        status_korekty=Status_Korekty.objects.get(nazwa="po korekcie"),
                        typ_kbn=Typ_KBN.objects.get(skrot="000"),
                    ),
                )[0]

            elif row["kind"] == "książka":
                rekord = Wydawnictwo_Zwarte.objects.get_or_create(
                    pk=row["id_artykulu"],
                    defaults=dict(
                        tytul_oryginalny=row["full_tytul"],
                        rok=row["rok_publikacji"],
                        jezyk=Jezyk.objects.get(skrot="pol."),
                        doi=row["doi"],
                        punkty_kbn=punkty_kbn,
                        charakter_formalny=Charakter_Formalny.objects.get(skrot="KS"),
                        status_korekty=Status_Korekty.objects.get(nazwa="po korekcie"),
                        typ_kbn=Typ_KBN.objects.get(skrot="000"),
                    ),
                )[0]

            elif row["kind"] == "rozdział":
                rekord = Wydawnictwo_Zwarte.objects.get_or_create(
                    pk=row["id_artykulu"],
                    defaults=dict(
                        tytul_oryginalny=row["full_tytul"],
                        rok=row["rok_publikacji"],
                        jezyk=Jezyk.objects.get(skrot="pol."),
                        doi=row["doi"],
                        punkty_kbn=punkty_kbn,
                        charakter_formalny=Charakter_Formalny.objects.get(skrot="ROZ"),
                        status_korekty=Status_Korekty.objects.get(nazwa="po korekcie"),
                        typ_kbn=Typ_KBN.objects.get(skrot="000"),
                    ),
                )[0]

            else:
                raise NotImplementedError(f"Brak obsługi kind={row['kind']}")

            if row["obcy"] != 1:
                if not row["afiliacja"].strip():
                    # Pusta afiliacja -- czyli autor "swój" ale afiliacja obca
                    jednostka = Jednostka.objects.get_or_create(
                        nazwa="Obca jednostka",
                        skrot="Obca jednostka",
                        uczelnia=uczelnia,
                        skupia_pracownikow=False,
                    )[0]
                    afiliuje = False
                else:
                    jednostka = Jednostka.objects.get_or_create(
                        nazwa=row["afiliacja"].strip(),
                        skrot=row["afiliacja"].strip(),
                        uczelnia=uczelnia,
                    )[0]
                    afiliuje = True
            else:
                jednostka = Jednostka.objects.get_or_create(
                    nazwa="Obca jednostka",
                    skrot="Obca jednostka",
                    uczelnia=uczelnia,
                    skupia_pracownikow=False,
                )[0]
                afiliuje = False

            Jednostka_Wydzial.objects.get_or_create(
                jednostka=jednostka, wydzial=wydzial
            )

            if row["jest_redaktorem"] == 0:
                typ_odpowiedzialnosci_skrot = "aut."
            else:
                typ_odpowiedzialnosci_skrot = "red."

            if autor is not None:

                dyscyplina_naukowa = None

                if afiliuje:

                    if row["inz_srod"].strip() or row["nauki_o_bezp"].strip():
                        #
                        # Dyscyplina
                        #

                        if row["inz_srod"] == "inz":
                            dyscyplina_naukowa = inz

                        elif row["nauki_o_bezp"] == "nauki":
                            dyscyplina_naukowa = nauki_o_bezp

                        try:
                            ad = Autor_Dyscyplina.objects.get(
                                rok=row["rok_publikacji"], autor=autor
                            )
                        except Autor_Dyscyplina.DoesNotExist:
                            ad = None

                        if ad:
                            if (
                                ad.dyscyplina_naukowa == dyscyplina_naukowa
                                or ad.subdyscyplina_naukowa == dyscyplina_naukowa
                            ):
                                pass
                            else:
                                raise NotImplementedError("Autor dwudyscyplinowy...")

                        ad = Autor_Dyscyplina.objects.get_or_create(
                            rok=row["rok_publikacji"],
                            autor=autor,
                            dyscyplina_naukowa=dyscyplina_naukowa,
                        )[0]

                rekord.dodaj_autora(
                    autor=autor,
                    jednostka=jednostka,
                    zapisany_jako=row["nname"] or row["oname"],
                    typ_odpowiedzialnosci_skrot=typ_odpowiedzialnosci_skrot,
                    kolejnosc=row["kolejnosc"],
                    afiliuje=afiliuje,
                    dyscyplina_naukowa=dyscyplina_naukowa,
                )

            # Uwagi do importu:
            # - typ_kbn zawsze INNE
            # - język zawsze POLSKI
            #         "inz_srod", -> boolean? -> przypisuje dyscypline inzynieria
            #         "nauki_o_bezp", -> boolean? -> przypisuje dyscypline nauki_o_bezp

            # dict_keys(
            #     [

            #         "d_kandydat1", -> nie wiem
            #         "d_kandydat2", -> nie wiem
            #         "d_kandydat3", -> nie wiem

            #         "oswiadczenie", -> 2 rekordy mają "0", 5 ma "1" -> nie wiem

            #         "id", -> nie wiem jakie ID
            #         "pbnid", -> nie wiem co to

            #         "modifier", -> zawsze puste
            #         "ostatni_edytor", -> ostatnia osoba poprawiająca
            #         "modified", -> data modyfikacji

            #         "pbnart", -> puste zawsze
            #         "pbnauthor", -> puste zawsze
            #         "dyscyplina", -> zawsze puste
            #     ]
            # )
