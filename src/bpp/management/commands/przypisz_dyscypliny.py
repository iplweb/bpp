# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Autor_Dyscyplina, \
    Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor


class Command(BaseCommand):
    help = 'Przypisuje dyscypliny autorom, ktorzy maja tylko jedna dyscypline'

    @transaction.atomic
    def handle(self, *args, **options):
        print("ID autora\tAutor\tRok\tDyscyplina\tTytul pracy\tID pracy")
        for ad in Autor_Dyscyplina.objects.all().filter(subdyscyplina_naukowa=None).exclude(
                dyscyplina_naukowa=None):
            for klass in Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor:
                for instance in klass.objects.filter(autor=ad.autor, rekord__rok=ad.rok, dyscyplina_naukowa=None):
                    print(f"{ad.autor.pk}\t{ad.autor}\t{ad.rok}\t{ad.dyscyplina_naukowa}\t{instance.rekord.tytul_oryginalny}\t{instance.rekord.pk}")
                    instance.dyscyplina_naukowa = ad.dyscyplina_naukowa
                    instance.save()
