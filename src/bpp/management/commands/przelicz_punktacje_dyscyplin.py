"""Przelicza zapisaną punktację dyscyplin i sloty (cache punktacji) rekordów.

Używane po zmianie sposobu liczenia punktów/slotów (np. FD#618: √(k/m) i k/m
zaokrąglane do 4 miejsc przed mnożeniem, § 13 ust. 6 rozporządzenia
o ewaluacji). Domyślnie przelicza TYLKO rekordy, na które taka zmiana może
wpłynąć — te, które mają w cache punktacji dyscypliny slot mniejszy niż 1
(liczone z √(k/m) albo k/m). Rekordy ze slotem 1 (100% punktów albo k = m)
mają √(k/m) = k/m = 1 i nie zmieniają się.

Każdy rekord jest przeliczany we własnej transakcji, więc komendę można
przerwać i uruchomić ponownie (jest idempotentna), a strona działa w trakcie.
"""

import logging
import time

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bpp.models.cache import Cache_Punktacja_Dyscypliny
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

logger = logging.getLogger(__name__)

MODELE = (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)


def pk_rekordow_ze_slotem_ponizej_1():
    """Słownik {id typu zawartości: set(pk)} rekordów ze slotem < 1 w cache."""
    ret = {}
    for ct_id, pk in Cache_Punktacja_Dyscypliny.objects.filter(slot__lt=1).values_list(
        "rekord_id", flat=True
    ):
        ret.setdefault(ct_id, set()).add(pk)
    return ret


def przelicz_rekord(rekord):
    """Przelicz cache punktacji rekordu i zapisz pole ``cached_punkty_dyscyplin``.

    ``update()`` zamiast ``save()`` — nie przeliczamy pozostałych pól
    denormalizowanych (opisu bibliograficznego itd.), bo się nie zmieniają."""
    with transaction.atomic():
        wynik = rekord.przelicz_punkty_dyscyplin()
        type(rekord).objects.filter(pk=rekord.pk).update(cached_punkty_dyscyplin=wynik)


def wybierz_rekordy(model, wybrane, od_roku, do_roku):
    """Rekordy ``model`` z podanych lat; ``wybrane`` (gdy podane) zawęża do pk
    z :func:`pk_rekordow_ze_slotem_ponizej_1`."""
    qs = model.objects.all()
    if od_roku is not None:
        qs = qs.filter(rok__gte=od_roku)
    if do_roku is not None:
        qs = qs.filter(rok__lte=do_roku)
    if wybrane is not None:
        ct_id = ContentType.objects.get_for_model(model).pk
        qs = qs.filter(pk__in=wybrane.get(ct_id, set()))
    return qs.order_by("pk")


class Command(BaseCommand):
    help = (
        "Przelicza zapisaną punktację dyscyplin i sloty (cache punktacji) "
        "artykułów, monografii i rozdziałów. Domyślnie tylko rekordy ze "
        "slotem < 1 (liczone z √(k/m) albo k/m)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wszystkie",
            action="store_true",
            help="Przelicz wszystkie rekordy z podanych lat, nie tylko te ze "
            "slotem < 1.",
        )
        parser.add_argument("--od-roku", type=int, default=None)
        parser.add_argument("--do-roku", type=int, default=None)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko policz, ile rekordów zostałoby przeliczonych.",
        )

    def handle(self, *args, wszystkie, od_roku, do_roku, dry_run, **options):
        verbosity = int(options.get("verbosity", 1))
        wybrane = None if wszystkie else pk_rekordow_ze_slotem_ponizej_1()

        querysety = [
            (model, wybierz_rekordy(model, wybrane, od_roku, do_roku))
            for model in MODELE
        ]

        razem = sum(qs.count() for _, qs in querysety)
        self.stdout.write(f"Rekordów do przeliczenia: {razem}")
        if dry_run:
            return

        start = time.monotonic()
        zrobione = bledy = 0
        for model, qs in querysety:
            for rekord in qs.iterator(chunk_size=500):
                try:
                    przelicz_rekord(rekord)
                except Exception:
                    # Pętla po całej bazie ma dojść do końca; błąd logujemy
                    # z tracebackiem, a na końcu komenda kończy się błędem.
                    logger.exception(
                        "Nie udało się przeliczyć punktacji %s pk=%s",
                        model.__name__,
                        rekord.pk,
                    )
                    bledy += 1
                zrobione += 1
                if verbosity >= 1 and zrobione % 1000 == 0:
                    minelo = time.monotonic() - start
                    self.stdout.write(
                        f"  {zrobione}/{razem} ({minelo:.0f} s, "
                        f"{minelo / zrobione * 1000:.0f} ms/rekord)"
                    )

        minelo = time.monotonic() - start
        if bledy:
            raise CommandError(
                f"Przeliczono {zrobione - bledy}/{razem} rekordów w {minelo:.0f} s; "
                f"błędy: {bledy} (szczegóły w logu)."
            )
        self.stdout.write(
            self.style.SUCCESS(f"Przeliczono {zrobione} rekordów w {minelo:.0f} s.")
        )
