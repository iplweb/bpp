from celery_singleton import clear_locks
from django.core.management.base import BaseCommand

from django_bpp.celery_tasks import app


class Command(BaseCommand):
    help = "Clears celery-singleton locks for optimization tasks"

    def handle(self, *args, **options):
        self.stdout.write("Clearing celery-singleton locks...")

        try:
            clear_locks(app)
            self.stdout.write(
                self.style.SUCCESS("Successfully cleared all celery-singleton locks")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to clear locks: {e}"))
            raise
