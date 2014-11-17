# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.cache import Rekord
from bpp.models import cache
from bpp.models.system import Charakter_Formalny
from bpp.util import NewGetter


class Command(BaseCommand):
    help = u'Zmienia charaktery formalne wg wytycznych'

    @transaction.atomic
    def handle(self, *args, **options):
        cache.enable()

        Charakter_Formalny.objects.get_or_create(
            nazwa="Artykuł w czasopismie",
            skrot="AC",
            publikacja=True,
            streszczenie=False)

        Charakter_Formalny.objects.get_or_create(
            nazwa="Książka",
            skrot="KS",
            publikacja=True,
            streszczenie=False
        )

        charakter = NewGetter(Charakter_Formalny)

        def safe_delete(skrot):
            try:
                char = charakter[skrot]
            except KeyError:
                print skrot, " => charakter nie znaleziony"
                return

            for elem in Rekord.objects.filter(charakter_formalny=char):
                print "Usuwam: ", elem
                elem.original.delete()

            char.delete()

        def safe_type_change(_from, _to):
            try:
                char = charakter[_from]
            except KeyError:
                print _from, " => charakter nie znaleziony"
                return

            for elem in Rekord.objects.filter(charakter_formalny=char):
                orig = elem.original
                print "zmieniam", _from, "na", _to, "dla", orig
                orig.charakter_formalny = charakter[_to]
                orig.save()

            char.delete()

        safe_delete("S")
        safe_delete("ZSUM")
        safe_delete("BPEX")
        safe_delete('PW')

        safe_type_change("AP", "AC")
        safe_type_change("API", "AC")
        safe_type_change("AZ", "AC")

        dok = charakter['DOK']
        dok.skrot = 'D'
        dok.save()

        hab = charakter['HAB']
        hab.skrot = 'H'
        hab.save()

        podr = charakter['PODR']
        podr.skrot = 'PA'
        podr.save()

        safe_type_change('PSI', 'PSZ')
        safe_type_change('PSUM', 'PSZ')

        safe_type_change('PRI', 'PRZ')

