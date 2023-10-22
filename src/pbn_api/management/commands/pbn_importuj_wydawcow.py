from django.core.management import call_command
from django.db import transaction

from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import Publisher

from bpp.const import PBN_LATA
from bpp.models import Wydawca

poziom_to_points_map = {2: 200, 1: 80}
points_to_poziom_map = {200: 2, 80: 1}


class Command(PBNBaseCommand):
    def handle(self, verbosity=1, *args, **options):
        needs_mapping = False
        needs_recalc = set()

        with transaction.atomic():
            for publisher in Publisher.objects.official():
                if not publisher.wydawca_set.exists():
                    # Nie ma takiego wydawcy w bazie BPP, spróbuj go zmatchować:

                    nw = publisher.matchuj_wydawce()
                    if nw is not None:
                        if publisher.publisherName != nw.nazwa:
                            print(
                                f"0 ZWERYFIKUJ FONETYCZNE DOPASOWANIE: {publisher.publisherName} do {nw.nazwa}"
                            )
                        nw.pbn_uid = publisher
                        nw.save()

                if not publisher.wydawca_set.exists():
                    # Nie ma takiego wydawcy w bazie, utwórz go:

                    nowy_wydawca = Wydawca.objects.create(
                        nazwa=publisher.publisherName, pbn_uid=publisher
                    )
                    if verbosity > 1:
                        print(
                            f"1 Tworze nowego wydawce z MNISWID, {publisher.publisherName}"
                        )

                    for rok in PBN_LATA:
                        points = publisher.points.get(str(rok))

                        if not points:
                            # Brak punktów w PBNie za dany rok
                            continue

                        if not points["accepted"]:
                            raise NotImplementedError(
                                f"Accepted = False dla {publisher} {rok}, co dalej?"
                            )

                        poziom = points_to_poziom_map.get(points["points"])
                        assert poziom, f"Brak odpowiednika dla {points['points']}"

                        nowy_wydawca.poziom_wydawcy_set.create(rok=rok, poziom=poziom)

                    needs_mapping = True
                    continue

                # Jest już taki wydawca i ma ustawiony match z PBN. Sprawdzimy mu jego poziomy:
                for wydawca in publisher.wydawca_set.all():
                    # Nie pracujemy na aliasach
                    wydawca = wydawca.get_toplevel()

                    for rok in PBN_LATA:
                        pbn_side = publisher.points.get(str(rok))

                        wydawca_side = wydawca.poziom_wydawcy_set.filter(
                            rok=rok
                        ).first()

                        if pbn_side is not None:
                            if not pbn_side["accepted"]:
                                raise NotImplementedError(
                                    f"Accepted = False dla {publisher} {rok}, co dalej?"
                                )

                            if wydawca_side is None:
                                # Nie ma poziomu po naszej stronie dla tego rkou ,dodamy go:
                                poziom_bpp = self.get_poziom_bpp(pbn_side)

                                if verbosity > 1:
                                    print(
                                        f"2 Wydawca {wydawca}: dodaje poziom {poziom_bpp} za {rok} "
                                    )

                                wydawca.poziom_wydawcy_set.create(
                                    rok=rok, poziom=poziom_bpp
                                )
                                needs_recalc.add((wydawca, rok))
                                continue

                            # Są obydwa poziomy: Publisher (PBN) i Wydawca (BPP)
                            # porównaj, czy są ok:

                            wydawca_side_poziom_translated = poziom_to_points_map.get(
                                wydawca_side.poziom
                            )

                            if pbn_side["points"] != wydawca_side_poziom_translated:
                                if verbosity > 1:
                                    print(
                                        f"5 Poziomy sie roznia dla {publisher} {rok}, ustawiam poziom z PBNu?"
                                    )
                                    wydawca_side.poziom = self.get_poziom_bpp(pbn_side)
                                    needs_recalc.add((wydawca, rok))

                                    wydawca_side.save()
                                    continue

                        else:
                            # pbn_side is None
                            if wydawca_side is not None:
                                print(
                                    f"4 PBN nie ma poziomu a wydawca ma, co robic? {publisher} {rok}"
                                )

                            # wydawca_side is None, są równe zatem, nic nie robimy

        # To uruchamiamy poza transakcją - jeżeli były zmiany
        if needs_mapping:
            call_command("zamapuj_wydawcow")

    def get_poziom_bpp(self, pbn_side):
        poziom_bpp = points_to_poziom_map.get(pbn_side["points"])
        if not poziom_bpp:
            raise NotImplementedError(
                f"Brak odpowiednika poziomu {pbn_side['points']} w mappingu"
            )
        return poziom_bpp
