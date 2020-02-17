# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Autor_Dyscyplina,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Ciagle_Autor,
)


class Command(BaseCommand):
    help = "Przypisuje dyscypliny do rekordów autorom, na podstawie wpisów Autor_Dyscyplina"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ustawiaj-pierwsza-gdy-dwie",
            action="store_true",
            help="""Dla osób posiadających dwie dysycpliny, ustawiaj zawsze pierwszą dyscyplinę.
            Jeżeli ta opcja nie zostanie określona, osoby posiadające dwie dysycpliny nie będą
            miały ustawianej dyscypliny w swoich rekordach. """,
        )
        parser.add_argument("rok", type=int)

    @transaction.atomic
    def handle(self, *args, **options):
        print("ID autora\tAutor\tRok\tDyscyplina\tTytul pracy\tID pracy")
        query = Autor_Dyscyplina.objects.all().exclude(dyscyplina_naukowa=None)

        if not options["ustawiaj_pierwsza_gdy_dwie"]:
            query = query.filter(subdyscyplina_naukowa=None)

        for ad in query:
            for klass in Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor:
                for instance in klass.objects.filter(
                    autor=ad.autor, rekord__rok=ad.rok, dyscyplina_naukowa=None
                ):
                    print(
                        f"{ad.autor.pk}\t{ad.autor}\t{ad.rok}\t"
                        f"{ad.dyscyplina_naukowa}\t{instance.rekord.tytul_oryginalny}"
                        f"\t{instance.rekord.pk}"
                    )
                    instance.dyscyplina_naukowa = ad.dyscyplina_naukowa
                    instance.save()
