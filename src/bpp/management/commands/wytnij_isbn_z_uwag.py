# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Wydawca,
    Wydawnictwo_Zwarte,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    cache,
)
import re

from bpp.util import wytnij_isbn_z_uwag


class Command(BaseCommand):
    help = 'Wycina ISBN z pola "Uwagi"'

    def add_arguments(self, parser):
        parser.add_argument("--przenies-do-uwag", action="store_true")
        parser.add_argument("--skasuj", action="store_true")

    @transaction.atomic
    def handle(self, przenies_do_uwag, skasuj, *args, **options):

        if przenies_do_uwag and skasuj:
            raise Exception("albo --skasuj, albo --przenies-do-uwag")

        if cache.enabled():
            cache.disable()

        for klass in Wydawnictwo_Zwarte, Wydawnictwo_Ciagle:
            for rec in klass.objects.filter(uwagi__istartswith="isbn"):

                res = wytnij_isbn_z_uwag(rec.uwagi)

                if res is None:
                    print(
                        f"*** No match for [{rec.uwagi}] ({rec.tytul_oryginalny}), why?"
                    )
                else:
                    isbn, rest = res

                    print(f"[{rec.uwagi}] => ISBN [{isbn}], uwagi [{rest}]")

                    if przenies_do_uwag:
                        rec.isbn = isbn
                        rec.uwagi = rest
                        rec.save()

                    if skasuj:
                        rec.uwagi = rest
                        rec.save()
