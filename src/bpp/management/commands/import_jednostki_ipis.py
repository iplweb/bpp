from django.core.management import BaseCommand
from django.db import transaction

from import_common.core import wytnij_skrot

from bpp.models import Jednostka, Jednostka_Wydzial, Uczelnia, Wydzial


def zrob_skrot(jednostka):
    return "".join(e[0] for e in jednostka.split()).upper()


class Command(BaseCommand):
    help = (
        "Czyści dane z PBNu oraz dane z bazy BPP (autorzy, źródła, wydawcy, publikacje)"
    )

    @transaction.atomic
    def handle(self, *args, **options):

        uczelnia = Uczelnia.objects.get_default()
        wydzial = Wydzial.objects.get(skrot="WD")  # wydział domyslny
        for elem in open(
            "/Users/mpasternak/Programowanie/bpp/jednostki-uniq.txt"
        ).readlines():
            elem = elem.strip()
            if elem.startswith("-"):
                continue

            jednostka, zespol, skrot, skrot_zespolu = (None,) * 4
            try:
                jednostka, zespol = elem.split(" - ", 2)
            except ValueError:
                jednostka = elem

            jednostka, skrot = wytnij_skrot(jednostka)

            if zespol:
                zespol, skrot_zespolu = wytnij_skrot(zespol)

            print(f"{jednostka=}, {skrot=}, {zespol=}, {skrot_zespolu=}")

            if skrot is None:
                skrot = zrob_skrot(jednostka)

            jednostka = Jednostka.objects.get_or_create(
                nazwa=jednostka, skrot=skrot, uczelnia=uczelnia
            )[0]
            Jednostka_Wydzial.objects.get_or_create(
                jednostka=jednostka, wydzial=wydzial
            )

            if zespol:
                zespol = Jednostka.objects.get_or_create(
                    nazwa=zespol,
                    skrot=skrot_zespolu,
                    parent=jednostka,
                    uczelnia=uczelnia,
                )[0]
                Jednostka_Wydzial.objects.get_or_create(
                    jednostka=zespol, wydzial=wydzial
                )
