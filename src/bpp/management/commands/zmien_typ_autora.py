from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    cache,
)


def set_seq(s):
    if settings.DATABASES["default"]["ENGINE"].find("postgresql") >= 0:
        from django.db import connection

        cursor = connection.cursor()
        cursor.execute(f"SELECT setval('{s}_id_seq', (SELECT MAX(id) FROM {s}))")


class Command(BaseCommand):
    help = "Zmienia typ odpowiedzialnosci autora na autora z redaktora w podanym charakterze formalnym"

    def add_arguments(self, parser):
        parser.add_argument("skrot")

    @transaction.atomic
    def handle(self, skrot, *args, **options):
        if cache.enabled():
            cache.disable()

        to_aut = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")
        to_red = Typ_Odpowiedzialnosci.objects.get(skrot="red.")
        for klass in Wydawnictwo_Zwarte, Wydawnictwo_Ciagle:
            for elem in klass.objects.filter(charakter_formalny__skrot=skrot):
                for wza in elem.autorzy_set.filter(typ_odpowiedzialnosci=to_red):
                    wza.typ_odpowiedzialnosci = to_aut
                    wza.save()
