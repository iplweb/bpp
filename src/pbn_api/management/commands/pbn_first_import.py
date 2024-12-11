import django

from pbn_api.importer import importuj_publikacje_instytucji

django.setup()

from pbn_api import importer
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_jezyki,
    integruj_kraje,
    pobierz_instytucje_polon,
    pobierz_ludzi_z_uczelni,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_publikacje_z_instytucji,
    pobierz_wydawcow_mnisw,
    pobierz_zrodla_mnisw,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Jednostka, Uczelnia, Wersja_Tekstu_OpenAccess, Wydzial


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
        *args,
        **kw
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
            if False:
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
            # integruj_publikacje_instytucji(disable_multiprocessing=True)
