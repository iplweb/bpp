import argparse

from django.db import transaction
from django.db.transaction import TransactionManagementError
from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla, Zrodlo
from pbn_api.management.commands.util import PBNBaseCommand


class DryRunException(TransactionManagementError):
    pass


class Command(PBNBaseCommand):
    """Nadpisuje wszystkie dyscypliny dla zrodel z odpowiednikami z PBNu"""

    def add_arguments(self, parser):
        parser.add_argument("--min-rok", type=int, default=2022)
        parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction)

    def _import_points_for_zrodlo(self, zrodlo, min_rok):
        """Import points for a source and return set of years with data."""
        points = zrodlo.pbn_uid.value("object", "points", return_none=True) or []
        lata_z_punktami = set()

        for rok in points:
            if int(rok) < min_rok:
                continue
            lata_z_punktami.add(int(rok))
            punkty = points[rok]["points"]
            self._update_or_create_punktacja(zrodlo, rok, punkty)
        else:
            tqdm.write(
                f"IDZ-6; zrodlo; {zrodlo.nazwa}; "
                f"nie zawiera danych o punktach "
                f"po stronie PBN"
            )

        return lata_z_punktami

    def _update_or_create_punktacja(self, zrodlo, rok, punkty):
        """Update or create Punktacja_Zrodla for given year."""
        try:
            pzr = zrodlo.punktacja_zrodla_set.get(rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            tqdm.write(
                f"IDZ-4: tworze nowy wpis punktacji zrodla; za rok; {rok}; "
                f"{zrodlo.nazwa}; punkty; {punkty}"
            )
            zrodlo.punktacja_zrodla_set.create(punkty_kbn=punkty, rok=rok)
            return

        if pzr.punkty_kbn != punkty:
            tqdm.write(
                f"IDZ-5: zrodlo; {zrodlo.nazwa}; rok; {rok}; BPP ma punktow; "
                f"{pzr.punkty_kbn}; a w PBN jest; {punkty}; ustawiam na PBN"
            )
            pzr.punkty_kbn = punkty
            pzr.save()

    def _import_disciplines_for_zrodlo(
        self, zrodlo, lata_z_punktami, min_rok, dyscypliny, missing
    ):
        """Import disciplines for a source."""
        aktualne_dyscypliny_zrodla = set(
            zrodlo.dyscyplina_zrodla_set.all().values_list(
                "dyscyplina__nazwa", flat=True
            )
        )

        zrodlo.dyscyplina_zrodla_set.all().delete()

        disciplines = zrodlo.pbn_uid.value("object", "disciplines", return_none=True)
        if not disciplines:
            tqdm.write(
                f"IDZ-1: źródło {zrodlo.pbn_uid} nie zawiera informacji o dyscyplinach"
            )
            return

        if not lata_z_punktami:
            tqdm.write(
                f"IDZ-7: źródło {zrodlo.pbn_uid} "
                f"nie ma danych o punktach "
                f"za lata >= {min_rok}, "
                f"pomijam przypisanie dyscyplin"
            )
            return

        self._assign_disciplines(
            zrodlo,
            disciplines,
            lata_z_punktami,
            dyscypliny,
            missing,
        )
        self._log_discipline_changes(zrodlo, aktualne_dyscypliny_zrodla)

    def _assign_disciplines(
        self,
        zrodlo,
        disciplines,
        lata_z_punktami,
        dyscypliny,
        missing,
    ):
        """Assign disciplines to source for all years with point data."""
        for disc_dict in disciplines:
            code = disc_dict.get("code") if isinstance(disc_dict, dict) else disc_dict
            if not code:
                continue
            code = str(code)
            kod_dyscypliny = f"{int(code[0])}.{int(code[1:])}"

            if kod_dyscypliny not in dyscypliny:
                if kod_dyscypliny not in missing:
                    tqdm.write(
                        f"IDZ-0: po stronie BPP brak kodu dyscypliny: {kod_dyscypliny}"
                    )
                    missing.add(kod_dyscypliny)
                continue

            for rok in lata_z_punktami:
                zrodlo.dyscyplina_zrodla_set.get_or_create(
                    dyscyplina_id=dyscypliny[kod_dyscypliny].pk,
                    rok=rok,
                )

    def _log_discipline_changes(self, zrodlo, aktualne_dyscypliny_zrodla):
        """Log added and removed disciplines."""
        nowe_dyscypliny_zrodla = set(
            zrodlo.dyscyplina_zrodla_set.all().values_list(
                "dyscyplina__nazwa", flat=True
            )
        )
        dodane = nowe_dyscypliny_zrodla.difference(aktualne_dyscypliny_zrodla)
        usuniete = aktualne_dyscypliny_zrodla.difference(nowe_dyscypliny_zrodla)

        if dodane:
            tqdm.write(f"IDZ-2: {zrodlo.nazwa} ;+++   DODANE; {dodane}")
        if usuniete:
            tqdm.write(f"IDZ-3: {zrodlo.nazwa} ;--- USUNIETE; {usuniete}")

    @transaction.atomic
    def handle(self, min_rok, dry_run, verbosity=1, *args, **options):
        dyscypliny = {x.kod: x for x in Dyscyplina_Naukowa.objects.all()}
        missing = set()

        queryset = Zrodlo.objects.exclude(pbn_uid_id=None).select_related("pbn_uid")
        for zrodlo in tqdm(queryset, desc="Import dyscyplin"):
            lata_z_punktami = self._import_points_for_zrodlo(zrodlo, min_rok)
            self._import_disciplines_for_zrodlo(
                zrodlo,
                lata_z_punktami,
                min_rok,
                dyscypliny,
                missing,
            )

        if dry_run:
            raise DryRunException(
                "IDZ-X: podano opcję --dry-run, wywołuję błąd, aby wycofać zmiany"
            )
