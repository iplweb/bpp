# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.management.commands.import_bpp import set_seq
from bpp.models import (
    Autor,
    Jednostka,
    Wydzial,
    Uczelnia,
    Zrodlo,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Baza,
    Praca_Doktorska,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    cache,
)


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
