"""Masowe kasowanie źródeł (Zrodlo) bez żadnych publikacji.

Powstało bo w adminie zaznaczenie ~35 tys. źródeł do skasowania przekracza
``DATA_UPLOAD_MAX_NUMBER_FIELDS`` (każde zaznaczone źródło = jedno pole POST).
Ta komenda omija ten limit (działa na queryset, nie na liście PK z formularza)
i kasuje wsadowo.

Bezpieczne: kasuje WYŁĄCZNIE źródła bez publikacji — źródła z choćby jednym
wydawnictwem ciągłym nigdy nie są ruszane.
"""

from django.core.management.base import BaseCommand

from bpp.models.zrodlo import Zrodlo


def zrodla_bez_publikacji(*, bez_mnisw=False):
    """QuerySet źródeł bez żadnej publikacji (opcjonalnie tylko bez mniswID).

    ``ma_publikacje=nie`` w adminie == brak powiązanego Wydawnictwo_Ciagle.
    ``mnisw_id=brak`` == ``pbn_uid__mniswId`` jest NULL (obejmuje też źródła
    bez pbn_uid)."""
    qs = Zrodlo.objects.filter(wydawnictwo_ciagle__isnull=True)
    if bez_mnisw:
        qs = qs.filter(pbn_uid__mniswId__isnull=True)
    return qs.distinct()


class Command(BaseCommand):
    help = (
        "Usuwa źródła (Zrodlo) bez żadnych publikacji. "
        "Bezpieczne: nie tyka źródeł z publikacjami."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bez-mnisw",
            action="store_true",
            help="Usuń tylko źródła BEZ mniswID (jak filtr admina mnisw_id=brak).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko pokaż, ile źródeł zostałoby usuniętych — nic nie kasuj.",
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=0,
            help=(
                "Rozmiar paczki kasowania. 0 (domyślnie) = wszystko w JEDNYM "
                "przebiegu — najszybciej, bo kaskada Django (cascade / SET NULL "
                "po ~15 tabelach powiązanych) liczona jest raz, a nie raz na "
                "paczkę. Ustaw dodatnią wartość tylko przy problemach z pamięcią."
            ),
        )

    def handle(self, *args, **options):
        bez_mnisw = options["bez_mnisw"]
        dry_run = options["dry_run"]
        batch = options["batch"]

        pks = list(
            zrodla_bez_publikacji(bez_mnisw=bez_mnisw).values_list("pk", flat=True)
        )
        total = len(pks)
        opis = "bez publikacji" + (" i bez mniswID" if bez_mnisw else "")
        self.stdout.write(f"Źródeł {opis}: {total}")

        if dry_run:
            self.stdout.write("--dry-run: nic nie usunięto.")
            return

        if batch and batch < total:
            deleted = 0
            for i in range(0, total, batch):
                chunk = pks[i : i + batch]
                Zrodlo.objects.filter(pk__in=chunk).delete()
                deleted += len(chunk)
                self.stdout.write(f"  usunięto {deleted}/{total}...")
        else:
            # Jeden przebieg kolektora kaskady — najszybciej.
            Zrodlo.objects.filter(pk__in=pks).delete()
            deleted = total

        self.stdout.write(self.style.SUCCESS(f"Usunięto {deleted} źródeł ({opis})."))
