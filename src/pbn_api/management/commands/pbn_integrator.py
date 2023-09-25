import sys

import django
from django.core.management import call_command

from pbn_api.integrator.odswiez_tabele_publikacji import odswiez_tabele_publikacji
from pbn_api.integrator.pobierz_skasowane_prace import pobierz_skasowane_prace

django.setup()


from pbn_api import integrator
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_instytucje,
    integruj_jezyki,
    integruj_kraje,
    integruj_oswiadczenia_z_instytucji,
    integruj_publikacje_instytucji,
    integruj_uczelnie,
    integruj_wszystkich_niezintegrowanych_autorow,
    integruj_wydawcow,
    integruj_zrodla,
    pobierz_instytucje,
    pobierz_konferencje,
    pobierz_ludzi_z_uczelni,
    pobierz_oswiadczenia_z_instytucji,
    pobierz_prace_po_doi,
    pobierz_prace_po_isbn,
    pobierz_publikacje_z_instytucji,
    pobierz_rekordy_publikacji_instytucji,
    pobierz_wydawcow_mnisw,
    pobierz_wydawcow_wszystkich,
    pobierz_zrodla,
    sprawdz_ilosc_autorow_przy_zmatchowaniu,
    synchronizuj_publikacje,
    usun_wszystkie_oswiadczenia,
    usun_zerowe_oswiadczenia,
    weryfikuj_orcidy,
    wyswietl_niezmatchowane_ze_zblizonymi_tytulami,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


