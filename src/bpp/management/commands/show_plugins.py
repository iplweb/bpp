from django.core.management import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Pokazuje listę zainstalowanych pluginów BPP"

    @transaction.atomic
    def handle(self, *args, **options):
        from django.conf import settings

        print(getattr(settings, "DISCOVERED_PLUGINS", []))
