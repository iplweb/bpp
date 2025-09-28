import sys
import time

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


class Command(BaseCommand):
    help = """Reset (pin) all disciplines in 2022-2025 records and wait for denorm flush.

    This command sets przypieta=True for all author-publication associations
    in the given year range, then monitors denorm dirty items until flushed.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be changed without actually making changes",
        )
        parser.add_argument(
            "--no-wait",
            action="store_true",
            default=False,
            help="Don't wait for denorm flush after resetting",
        )
        parser.add_argument(
            "--year-from", type=int, default=2022, help="Starting year (default: 2022)"
        )
        parser.add_argument(
            "--year-to", type=int, default=2025, help="Ending year (default: 2025)"
        )

    def get_dirty_count(self):
        """Get approximate count of dirty denorm items"""
        try:
            # Try to get dirty count from denorms
            from denorm.models import DirtyInstance

            return DirtyInstance.objects.count()
        except BaseException:
            # If DirtyInstance model doesn't exist, return 0
            return 0

    def handle(self, dry_run, no_wait, year_from, year_to, *args, **options):
        self.stdout.write(
            f"Resetting (pinning) disciplines for years {year_from}-{year_to}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - no changes will be made")
            )

        # Count records to update
        wc_count = Wydawnictwo_Ciagle_Autor.objects.filter(
            rekord__rok__gte=year_from, rekord__rok__lte=year_to, przypieta=False
        ).count()

        wz_count = Wydawnictwo_Zwarte_Autor.objects.filter(
            rekord__rok__gte=year_from, rekord__rok__lte=year_to, przypieta=False
        ).count()

        p_count = Patent_Autor.objects.filter(
            rekord__rok__gte=year_from, rekord__rok__lte=year_to, przypieta=False
        ).count()

        total_count = wc_count + wz_count + p_count

        self.stdout.write("\nRecords to reset (currently unpinned):")
        self.stdout.write(f"  Wydawnictwo_Ciagle_Autor: {wc_count}")
        self.stdout.write(f"  Wydawnictwo_Zwarte_Autor: {wz_count}")
        self.stdout.write(f"  Patent_Autor: {p_count}")
        self.stdout.write(f"  TOTAL: {total_count}")

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nNo unpinned records found. All disciplines are already pinned."
                )
            )
            return

        if not dry_run:
            with transaction.atomic():
                # Reset Wydawnictwo_Ciagle_Autor
                updated = Wydawnictwo_Ciagle_Autor.objects.filter(
                    rekord__rok__gte=year_from,
                    rekord__rok__lte=year_to,
                    przypieta=False,
                ).update(przypieta=True)
                self.stdout.write(
                    f"\nUpdated {updated} Wydawnictwo_Ciagle_Autor records"
                )

                # Reset Wydawnictwo_Zwarte_Autor
                updated = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord__rok__gte=year_from,
                    rekord__rok__lte=year_to,
                    przypieta=False,
                ).update(przypieta=True)
                self.stdout.write(f"Updated {updated} Wydawnictwo_Zwarte_Autor records")

                # Reset Patent_Autor
                updated = Patent_Autor.objects.filter(
                    rekord__rok__gte=year_from,
                    rekord__rok__lte=year_to,
                    przypieta=False,
                ).update(przypieta=True)
                self.stdout.write(f"Updated {updated} Patent_Autor records")

            self.stdout.write(
                self.style.SUCCESS(
                    "\nAll disciplines have been pinned (przypieta=True)"
                )
            )

            if not no_wait:
                # Monitor denorm dirty items
                self.stdout.write("\nMonitoring denorm dirty items...")
                self.stdout.write(
                    "You can manually flush denorms by running: python src/manage.py denorm_flush"
                )

                last_count = -1
                no_change_iterations = 0
                max_no_change_iterations = 10

                while True:
                    dirty_count = self.get_dirty_count()

                    if dirty_count != last_count:
                        sys.stdout.write(f"\rDirty items: {dirty_count}    ")
                        sys.stdout.flush()
                        last_count = dirty_count
                        no_change_iterations = 0
                    else:
                        no_change_iterations += 1

                    if dirty_count == 0:
                        self.stdout.write(
                            self.style.SUCCESS("\n\nDenorm flush complete!")
                        )
                        break

                    # If count hasn't changed for a while, suggest manual flush
                    if no_change_iterations >= max_no_change_iterations:
                        self.stdout.write(
                            self.style.WARNING(
                                f"\n\nDirty count hasn't changed for {max_no_change_iterations} iterations."
                            )
                        )
                        self.stdout.write(
                            "Consider running manual flush: python src/manage.py denorm_flush"
                        )
                        self.stdout.write(
                            "Or press Ctrl+C to exit and flush manually later."
                        )
                        no_change_iterations = 0  # Reset counter

                    time.sleep(1)
        else:
            self.stdout.write(self.style.WARNING("\nDRY RUN - no changes were made"))
