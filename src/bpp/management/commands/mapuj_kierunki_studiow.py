import sys

from django.core.management import BaseCommand, CommandError, CommandParser
from django.db import transaction

from bpp.models import Autorzy, AutorzyView, Jednostka, Kierunek_Studiow, Wydzial


class Command(BaseCommand):
    help = 'Mapuje kierunki studiów z zadanego "wydziału" i wyświetla zmienione rekordy'

    def add_arguments(self, parser: CommandParser):

        parser.add_argument(
            "--jednostka",
            default="Uniwersytet Medyczny w Lublinie",
            help="Jednostka, do której zostaną przypisani przemapowywani studenci",
        )

    @transaction.atomic
    def handle(self, jednostka, *args, **options):
        jednostka_id = -1
        try:
            jednostka_id = Jednostka.objects.get(nazwa=jednostka).pk
        except Jednostka.DoesNotExist:
            raise CommandError(
                f'Brak jednostki o nazwie "{jednostka}". '
                f"Uzyj parametru --jednostka i podaj inną nazwę"
            )

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

                for wa in [
                    a.original for a in Autorzy.objects.filter(jednostka=jednostka)
                ]:
                    wa.jednostka_id = jednostka_id
                    wa.kierunek_studiow = kierunek_studiow
                    print(
                        f"{wa.rekord.tytul_oryginalny}\t{wa.autor}\t{kierunek_studiow.nazwa}"
                    )
                    wa.save()

                jednostka.delete()
            wydzialokierunek.delete()

        # Skasuj nieuzywane kierunki studiow
        wykorzystane = AutorzyView.objects.values_list(
            "kierunek_studiow_id", flat=True
        ).distinct()

        for elem in Kierunek_Studiow.objects.all():
            if elem.pk not in wykorzystane:
                elem.delete()
