import argparse

from django.core.management import BaseCommand, CommandError, CommandParser
from django.db import transaction

from bpp.models import Autorzy, Jednostka


class Command(BaseCommand):
    help = (
        'Dla osob które maja prace z jednostki (parametru -- domyslnie "Uniwersytet Medyczny w Lublinie") '
        "oraz wpisany kierunek studiów, ta procedura przypisuje im koła naukowe, do których są przypisani "
        "jako autor w modelu Autor_Jednostka. "
        "Jeżeli autor jest przypisany do kilku kół naukowych, system wyrzuca dla niego komunikat i nic nie robi. "
        "Podobnie gdy autor nie jest w ogóle przypisany do żadnego koła"
    )

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--jednostka",
            default="Uniwersytet Medyczny w Lublinie",
            help="Jednostka z której zostaną przypisani do kół przemapowywani studenci",
        )
        parser.add_argument(
            "--rok",
            type=int,
            default=2022,
            help="Ogranicz do roku",
        )
        parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction)

    @transaction.atomic
    def handle(self, jednostka, rok, dry_run, *args, **options):
        for _jedn in Jednostka.objects.exclude(
            rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
        ):
            if (
                _jedn.nazwa.lower().find("koło naukowe") >= 0
                or _jedn.nazwa.lower().find("skn ") >= 0
            ):
                print(
                    f"Jednostka {_jedn.nazwa} wydaje się byc kołem naukowym, "
                    f"ale nie ma określonego własciwego rodzaju jednostki. Ustawiam rodzaj na koło naukowe"
                )
                _jedn.rodzaj_jednostki = Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
                _jedn.save()

        jednostka_id = -1
        try:
            jednostka_id = Jednostka.objects.get(nazwa=jednostka).pk
        except Jednostka.DoesNotExist:
            raise CommandError(
                f'Brak jednostki o nazwie "{jednostka}". '
                f"Uzyj parametru --jednostka i podaj inną nazwę"
            )

        for aj in Autorzy.objects.filter(jednostka__pk=jednostka_id, rekord__rok=rok):
            # Znajdź dla autora jednostkę będącą kołem naukowym
            autor = aj.autor

            if aj.kierunek_studiow_id is None:
                print(
                    f"Autor {autor} nie ma określonego kierunku studiów, nie przypiszę żadnego koła naukowego. "
                    f"Rekord: {aj.rekord.tytul_oryginalny}, {aj.rekord_id}"
                )

            kolo_naukowe = autor.jednostki.filter(
                rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
            )

            if not kolo_naukowe.exists():
                print(
                    f"Autor {autor} nie ma zadnego kola naukowego, nie mam gdzie przypisać -- "
                    f"praca {aj.rekord.tytul_oryginalny}, {aj.rekord_id}"
                )
                continue

            elif kolo_naukowe.count() == 1:
                aj = aj.original
                aj.jednostka = kolo_naukowe.first()
                aj.save()
                print(
                    f"Przypisano autorowi {autor} koło {kolo_naukowe.first().nazwa} "
                    f"dla pracy {aj.rekord.tytul_oryginalny}, {aj.rekord_id}"
                )
                continue

            else:
                print(
                    f"Autor {autor} ma ilość przypisań do kół = {kolo_naukowe.count()}, proszę określić ręcznie. "
                    f"Rekord {aj.rekord.tytul_oryginalny}, {aj.rekord_id}"
                )
                continue

        if dry_run:
            transaction.rollback()
