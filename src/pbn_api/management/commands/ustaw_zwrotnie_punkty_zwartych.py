from tqdm import tqdm

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Wydawnictwo_Zwarte


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--min-rok", type=int, default=2022)

    def handle(self, min_rok, *args, **kw):
        punkty_dct = [
            {"KS": 20, "RED": 5, "ROZ": 5},
            {"KS": 80, "RED": 20, "ROZ": 20},
            {"KS": 200, "RED": 100, "ROZ": 50},
        ]

        for elem in tqdm(Wydawnictwo_Zwarte.objects.filter(rok__gte=min_rok)):
            poziom_wydawcy = elem.wydawca.get_tier(elem.rok)
            if poziom_wydawcy == -1:
                poziom_wydawcy = 0

            values = punkty_dct[poziom_wydawcy]

            rozdzial = elem.warunek_rozdzial()
            ksiazka = elem.warunek_ksiazka()

            if ksiazka and rozdzial:
                raise NotImplementedError("To sie nie powinno wydarzyc)")

            autorstwo = elem.warunek_autorstwo()
            redakcja = elem.warunek_redakcja()

            if ksiazka and autorstwo:
                punkty_pk = values["KS"]
            elif ksiazka and redakcja:
                punkty_pk = values["RED"]
            elif rozdzial and autorstwo:
                punkty_pk = values["ROZ"]
            else:
                print(
                    f"NIE ZAIMPLEMENTOWANO  {ksiazka=} {rozdzial=} {redakcja=} {autorstwo=}"
                )
                print(elem)
                print(elem.autorzy_set.all())
                print("=" * 80)
                continue

            elem.punkty_kbn = punkty_pk
            elem.save()
