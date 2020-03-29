# -*- encoding: utf-8 -*-
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.struktura import Jednostka, Uczelnia


class Command(BaseCommand):
    help = "Ustawia obcą jednostkę"

    def add_arguments(self, parser):
        parser.add_argument("nazwa")
        parser.add_argument(
            "--wymuszaj",
            default=False,
            action="store_true",
            help="jeżeli PRAWDA to wymusi ustawienie wartości "
            "skupia_pracownikow jednostki na 'fałsz'",
        )

    @transaction.atomic
    def handle(self, nazwa, wymuszaj, *args, **options):
        j = Jednostka.objects.get(nazwa=nazwa)
        u = Uczelnia.objects.first()
        u.obca_jednostka = j
        if wymuszaj:
            if j.skupia_pracownikow:
                j.skupia_pracownikow = False
                j.save()

        u.save()

        j.skupia_pracownikow = False
        j.save()
