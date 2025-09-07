import os
import sys

from django.core.management.base import BaseCommand

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")


class Command(BaseCommand):
    help = "Generate all possible work combinations for evaluation optimization"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rok-min",
            type=int,
            default=2022,
            help="Minimum year to process (default: 2022)",
        )
        parser.add_argument(
            "--rok-max",
            type=int,
            default=2025,
            help="Maximum year to process (default: 2025)",
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            help="Number of processes to use (default: 2 * CPU count)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of records per batch (default: 50)",
        )
        parser.add_argument(
            "--no-multiprocessing",
            action="store_true",
            help="Disable multiprocessing and run in single process mode",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose output (print each combination)",
        )

    def handle(self, *args, **options):
        from ewaluacja_optymalizacja.utils import wszystkie_wersje_rekordow

        rok_min = options["rok_min"]
        rok_max = options["rok_max"]
        max_workers = options["max_workers"]
        batch_size = options["batch_size"]
        use_multiprocessing = not options["no_multiprocessing"]
        verbose = options["verbose"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting work combinations generation for years {rok_min}-{rok_max}"
            )
        )

        if use_multiprocessing:
            self.stdout.write(
                f"Using multiprocessing with {max_workers or '2 * CPU count'} workers, "
                f"batch size: {batch_size}"
            )
        else:
            self.stdout.write("Running in single process mode")

        count = 0
        try:
            for elem in wszystkie_wersje_rekordow(
                rok_min=rok_min,
                rok_max=rok_max,
                max_workers=max_workers,
                batch_size=batch_size,
                use_multiprocessing=use_multiprocessing,
            ):
                if verbose:
                    self.stdout.write(str(elem))
                    self.stdout.write("---")
                count += 1

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING(
                    f"\nProcessing interrupted. Processed {count} combinations."
                )
            )
            return

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during processing: {e}"))
            raise

        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed {count} work combinations")
        )