def check_end_before(stage, end_before_stage):
    if end_before_stage == stage:
        sys.exit(0)


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--disable-multiprocessing", action="store_true", default=False
        ),

        parser.add_argument("--start-from-stage", type=int, default=0)
        parser.add_argument("--end-before-stage", type=int, default=None)
        parser.add_argument("--just-one-stage", action="store_true"),

        parser.add_argument("--clear-all", action="store_true", default=False)
        parser.add_argument("--clear-publications", action="store_true", default=False)
        parser.add_argument(
            "--clear-match-publications", action="store_true", default=False
        )
        parser.add_argument("--enable-all", action="store_true", default=False)
        parser.add_argument("--enable-delete-all", action="store_true", default=False)
        parser.add_argument("--enable-delete-zeros", action="store_true", default=False)

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
            "--enable-pobierz-po-isbn", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-pobierz-wszystkie-publikacje", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-pobierz-publikacje-instytucji", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-pobierz-rekordy-publikacji-instytucji",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--enable-pobierz-oswiadczenia-instytucji",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--enable-odswiez-tabele-publikacji",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--enable-integruj-wszystkie-publikacje", action="store_true", default=False
        )
        parser.add_argument(
            "--enable-integruj-publikacje-instytucji",
            action="store_true",
            default=False,
        )
        parser.add_argument("--skip-pages", type=int, default=0)
        parser.add_argument("--enable-sync", action="store_true", default=False)
        parser.add_argument("--force-upload", action="store_true", default=False)
        parser.add_argument("--only-bad", action="store_true", default=False)
        parser.add_argument("--only-new", action="store_true", default=False)
        parser.add_argument(
            "--delete-statements-before-upload", action="store_true", default=None
        )
        parser.add_argument(
            "--export-pk-zero",
            action="store_true",
            default=None,
        )
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
        just_one_stage,
        disable_multiprocessing,
        clear_all,
        clear_publications,
        clear_match_publications,
        enable_all,
        enable_delete_all,
        enable_delete_zeros,
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
        enable_pobierz_po_isbn,
        enable_pobierz_wszystkie_publikacje,
        enable_pobierz_publikacje_instytucji,
        enable_pobierz_oswiadczenia_instytucji,
        enable_odswiez_tabele_publikacji,
        enable_pobierz_rekordy_publikacji_instytucji,
        enable_integruj_wszystkie_publikacje,
        enable_integruj_publikacje_instytucji,
        skip_pages,
        enable_sync,
        force_upload,
        only_bad,
        only_new,
        disable_progress_bar,
        delete_statements_before_upload,
        export_pk_zero,
        *args,
        **options
    ):
        if disable_multiprocessing:
            integrator.CPU_COUNT = "single"

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        if clear_all:
            integrator.clear_all()
            sys.exit(0)

        if clear_match_publications:
            integrator.clear_match_publications()
            sys.exit(0)

        if clear_publications:
            integrator.clear_publications()
            sys.exit(0)

        if just_one_stage:
            end_before_stage = start_from_stage + 1

        stage = 0
        if (enable_system_data or enable_all) and start_from_stage <= stage:
            integruj_jezyki(client)
            integruj_kraje(client)
            client.download_disciplines()
            client.sync_disciplines()

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

        # stage = 4
        # check_end_before(stage, end_before_stage)
        # if (enable_download_people_all or enable_all) and start_from_stage <= stage:
        #     os.makedirs("pbn_json_data", exist_ok=True)
        #     pobierz_ludzi_offline(client)
        #
        # stage = 5
        # check_end_before(stage, end_before_stage)
        # if (enable_download_people_all or enable_all) and start_from_stage <= stage:
        #     wgraj_ludzi_z_offline_do_bazy()

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
            call_command("pbn_importuj_wydawcow")
            # zamapuj_wydawcow nie trzeba, bo zostanie wywołany przez pbn_importuj_wydawców gdyby coś
            # call_command("zamapuj_wydawcow")

        stage = 11
        check_end_before(stage, end_before_stage)

        if (enable_conferences or enable_all) and start_from_stage <= stage:
            pobierz_konferencje(client)

        stage = 12
        check_end_before(stage, end_before_stage)

        #
        # Pobieranie wszystkich publikacji z całego PBNu - bez wiekszego sensu
        # do obecnych zastosowań
        #
        # if (
        #     enable_pobierz_wszystkie_publikacje
        # ) and start_from_stage <= stage:
        #     os.makedirs("pbn_json_data", exist_ok=True)
        #     pobierz_prace_offline(client)
        #
        # stage = 13
        # check_end_before(stage, end_before_stage)
        #
        # Wgrywanie wszystkich prac z offline do bazy
        #
        # if (
        #     enable_pobierz_wszystkie_publikacje
        # ) and start_from_stage <= stage:
        #     wgraj_prace_z_offline_do_bazy()
        #

        #
        # Pobieranie oswiadczen i publikacji z insytucji
        #

        if (
            enable_pobierz_rekordy_publikacji_instytucji or enable_all
        ) and start_from_stage <= stage:
            pobierz_rekordy_publikacji_instytucji(client)

        stage = 13
        check_end_before(stage, end_before_stage)
        if (
            enable_pobierz_publikacje_instytucji or enable_all
        ) and start_from_stage <= stage:
            pobierz_publikacje_z_instytucji(client)

        stage = 14
        check_end_before(stage, end_before_stage)

        if (
            enable_pobierz_oswiadczenia_instytucji or enable_all
        ) and start_from_stage <= stage:
            pobierz_oswiadczenia_z_instytucji(client)

        stage = 15

        if (
            enable_odswiez_tabele_publikacji or enable_all
        ) and start_from_stage <= stage:
            pobierz_skasowane_prace(client)

        stage = 16
        check_end_before(stage, end_before_stage)

        if (
            enable_odswiez_tabele_publikacji or enable_all
        ) and start_from_stage <= stage:
            odswiez_tabele_publikacji(client)

        stage = 17
        check_end_before(stage, end_before_stage)

        # if (enable_integruj_wszystkie_publikacje) and start_from_stage <= stage:
        #     integruj_wszystkie_publikacje(
        #         disable_multiprocessing, skip_pages=skip_pages
        #     )

        if (
            enable_integruj_publikacje_instytucji or enable_all
        ) and start_from_stage <= stage:
            integruj_publikacje_instytucji(
                disable_multiprocessing, skip_pages=skip_pages
            )

        stage = 18
        check_end_before(stage, end_before_stage)

        if (
            enable_pobierz_oswiadczenia_instytucji or enable_all
        ) and start_from_stage <= stage:
            integruj_oswiadczenia_z_instytucji()

        stage = 19
        check_end_before(stage, end_before_stage)

        if (enable_pobierz_po_doi or enable_all) and start_from_stage <= stage:
            pobierz_prace_po_doi(client)

        stage = 20
        check_end_before(stage, end_before_stage)

        if (enable_pobierz_po_isbn or enable_all) and start_from_stage <= stage:
            pobierz_prace_po_isbn(client)

        stage = 21
        check_end_before(stage, end_before_stage)

        if (
            enable_integruj_wszystkie_publikacje or enable_all
        ) and start_from_stage <= stage:
            wyswietl_niezmatchowane_ze_zblizonymi_tytulami()
            sprawdz_ilosc_autorow_przy_zmatchowaniu()

        stage = 22
        check_end_before(stage, end_before_stage)

        if enable_delete_all:
            usun_wszystkie_oswiadczenia(client)

        if enable_delete_zeros:
            usun_zerowe_oswiadczenia(client)

        if enable_sync:
            uczelnia = Uczelnia.objects.get_default()

            if export_pk_zero is None:
                export_pk_zero = not uczelnia.pbn_api_nie_wysylaj_prac_bez_pk

            if delete_statements_before_upload is None:
                delete_statements_before_upload = uczelnia.pbn_api_kasuj_przed_wysylka

            synchronizuj_publikacje(
                client=client,
                force_upload=force_upload,
                only_bad=only_bad,
                only_new=only_new,
                delete_statements_before_upload=delete_statements_before_upload,
                export_pk_zero=export_pk_zero,
            )
