import django

from import_common.core import matchuj_uczelnie
from pbn_api.importer import importuj_publikacje_instytucji

from bpp.util import pbar

django.setup()

from pbn_api import importer
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_jezyki,
    integruj_kraje,
    integruj_oswiadczenia_z_instytucji,
    integruj_publikacje_instytucji,
    pobierz_instytucje_polon,
    pobierz_konferencje,
    pobierz_ludzi_z_uczelni,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_publikacje_z_instytucji,
    pobierz_wydawcow_mnisw,
    pobierz_zrodla_mnisw,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import (
    Jednostka,
    Uczelnia,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
)


def zrob_skrot(s: str):
    res = ""
    for elem in s:
        if elem.isspace():
            continue

        if not elem.isalnum():
            res += elem
            continue

        if elem.isupper():
            res += elem

    return res


class Command(PBNBaseCommand):
    def send_progress(self, msg):
        print(msg)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("--disable-initial", action="store_true", default=False),
        parser.add_argument("--disable-zrodla", action="store_true", default=False),
        parser.add_argument(
            "--disable-konferencje", action="store_true", default=False
        ),
        parser.add_argument("--disable-wydawcy", action="store_true", default=False),
        parser.add_argument("--disable-autorzy", action="store_true", default=False),
        parser.add_argument("--disable-publikacje", action="store_true", default=False),
        parser.add_argument("--disable-oplaty", action="store_true", default=False),
        parser.add_argument("--wydzial-domyslny", default="Wydział Domyślny"),
        parser.add_argument("--wydzial-domyslny-skrot", default=None),
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
        disable_konferencje,
        disable_publikacje,
        disable_oplaty,
        disable_oswiadczenia,
        wydzial_domyslny,
        wydzial_domyslny_skrot,
        *args,
        **kw,
    ):
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                uczelnia.pbn_integracja = True
                uczelnia.save(update_fields=["pbn_integracja"])
                # raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        if not disable_initial:
            integruj_jezyki(client, create_if_not_exists=True)
            integruj_kraje(client)
            client.download_disciplines()
            client.sync_disciplines()

            # Na pustej bazie nie ma instytucji, stąd trzeba pobrać i ustawić dla obiektu Uczelnia
            pobierz_instytucje_polon(client)

            # Dopasuj uczelnie po nazwie
            if uczelnia.pbn_uid_id is None:
                res = matchuj_uczelnie(uczelnia.nazwa)

                if res is None:
                    raise NotImplementedError(
                        "Teraz musisz uruchomic serwer, zalogowac sie do admina i wybrac PBN UID dla uczelni. Bez "
                        "możliwości automatycznego dopasowania wpisu dla uczelni"
                    )
                uczelnia.pbn_uid = res
                uczelnia.save()

        if not disable_zrodla:
            pobierz_zrodla_mnisw(client)
            importer.importuj_zrodla()

        if not disable_wydawcy:
            pobierz_wydawcow_mnisw(client)
            importer.importuj_wydawcow()

        if not disable_konferencje:
            pobierz_konferencje(client)

        if not disable_autorzy:
            pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
            integruj_autorow_z_uczelni(
                client, Uczelnia.objects.default.pbn_uid_id, import_unexistent=True
            )

        if not disable_publikacje:
            pobierz_publikacje_z_instytucji(client)
            pobierz_oswiadczenia_z_instytucji(client)

            wydzial = Wydzial.objects.get_or_create(
                nazwa=wydzial_domyslny,
                skrot=wydzial_domyslny_skrot or zrob_skrot(wydzial_domyslny),
                uczelnia=Uczelnia.objects.default,
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
            integruj_oswiadczenia_z_instytucji()

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
