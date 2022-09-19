import json

from crossref.restful import Works
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Rekord


class Command(BaseCommand):
    help = "Pobiera dane z Crossref API dla ostatnich 100 rekordów z DOI"

    @transaction.atomic
    def handle(self, *args, **options):
        works = Works()
        for rekord in (
            Rekord.objects.exclude(doi=None)
            .exclude(doi="")
            .order_by("-ostatnio_zmieniony")[:100]
        ):
            data = works.doi(rekord.doi)
            if data:
                print(f"{rekord.tytul_oryginalny}")
                print(f"{rekord.pk}")
                print("")
                print(json.dumps(data, indent=4))
                print("-" * 80)
