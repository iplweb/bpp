import django

from pbn_api.importer import importuj_publikacje_instytucji
from pbn_api.models import OswiadczenieInstytucji

from bpp.util import pbar

django.setup()

from pbn_api import importer
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_jezyki,
    integruj_kraje,
    integruj_publikacje_instytucji,
    pobierz_instytucje_polon,
    pobierz_ludzi_z_uczelni,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_publikacje_z_instytucji,
    pobierz_wydawcow_mnisw,
    pobierz_zrodla_mnisw,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import (
    Autor_Dyscyplina,
    Jednostka,
    Uczelnia,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydzial,
)


class Command(PBNBaseCommand):
    def send_progress(self, msg):
        print(msg)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("--disable-initial", action="store_true", default=False),
        parser.add_argument("--disable-zrodla", action="store_true", default=False),
        parser.add_argument("--disable-wydawcy", action="store_true", default=False),
        parser.add_argument("--disable-autorzy", action="store_true", default=False),
        parser.add_argument("--disable-publikacje", action="store_true", default=False),
        parser.add_argument("--disable-oplaty", action="store_true", default=False),
        parser.add_argument(
            "--disable-oswiadczenia", action="store_true", default=False
        ),

    def handle(
        self,
        app_id,
        app_token,
        base_url,
        user_token,
        disable_initial,
        disable_zrodla,
        disable_wydawcy,
        disable_autorzy,
        disable_publikacje,
        disable_oplaty,
        disable_oswiadczenia,
        *args,
        **kw,
    ):
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        if not disable_initial:
            integruj_jezyki(client, create_if_not_exists=True)
            integruj_kraje(client)
            client.download_disciplines()
            client.sync_disciplines()

            # Na pustej bazie nie ma instytucji, stąd trzeba pobrać i ustawić dla obiektu Uczelnia
            pobierz_instytucje_polon(client)

        if not disable_zrodla:
            pobierz_zrodla_mnisw(client)
            importer.importuj_zrodla()

        if not disable_wydawcy:
            pobierz_wydawcow_mnisw(client)
            importer.importuj_wydawcow()

        if not disable_autorzy:
            pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
            integruj_autorow_z_uczelni(
                client, Uczelnia.objects.default.pbn_uid_id, import_unexistent=True
            )

        if not disable_publikacje:
            pobierz_publikacje_z_instytucji(client)
            pobierz_oswiadczenia_z_instytucji(client)

            wydzial = Wydzial.objects.get_or_create(
                nazwa="Wydział Domyślny", skrot="WD", uczelnia=Uczelnia.objects.default
            )[0]

            jednostka = Jednostka.objects.get_or_create(
                nazwa="Jednostka Domyślna",
                skrot="JD",
                uczelnia=Uczelnia.objects.default,
            )[0]

            if not jednostka.jednostka_wydzial_set.filter(wydzial=wydzial).exists():
                jednostka.jednostka_wydzial_set.create(wydzial=wydzial)

            obca_jednostka = Jednostka.objects.get_or_create(
                nazwa="Obca jednostka",
                skrot="O",
                uczelnia=Uczelnia.objects.default,
                skupia_pracownikow=False,
            )[0]

            if not obca_jednostka.jednostka_wydzial_set.filter(
                wydzial=wydzial
            ).exists():
                obca_jednostka.jednostka_wydzial_set.create(wydzial=wydzial)

            u = Uczelnia.objects.default
            u.obca_jednostka = obca_jednostka
            u.save()

            Wersja_Tekstu_OpenAccess.objects.get_or_create(nazwa="Inna", skrot="OTHER")

            importuj_publikacje_instytucji(client=client, default_jednostka=jednostka)
            integruj_publikacje_instytucji(disable_multiprocessing=True)

        if not disable_oswiadczenia:
            for oswiadczenie in OswiadczenieInstytucji.objects.all():
                bpp_pub = oswiadczenie.get_bpp_publication()
                if bpp_pub is None:
                    print(
                        f"Brak odpowiednika publikacji po stronie BPP dla pracy w PBN {oswiadczenie.publicationId}, "
                        f"moze zaimportuj baze raz jeszcze"
                    )
                    continue
                bpp_aut = oswiadczenie.get_bpp_autor()
                bpp_dyscyplina = oswiadczenie.get_bpp_discipline()

                try:
                    rekord_aut = bpp_pub.autorzy_set.get(autor=bpp_aut)
                except (
                    Wydawnictwo_Zwarte_Autor.DoesNotExist,
                    Wydawnictwo_Ciagle_Autor.DoesNotExist,
                ):
                    print(
                        f"brak autora {bpp_aut=} w pracy {bpp_pub=}, a w PBN jest... moze zaimportuj dane raz jeszcze"
                    )
                    continue

                if (
                    rekord_aut.dyscyplina_naukowa is not None
                    and rekord_aut.dyscyplina_naukowa != bpp_dyscyplina
                ):
                    raise NotImplementedError(
                        f"dyscyplina juz jest w bazie i sie rozni {bpp_pub}"
                    )

                rekord_aut.dyscyplina_naukowa = bpp_dyscyplina

                if bpp_dyscyplina is not None:
                    # Spróbujmy zwrotnie przypisać autorowi dyscyplinę za dany rok:
                    try:
                        ad = bpp_aut.autor_dyscyplina_set.get(rok=bpp_pub.rok)
                    except Autor_Dyscyplina.DoesNotExist:
                        # Nie ma przypisania za dany rok -- tworzomy nowy wpis
                        bpp_aut.autor_dyscyplina_set.create(
                            rok=bpp_pub.rok, dyscyplina_naukowa=bpp_dyscyplina
                        )
                    else:
                        # JEst przypisanie. Czy występuje w nim dyscuyplina?
                        if (
                            ad.dyscyplina_naukowa == bpp_dyscyplina
                            or ad.subdyscyplina_naukowa == bpp_dyscyplina
                        ):
                            # Tak, występuje, zostawiamy.
                            pass
                        elif (
                            ad.dyscyplina_naukowa != bpp_dyscyplina
                            and ad.subdyscyplina_naukowa is None
                        ):
                            # Nie, nie wystepuję, ale można wpisać do pustej sub-dyscypliny
                            ad.subdyscyplina_naukowa = bpp_dyscyplina
                            ad.save()
                        else:
                            # Nie, nie występuje i nie można wpisać
                            raise NotImplementedError(
                                f"Autor miałby mieć 3 przypisania dyscyplin za {bpp_pub.rok}, sprawdź kod"
                            )

                rekord_aut.save()

                # Przelicz punktację
                bpp_pub.save()

        if not disable_oplaty:
            for klass in Wydawnictwo_Ciagle, Wydawnictwo_Zwarte:
                for rekord in pbar(klass.objects.exclude(pbn_uid_id=None)):
                    res = client.get_publication_fee(rekord.pbn_uid_id)
                    if res is not None:
                        rekord.opl_pub_cost_free = res["fee"]["costFreePublication"]
                        rekord.opl_pub_research_potential = res["fee"][
                            "researchPotentialFinancialResources"
                        ]
                        rekord.opl_pub_research_or_development_projects = res["fee"][
                            "researchOrDevelopmentProjectsFinancialResources"
                        ]
                        rekord.opl_pub_other = res["fee"]["other"]
                        rekord.opl_pub_amount = res["fee"]["amount"]

                        rekord.save(
                            update_fields=[
                                "opl_pub_cost_free",
                                "opl_pub_research_potential",
                                "opl_pub_research_or_development_projects",
                                "opl_pub_other",
                                "opl_pub_amount",
                            ]
                        )
