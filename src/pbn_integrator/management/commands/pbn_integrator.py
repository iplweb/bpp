import sys

import django
from django.core.management import call_command

from pbn_integrator.utils.odswiez_tabele_publikacji import odswiez_tabele_publikacji
from pbn_integrator.utils.pobierz_skasowane_prace import pobierz_skasowane_prace

django.setup()


# Importy poniżej muszą być po django.setup() — stąd noqa E402.
from bpp.models import Uczelnia  # noqa: E402
from pbn_api.exceptions import IntegracjaWylaczonaException  # noqa: E402
from pbn_api.management.commands.util import PBNBaseCommand  # noqa: E402
from pbn_integrator import utils as integrator  # noqa: E402
from pbn_integrator.utils import (  # noqa: E402
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


def check_end_before(stage, end_before_stage):
    if end_before_stage == stage:
        sys.exit(0)


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

        (
            parser.add_argument(
                "--disable-multiprocessing", action="store_true", default=False
            ),
        )

        parser.add_argument("--start-from-stage", type=int, default=0)
        parser.add_argument("--end-before-stage", type=int, default=None)
        (parser.add_argument("--just-one-stage", action="store_true"),)

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
            "--export-pk-zero",
            action="store_true",
            default=None,
        )
        parser.add_argument(
            "--disable-progress-bar", action="store_true", default=False
        )

    def _run_stage(self, flag, enable_all, start, end, stage, func):
        """Uruchom etap jeśli odpowiednia flaga jest włączona."""
        check_end_before(stage, end)
        if (flag or enable_all) and start <= stage:
            func()

    def _handle_clears(self, clear_all, clear_match, clear_pubs):
        if clear_all:
            integrator.clear_all()
            sys.exit(0)
        if clear_match:
            integrator.clear_match_publications()
            sys.exit(0)
        if clear_pubs:
            integrator.clear_publications()
            sys.exit(0)

    def _handle_system_and_sources(self, opts, client, s, e):
        """Etapy 0-3: system data, źródła, instytucje."""
        ea = opts["enable_all"]
        dpb = opts["disable_progress_bar"]

        self._run_stage(
            opts["enable_system_data"],
            ea,
            s,
            e,
            0,
            lambda: (
                integruj_jezyki(client),
                integruj_kraje(client),
                client.download_disciplines(),
                client.sync_disciplines(),
            ),
        )
        self._run_stage(
            opts["enable_pobierz_zrodla"],
            ea,
            s,
            e,
            1,
            lambda: pobierz_zrodla(client),
        )
        self._run_stage(
            opts["enable_integruj_zrodla"],
            ea,
            s,
            e,
            2,
            lambda: integruj_zrodla(dpb),
        )
        self._run_stage(
            opts["enable_institutions"],
            ea,
            s,
            e,
            3,
            lambda: (
                pobierz_instytucje(client),
                integruj_uczelnie(),
                integruj_instytucje(),
            ),
        )

    def _handle_people(self, opts, client, s, e):
        """Etapy 6-9: pobieranie i integracja ludzi."""
        ea = opts["enable_all"]
        pbn_uid_id = client.uczelnia.pbn_uid_id

        self._run_stage(
            opts["enable_download_people_institution"],
            ea,
            s,
            e,
            6,
            lambda: pobierz_ludzi_z_uczelni(client, pbn_uid_id),
        )
        self._run_stage(
            opts["enable_integrate_people_institution"],
            ea,
            s,
            e,
            7,
            lambda: integruj_autorow_z_uczelni(client, pbn_uid_id),
        )
        self._run_stage(
            opts["enable_integrate_people_all"],
            ea,
            s,
            e,
            8,
            integruj_wszystkich_niezintegrowanych_autorow,
        )
        self._run_stage(
            opts["enable_check_orcid_people"],
            ea,
            s,
            e,
            9,
            lambda: weryfikuj_orcidy(client, pbn_uid_id),
        )

    def _handle_publishers_and_conferences(self, opts, client, s, e):
        """Etapy 10-11: wydawcy i konferencje."""
        ea = opts["enable_all"]

        self._run_stage(
            opts["enable_publishers"],
            ea,
            s,
            e,
            10,
            lambda: (
                pobierz_wydawcow_wszystkich(client),
                pobierz_wydawcow_mnisw(client),
                integruj_wydawcow(),
                call_command("pbn_importuj_wydawcow"),
            ),
        )
        self._run_stage(
            opts["enable_conferences"],
            ea,
            s,
            e,
            11,
            lambda: pobierz_konferencje(client),
        )

    def _handle_publications(self, opts, client, s, e):
        """Etapy 12-21: pobieranie i integracja publikacji."""
        ea = opts["enable_all"]
        skip_pages = opts["skip_pages"]
        dm = opts["disable_multiprocessing"]

        self._run_stage(
            opts["enable_pobierz_rekordy_publikacji_instytucji"],
            ea,
            s,
            e,
            12,
            lambda: pobierz_rekordy_publikacji_instytucji(client),
        )
        self._run_stage(
            opts["enable_pobierz_publikacje_instytucji"],
            ea,
            s,
            e,
            13,
            lambda: pobierz_publikacje_z_instytucji(client),
        )
        self._run_stage(
            opts["enable_pobierz_oswiadczenia_instytucji"],
            ea,
            s,
            e,
            14,
            lambda: pobierz_oswiadczenia_z_instytucji(client),
        )
        self._run_stage(
            opts["enable_odswiez_tabele_publikacji"],
            ea,
            s,
            e,
            15,
            lambda: pobierz_skasowane_prace(client),
        )
        self._run_stage(
            opts["enable_odswiez_tabele_publikacji"],
            ea,
            s,
            e,
            16,
            lambda: odswiez_tabele_publikacji(client),
        )
        self._run_stage(
            opts["enable_integruj_publikacje_instytucji"],
            ea,
            s,
            e,
            17,
            lambda: integruj_publikacje_instytucji(dm, skip_pages=skip_pages),
        )
        self._run_stage(
            opts["enable_pobierz_oswiadczenia_instytucji"],
            ea,
            s,
            e,
            18,
            integruj_oswiadczenia_z_instytucji,
        )
        self._run_stage(
            opts["enable_pobierz_po_doi"],
            ea,
            s,
            e,
            19,
            lambda: pobierz_prace_po_doi(client),
        )
        self._run_stage(
            opts["enable_pobierz_po_isbn"],
            ea,
            s,
            e,
            20,
            lambda: pobierz_prace_po_isbn(client),
        )
        self._run_stage(
            opts["enable_integruj_wszystkie_publikacje"],
            ea,
            s,
            e,
            21,
            lambda: (
                wyswietl_niezmatchowane_ze_zblizonymi_tytulami(),
                sprawdz_ilosc_autorow_przy_zmatchowaniu(),
            ),
        )

    def _handle_sync(self, opts, uczelnia, client):
        """Etap końcowy: synchronizacja publikacji z PBN."""
        if opts["enable_delete_all"]:
            usun_wszystkie_oswiadczenia(client)
        if opts["enable_delete_zeros"]:
            usun_zerowe_oswiadczenia(client)

        if opts["enable_sync"]:
            export_pk_zero = opts["export_pk_zero"]

            if export_pk_zero is None:
                export_pk_zero = not uczelnia.pbn_api_nie_wysylaj_prac_bez_pk

            synchronizuj_publikacje(
                client=client,
                force_upload=opts["force_upload"],
                only_bad=opts["only_bad"],
                only_new=opts["only_new"],
                export_pk_zero=export_pk_zero,
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
        export_pk_zero,
        *args,
        **options,
    ):
        if disable_multiprocessing:
            integrator.CPU_COUNT = "single"

        uczelnia_id = options.get("uczelnia_id")
        uczelnia = (
            Uczelnia.objects.get(pk=uczelnia_id)
            if uczelnia_id
            else Uczelnia.objects.get()
        )
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        self._handle_clears(clear_all, clear_match_publications, clear_publications)

        if just_one_stage:
            end_before_stage = start_from_stage + 1

        s = start_from_stage
        e = end_before_stage

        # Zbierz wszystkie opcje do słownika
        opts = {k: v for k, v in locals().items() if k.startswith("enable_")}
        opts.update(
            {
                "disable_progress_bar": disable_progress_bar,
                "disable_multiprocessing": disable_multiprocessing,
                "skip_pages": skip_pages,
                "force_upload": force_upload,
                "only_bad": only_bad,
                "only_new": only_new,
                "export_pk_zero": export_pk_zero,
            }
        )

        self._handle_system_and_sources(opts, client, s, e)
        self._handle_people(opts, client, s, e)
        self._handle_publishers_and_conferences(opts, client, s, e)
        self._handle_publications(opts, client, s, e)
        self._handle_sync(opts, uczelnia, client)
