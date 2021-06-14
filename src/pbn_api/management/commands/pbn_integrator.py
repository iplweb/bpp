# -*- encoding: utf-8 -*-
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_instytucje,
    integruj_jezyki,
    integruj_kraje,
    integruj_publikacje,
    integruj_uczelnie,
    integruj_wszystkich_niezintegrowanych_autorow,
    integruj_wydawcow,
    integruj_zrodla,
    pobierz_instytucje,
    pobierz_konferencje,
    pobierz_ludzi,
    pobierz_ludzi_z_uczelni,
    pobierz_prace,
    pobierz_prace_po_doi,
    pobierz_wydawcow,
    pobierz_zrodla,
    synchronizuj_publikacje,
    weryfikuj_orcidy,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument("--enable-all", action="store_true", default=False)

        parser.add_argument("--enable-system-data", action="store_true", default=False)
        parser.add_argument(
            "--enable-pobierz-zrodla", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-integruj-zrodla", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-download-people-institution", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-download-people-all", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-integrate-people-institution", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-integrate-people-all", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-check-orcid-people", action="store_true", default=False
        )
        parser.add_argument("--enable-publishers", action="store_true", default=False)
        parser.add_argument("--enable-conferences", action="store_true", default=False)
        parser.add_argument("--enable-institutions", action="store_true", default=False)
        parser.add_argument(
            "--enable-pobierz-po-doi", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-pobierz-wszystkie-publikacje", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-integruj-publikacje", action="store_true", default=False
        )
        parser.add_argument("--enable-sync", action="store_true", default=False)
        parser.add_argument(
            "--disable-progress-bar", action="store_true", default=False
        )

    def handle(
        self,
        app_id,
        app_token,
        base_url,
        user_token,
        enable_all,
        enable_system_data,
        enable_pobierz_zrodla,
        enable_integruj_zrodla,
        enable_download_people_institution,
        enable_download_people_all,
        enable_integrate_people_institution,
        enable_integrate_people_all,
        enable_check_orcid_people,
        enable_publishers,
        enable_conferences,
        enable_institutions,
        enable_pobierz_po_doi,
        enable_pobierz_wszystkie_publikacje,
        enable_integruj_publikacje,
        enable_sync,
        disable_progress_bar,
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

        if enable_pobierz_zrodla or enable_all:
            pobierz_zrodla(client)

        if enable_integruj_zrodla or enable_all:
            integruj_zrodla(disable_progress_bar)

        if enable_download_people_all or enable_all:
            pobierz_ludzi(client)

        if enable_download_people_institution or enable_all:
            pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)

        if enable_integrate_people_institution or enable_all:
            integruj_autorow_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)

        if enable_integrate_people_all or enable_all:
            integruj_wszystkich_niezintegrowanych_autorow()

        if enable_check_orcid_people or enable_all:
            weryfikuj_orcidy(client, Uczelnia.objects.default.pbn_uid_id)

        if enable_publishers or enable_all:
            pobierz_wydawcow(client)
            integruj_wydawcow()

        if enable_conferences or enable_all:
            pobierz_konferencje(client)

        if enable_institutions or enable_all:
            pobierz_instytucje(client)
            integruj_uczelnie()
            integruj_instytucje()

        if enable_pobierz_wszystkie_publikacje or enable_all:
            pobierz_prace(client)

        if enable_pobierz_po_doi:  # or enable_all:
            pobierz_prace_po_doi(client)

        if enable_integruj_publikacje or enable_all:
            integruj_publikacje()

        if enable_sync or enable_all:
            synchronizuj_publikacje(client)
