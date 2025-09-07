from tqdm import tqdm

from pbn_api.management.commands.util import PBNBaseCommand
from pbn_integrator import utils as integrator


class Command(PBNBaseCommand):
    help = "Download institution statements (oświadczenia) and institution publications from PBN API"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--oswiadczenia-only",
            action="store_true",
            help="Download only institution statements (oświadczenia)",
        )
        parser.add_argument(
            "--publikacje-only",
            action="store_true",
            help="Download only institution publications (publikacje instytucji)",
        )

    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        oswiadczenia_only = options.get("oswiadczenia_only", False)
        publikacje_only = options.get("publikacje_only", False)

        # Validate mutually exclusive options
        if oswiadczenia_only and publikacje_only:
            self.stdout.write(
                self.style.ERROR(
                    "Cannot use both --oswiadczenia-only and --publikacje-only"
                )
            )
            return

        client = self.get_client(
            app_id=app_id, app_token=app_token, base_url=base_url, user_token=user_token
        )

        # Download oświadczenia instytucji (institution statements)
        if not publikacje_only:
            tqdm.write(
                self.style.SUCCESS(
                    "Starting download of institution statements (oświadczenia)..."
                )
            )
            try:
                integrator.pobierz_oswiadczenia_z_instytucji(client)
                tqdm.write(
                    self.style.SUCCESS(
                        "✓ Successfully downloaded institution statements"
                    )
                )
            except Exception as e:
                tqdm.write(
                    self.style.ERROR(f"✗ Error downloading institution statements: {e}")
                )
                if not oswiadczenia_only:
                    tqdm.write(
                        self.style.WARNING("Continuing with publication downloads...")
                    )
                else:
                    return

        # Download publikacje instytucji (institution publications)
        if not oswiadczenia_only:
            tqdm.write(
                self.style.SUCCESS(
                    "Starting download of institution publications (publikacje)..."
                )
            )
            try:
                integrator.pobierz_publikacje_z_instytucji(client)
                tqdm.write(
                    self.style.SUCCESS(
                        "✓ Successfully downloaded institution publications"
                    )
                )
            except Exception as e:
                tqdm.write(
                    self.style.ERROR(
                        f"✗ Error downloading institution publications: {e}"
                    )
                )

        tqdm.write(self.style.SUCCESS("\n🎉 Download process completed!"))
