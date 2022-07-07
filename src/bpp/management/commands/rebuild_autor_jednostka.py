from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Autor_Jednostka
from bpp.util import pbar


class Command(BaseCommand):
    help = "Przebudowuje przypisania autora do jednostek w całej bazie; wskazane uruchamianie raz na dobę"

    @transaction.atomic
    def handle(self, *args, **options):
        for elem in pbar(Autor_Jednostka.objects.all()):
            elem.save()
