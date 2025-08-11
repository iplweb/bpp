import random

from coverage.html import os
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from pbn_api.models import (
    Conference,
    Discipline,
    DisciplineGroup,
    Institution,
    Journal,
    Language,
    OswiadczenieInstytucji,
    Publication,
    PublikacjaInstytucji,
    Publisher,
    Scientist,
    SentData,
)

from bpp.models import (
    Autor,
    Konferencja,
    Patent,
    Patent_Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)
from bpp.util import pbar


class Command(BaseCommand):
    help = (
        "Czyści dane z PBNu oraz dane z bazy BPP (autorzy, źródła, wydawcy, publikacje)"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("--tylko-publikacje", action="store_true", default=False),

    @transaction.atomic
    def handle(self, tylko_publikacje, *args, **options):
        challenge = "".join(random.sample("abcdefghijklmnopqrstuvwxzy!@#$^^&", 5))
        print("Informacje o systemie")
        print("=====================")
        os.system("uname -mon")
        print(settings.DATABASES["default"])
        print("")
        print("Baza danych czyja?")
        print("==================")
        print(Uczelnia.objects.get_default())
        print("")
        print("Kasowanie danych?")
        print("=================")

        if not tylko_publikacje:
            print(
                f"Aby skasować wszystkich autorów, publikacje i dane z PBN, wpisz znaki '{challenge}' "
                f"lub naciśnij CTRL+C aby wyjść. "
            )
        else:
            print(
                f"Aby skasować tylko publikacje po stronie BPP -- BEZ autorow w BPP, bez Źródeł w BPP, bez danych z "
                f"PBN, wpisz znaki '{challenge}' lub naciśnij CTRL+C aby wyjść. "
            )

        reply = input("> ")
        if challenge != reply:
            print("Wychodzę z programu")
            return

        klasy_do_skasowania = [
            # BPP
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
            Patent_Autor,
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Patent,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        ]

        if not tylko_publikacje:
            klasy_do_skasowania += [
                # BPP
                Zrodlo,
                Wydawca,
                Konferencja,
                Autor,
                # PBN
                Journal,
                Scientist,
                Conference,
                Discipline,
                DisciplineGroup,
                Institution,
                Language,
                OswiadczenieInstytucji,
                Publication,
                PublikacjaInstytucji,
                Publisher,
                Scientist,
                SentData,
            ]

        for klass in pbar(
            klasy_do_skasowania,
            label="Kasuję dane z bazy BPP:",
        ):
            klass.objects.all().delete()
