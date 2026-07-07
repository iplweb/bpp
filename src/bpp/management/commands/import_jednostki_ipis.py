from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Jednostka, Jednostka_Rodzic, Uczelnia, Wydzial
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu
from import_common.core import wytnij_skrot


def zrob_skrot(jednostka):
    return "".join(e[0] for e in jednostka.split()).upper()


class Command(BaseCommand):
    help = (
        "Czyści dane z PBNu oraz dane z bazy BPP (autorzy, źródła, wydawcy, publikacje)"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--uczelnia-id",
            type=int,
            default=None,
            help=("ID uczelni (domyślnie: pierwsza uczelnia w bazie)"),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        uczelnia_id = options.get("uczelnia_id")
        if uczelnia_id:
            uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
        else:
            uczelnia = Uczelnia.objects.get()
        wydzial = Wydzial.objects.get(skrot="WD")  # wydział domyslny
        # Faza B (#438): wpisy metryczki wskazują węzeł-rodzic (Jednostka);
        # LAZY resolve wydział → węzeł-lustro (tworzony tu, jeśli brak).
        wezel_wydzialu, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
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
            Jednostka_Rodzic.objects.get_or_create(
                jednostka=jednostka, parent=wezel_wydzialu
            )

            if zespol:
                zespol = Jednostka.objects.get_or_create(
                    nazwa=zespol,
                    skrot=skrot_zespolu,
                    parent=jednostka,
                    uczelnia=uczelnia,
                )[0]
                Jednostka_Rodzic.objects.get_or_create(
                    jednostka=zespol, parent=wezel_wydzialu
                )
