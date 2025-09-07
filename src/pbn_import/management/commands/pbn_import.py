"""Modern PBN import command using ImportManager"""

from django.core.management import BaseCommand

from pbn_api.client import PBNClient
from pbn_import.models import ImportSession
from pbn_import.utils import ImportManager

from django.contrib.auth import get_user_model

from bpp.models import Uczelnia

User = get_user_model()


class Command(BaseCommand):
    help = "Import data from PBN using the modern import system"

    def add_arguments(self, parser):
        # PBN API credentials
        parser.add_argument("--app-id", required=True, help="PBN Application ID")
        parser.add_argument("--app-token", required=True, help="PBN Application Token")
        parser.add_argument("--user-token", required=True, help="PBN User Token")
        parser.add_argument(
            "--base-url",
            default="https://pbn-micro-alpha.opi.org.pl",
            help="PBN API Base URL",
        )

        # Import options
        parser.add_argument(
            "--disable-initial", action="store_true", help="Skip initial setup"
        )
        parser.add_argument(
            "--disable-zrodla", action="store_true", help="Skip sources import"
        )
        parser.add_argument(
            "--disable-konferencje", action="store_true", help="Skip conferences import"
        )
        parser.add_argument(
            "--disable-wydawcy", action="store_true", help="Skip publishers import"
        )
        parser.add_argument(
            "--disable-autorzy", action="store_true", help="Skip authors import"
        )
        parser.add_argument(
            "--disable-publikacje", action="store_true", help="Skip publications import"
        )
        parser.add_argument(
            "--disable-oswiadczenia", action="store_true", help="Skip statements import"
        )
        parser.add_argument(
            "--disable-oplaty", action="store_true", help="Skip fees import"
        )

        # Additional options
        parser.add_argument(
            "--delete-existing",
            action="store_true",
            help="Delete existing PBN publications",
        )
        parser.add_argument(
            "--wydzial-domyslny",
            default="Wydział Domyślny",
            help="Default department name",
        )
        parser.add_argument(
            "--wydzial-domyslny-skrot", help="Default department abbreviation"
        )

        # User for session tracking
        parser.add_argument(
            "--username", help="Username for import session (default: first superuser)"
        )

    def handle(self, *args, **options):
        # Get user for session
        if options["username"]:
            user = User.objects.get(username=options["username"])
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stderr.write("No superuser found. Please specify --username")
                return

        # Enable PBN integration
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia and not uczelnia.pbn_integracja:
            uczelnia.pbn_integracja = True
            uczelnia.save(update_fields=["pbn_integracja"])

        # Create PBN client
        client = PBNClient(
            base_url=options["base_url"],
            app_id=options["app_id"],
            app_token=options["app_token"],
            user_token=options["user_token"],
        )

        # Create import session
        session = ImportSession.objects.create(
            user=user,
            status="pending",
            config={
                "app_id": options["app_id"],
                "base_url": options["base_url"],
                "disable_initial": options["disable_initial"],
                "disable_zrodla": options["disable_zrodla"],
                "disable_konferencje": options["disable_konferencje"],
                "disable_wydawcy": options["disable_wydawcy"],
                "disable_autorzy": options["disable_autorzy"],
                "disable_publikacje": options["disable_publikacje"],
                "disable_oswiadczenia": options["disable_oswiadczenia"],
                "disable_oplaty": options["disable_oplaty"],
                "delete_existing": options["delete_existing"],
                "wydzial_domyslny": options["wydzial_domyslny"],
                "wydzial_domyslny_skrot": options["wydzial_domyslny_skrot"],
            },
        )

        self.stdout.write(f"Created import session {session.id}")

        # Create and run import manager
        manager = ImportManager(session=session, client=client, config=session.config)

        # Create import steps in database
        manager.create_import_steps()

        try:
            self.stdout.write("Starting import...")
            results = manager.run()

            self.stdout.write(
                self.style.SUCCESS("\n=== Import completed successfully ===")
            )

            # Display results
            for step_name, result in results.items():
                if isinstance(result, dict):
                    if "error" in result:
                        self.stdout.write(
                            f"  {step_name}: {self.style.ERROR('FAILED')}"
                        )
                    else:
                        self.stdout.write(f"  {step_name}: {self.style.SUCCESS('OK')}")

            # Display statistics
            if hasattr(session, "statistics"):
                stats = session.statistics
                self.stdout.write("\n=== Statistics ===")
                self.stdout.write(f"  Authors imported: {stats.authors_imported}")
                self.stdout.write(
                    f"  Publications imported: {stats.publications_imported}"
                )
                self.stdout.write(f"  Duration: {session.duration}")

                if stats.coffee_breaks_recommended > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n  ☕ You deserved {stats.coffee_breaks_recommended} coffee break(s)!"
                        )
                    )

        except Exception as e:
            self.stderr.write(f"\n{self.style.ERROR('Import failed:')}")
            self.stderr.write(str(e))

            if session.error_message:
                self.stderr.write("\nError details:")
                self.stderr.write(session.error_message)

            raise
