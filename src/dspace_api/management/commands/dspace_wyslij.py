from django.apps import apps
from django.core.management.base import BaseCommand

from dspace_api.eksport import eksportuj_rekord


class Command(BaseCommand):
    help = "Wyślij wybrane rekordy do DSpace (wachlarz per uczelnia)."

    def add_arguments(self, parser):
        parser.add_argument("model_name", help="np. wydawnictwo_ciagle")
        parser.add_argument("ids", nargs="+", help="ID rekordów")

    def handle(self, *args, **options):
        model = apps.get_model("bpp", options["model_name"])
        for rec in model.objects.filter(id__in=options["ids"]):
            for w in eksportuj_rekord(rec):
                self.stdout.write(
                    f"{rec.id} → {w['uczelnia']}: {w['status']} {w['powod']}"
                )
