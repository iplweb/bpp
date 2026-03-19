import rollbar
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Wysyła testową wiadomość do Rollbara w celu weryfikacji integracji."

    def handle(self, *args, **options):
        rollbar.report_message(
            "Testowa wiadomość z management command test_rollbar",
            "info",
        )
        self.stdout.write(self.style.SUCCESS("Wiadomość testowa wysłana do Rollbara."))
