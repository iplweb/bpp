# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Wydawca,
    Wydawnictwo_Zwarte,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
)
import re


class Command(BaseCommand):
    help = 'Wycina ISBN z pola "Uwagi"'

    @transaction.atomic
    def handle(self, *args, **options):
        isbn_regex = re.compile(
            r"^isbn\s*[0-9]*[-| ][0-9]*[-| ][0-9]*[-| ][0-9]*[-| ][0-9]*",
            flags=re.IGNORECASE,
        )

        for klass in Wydawnictwo_Zwarte, Wydawnictwo_Ciagle:
            for rec in klass.objects.filter(uwagi__istartswith="isbn"):
                res = isbn_regex.search(rec.uwagi)
                if res:
                    res = res.group()
                    orig_uwagi = rec.uwagi
                    rec.isbn = res.replace("ISBN", "").replace("isbn", "").strip()
                    rec.uwagi = rec.uwagi.replace(res, "").strip()

                    while (
                        rec.uwagi.startswith(".")
                        or rec.uwagi.startswith(";")
                        or rec.uwagi.startswith(",")
                    ):
                        rec.uwagi = rec.uwagi[1:].strip()

                    print(f"[{orig_uwagi}] => ISBN [{rec.isbn}], uwagi [{rec.uwagi}]")
                    rec.save()
                else:
                    print(
                        f"*** No match for [{rec.uwagi}] ({rec.tytul_oryginalny}), why?"
                    )
