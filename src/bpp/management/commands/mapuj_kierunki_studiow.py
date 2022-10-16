import sys

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Autorzy, Jednostka, Kierunek_Studiow, Wydzial


class Command(BaseCommand):
    help = 'Mapuje kierunki studiów z zadanego "wydziału" i wyświetla zmienione rekordy'

    @transaction.atomic
    def handle(self, *args, **options):
        for wydzialokierunek in Wydzial.objects.filter(nazwa__startswith="Studenci - "):
            wnazwa = wydzialokierunek.nazwa.replace("Studenci - ", "").strip()
            try:
                wydzial = Wydzial.objects.get(nazwa=wnazwa)
            except Wydzial.DoesNotExist:
                print(f"Brak wydziału {wnazwa} -- {wydzialokierunek}")
                sys.exit(1)

            for jednostka in Jednostka.objects.filter(wydzial__nazwa=wydzialokierunek):
                nazwa = jednostka.nazwa.lower()
                skrot = jednostka.skrot.lower()

                kierunek_studiow = Kierunek_Studiow.objects.get_or_create(
                    nazwa=nazwa, skrot=skrot, wydzial=wydzial
                )[0]

                for wa in Autorzy.objects.filter(jednostka=jednostka):
                    wa.jednostka_id = -1
                    wa.kierunek_studiow = kierunek_studiow
                    print(
                        f"{wa.rekord.tytul_oryginalny}\t{wa.autor}\t{kierunek_studiow.nazwa}"
                    )
                    wa.save()

            jednostka.delete()
        wydzialokierunek.delete()
