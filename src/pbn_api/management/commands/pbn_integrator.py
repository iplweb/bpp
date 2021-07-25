# -*- encoding: utf-8 -*-
import multiprocessing
import os
import sys

multiprocessing.set_start_method("fork")

import django

django.setup()


from pbn_api import integrator
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
    pobierz_ludzi_offline,
    pobierz_ludzi_z_uczelni,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_prace_offline,
    pobierz_prace_po_doi,
    pobierz_publikacje_z_instytucji,
    pobierz_wydawcow_mnisw,
    pobierz_wydawcow_wszystkich,
    pobierz_zrodla,
    synchronizuj_publikacje,
    weryfikuj_orcidy,
    wgraj_ludzi_z_offline_do_bazy,
    wgraj_prace_z_offline_do_bazy,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


def check_end_before(stage, end_before_stage):
    if end_before_stage == stage:
        sys.exit(0)


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument("--start-from-stage", type=int, default=0)
        parser.add_argument("--end-before-stage", type=int, default=None)

        parser.add_argument("--clear-all", action="store_true", default=False)
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
            "--enable-pobierz-publikacje-instytucji", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-pobierz-oswiadczenia-instytucji",
            action="store_true",
            default=False,
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
        start_from_stage,
        end_before_stage,
        clear_all,
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
        enable_pobierz_publikacje_instytucji,
        enable_pobierz_oswiadczenia_instytucji,
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

        if clear_all:
            integrator.clear_all()
            sys.exit(0)

        stage = 0
        if (enable_system_data or enable_all) and start_from_stage <= stage:
            integruj_jezyki(client)
            integruj_kraje(client)

        stage = 1
        check_end_before(stage, end_before_stage)
        if (enable_pobierz_zrodla or enable_all) and start_from_stage <= stage:
            pobierz_zrodla(client)

        stage = 2
        check_end_before(stage, end_before_stage)
        if (enable_integruj_zrodla or enable_all) and start_from_stage <= stage:
            integruj_zrodla(disable_progress_bar)

        stage = 3
        check_end_before(stage, end_before_stage)
        if (enable_institutions or enable_all) and start_from_stage <= stage:
            # Pobieranie instytucji musi odbywac się przed pobieraniem ludzi
            pobierz_instytucje(client)
            integruj_uczelnie()
            integruj_instytucje()

        stage = 4
        check_end_before(stage, end_before_stage)
        if (enable_download_people_all or enable_all) and start_from_stage <= stage:
            os.makedirs("pbn_json_data", exist_ok=True)
            pobierz_ludzi_offline(client)

        stage = 5
        check_end_before(stage, end_before_stage)
        if (enable_download_people_all or enable_all) and start_from_stage <= stage:
            wgraj_ludzi_z_offline_do_bazy()

        stage = 6
        check_end_before(stage, end_before_stage)

        if (
            enable_download_people_institution or enable_all
        ) and start_from_stage <= stage:
            pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
        stage = 7
        check_end_before(stage, end_before_stage)

        if (
            enable_integrate_people_institution or enable_all
        ) and start_from_stage <= stage:
            integruj_autorow_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
        stage = 8

        if (enable_integrate_people_all or enable_all) and start_from_stage <= stage:
            integruj_wszystkich_niezintegrowanych_autorow()
        stage = 9

        if (enable_check_orcid_people or enable_all) and start_from_stage <= stage:
            weryfikuj_orcidy(client, Uczelnia.objects.default.pbn_uid_id)
        stage = 10
        check_end_before(stage, end_before_stage)

        if (enable_publishers or enable_all) and start_from_stage <= stage:
            pobierz_wydawcow_wszystkich(client)
            pobierz_wydawcow_mnisw(client)
            integruj_wydawcow()
        stage = 11
        check_end_before(stage, end_before_stage)

        if (enable_conferences or enable_all) and start_from_stage <= stage:
            pobierz_konferencje(client)
        stage = 12

        # Pobieranie publikacji
        if (
            enable_pobierz_wszystkie_publikacje or enable_all
        ) and start_from_stage <= stage:
            os.makedirs("pbn_json_data", exist_ok=True)
            pobierz_prace_offline(client)
        stage = 13

        if (
            enable_pobierz_wszystkie_publikacje or enable_all
        ) and start_from_stage <= stage:
            wgraj_prace_z_offline_do_bazy()
        stage = 14

        if (
            enable_pobierz_publikacje_instytucji or enable_all
        ) and start_from_stage <= stage:
            pobierz_publikacje_z_instytucji(client)
        stage = 15

        if (
            enable_pobierz_oswiadczenia_instytucji or enable_all
        ) and start_from_stage <= stage:
            pobierz_oswiadczenia_z_instytucji(client)
        stage = 16

        if (enable_integruj_publikacje or enable_all) and start_from_stage <= stage:
            integruj_publikacje()
        stage = 17

        if (enable_pobierz_po_doi or enable_all) and start_from_stage <= stage:
            pobierz_prace_po_doi(client)

        if enable_sync:  # or enable_all:
            synchronizuj_publikacje(client)
