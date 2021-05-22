# -*- encoding: utf-8 -*-
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_instytucje,
    integruj_jezyki,
    integruj_kraje,
    integruj_publikacje,
    integruj_uczelnie,
    integruj_wydawcow,
    integruj_zrodla,
    pobierz_instytucje,
    pobierz_konferencje,
    pobierz_ludzi_z_uczelni,
    pobierz_prace_po_doi,
    pobierz_wydawcow,
    pobierz_zrodla,
    synchronizuj_publikacje,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument("--enable-all", action="store_true", default=False)

        parser.add_argument("--enable-system-data", action="store_true", default=False)
        parser.add_argument("--enable-zrodla", action="store_true", default=False)
        parser.add_argument("--enable-people", action="store_true", default=False)
        parser.add_argument("--enable-publishers", action="store_true", default=False)
        parser.add_argument("--enable-conferences", action="store_true", default=False)
        parser.add_argument("--enable-institutions", action="store_true", default=False)
        parser.add_argument("--enable-publications", action="store_true", default=False)
        parser.add_argument("--enable-sync", action="store_true", default=False)

    def handle(
        self,
        app_id,
        app_token,
        base_url,
        user_token,
        enable_all,
        enable_system_data,
        enable_zrodla,
        enable_people,
        enable_publishers,
        enable_conferences,
        enable_institutions,
        enable_publications,
        enable_sync,
        *args,
        **options
    ):
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        if enable_system_data or enable_all:
            integruj_jezyki(client)
            integruj_kraje(client)

        if enable_zrodla or enable_all:
            pobierz_zrodla(client)
            integruj_zrodla()

        if enable_people or enable_all:
            pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
            integruj_autorow_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)

        if enable_publishers or enable_all:
            pobierz_wydawcow(client)
            integruj_wydawcow()

        if enable_conferences or enable_all:
            pobierz_konferencje(client)

        if enable_institutions or enable_all:
            pobierz_instytucje(client)
            integruj_uczelnie()
            integruj_instytucje()

        if enable_publications or enable_all:
            pobierz_prace_po_doi(client)
            integruj_publikacje()

        if enable_sync or enable_all:
            synchronizuj_publikacje(client)
