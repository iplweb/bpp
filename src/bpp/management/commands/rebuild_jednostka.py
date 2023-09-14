from django.core.management import BaseCommand

from bpp.models import Jednostka


class Command(BaseCommand):
    def handle(self, *args, **options):
        Jednostka.objects.rebuild()
