"""Test command to run PBN import directly"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from pbn_import.models import ImportSession

User = get_user_model()


class Command(BaseCommand):
    help = "Test PBN import by running it directly (without Celery)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user", type=str, default="admin", help="Username to run import as"
        )

    def handle(self, *args, **options):
        username = options["user"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found"))
            return

        # Create test session
        session = ImportSession.objects.create(
            user=user,
            status="pending",
            config={
                "disable_initial": False,
                "disable_zrodla": False,
                "disable_wydawcy": False,
                "disable_konferencje": False,
                "disable_autorzy": False,
                "disable_publikacje": False,
                "disable_oswiadczenia": False,
                "disable_oplaty": False,
                "delete_existing": False,
                "wydzial_domyslny": "Wydział Domyślny",
            },
            current_step="Przygotowywanie importu...",
        )

        self.stdout.write(self.style.SUCCESS(f"Created import session #{session.id}"))
        self.stdout.write("Running import directly (not via Celery)...")

        # Run the task directly (not through Celery queue)
        from pbn_import.tasks import run_pbn_import

        run_pbn_import(session.id)

        # Refresh session
        session.refresh_from_db()

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completed with status: {session.get_status_display()}"
            )
        )
