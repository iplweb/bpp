# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Punktacja_Zrodla


class Command(BaseCommand):
    help = "Ustawia punktacje dla niektorych typow prac"

    @transaction.atomic
    def handle(self, *args, **options):

        for praca in Wydawnictwo_Ciagle.objects.exclude(zrodlo=None).order_by("-rok"):
            try:
                punktacja = praca.zrodlo.punktacja_zrodla_set.get(rok=praca.rok)

                if (
                    punktacja.impact_factor != praca.impact_factor
                    or punktacja.punkty_kbn != praca.punkty_kbn
                ):
                    print(
                        f"Punkty pomiedzy praca {praca.tytul_oryginalny} a zrodlem {praca.zrodlo.nazwa} "
                        f"roznia sie {punktacja.impact_factor} != {praca.impact_factor} lub {punktacja.punkty_kbn} "
                        f"!= {praca.punkty_kbn}"
                    )
            except Punktacja_Zrodla.DoesNotExist:
                # Teoretycznie możnaby tą punktację wpisać...

                punkty_kbn = praca.punkty_kbn
                impact_factor = praca.impact_factor

                if punkty_kbn == 0 and impact_factor == 0:
                    continue

                # Sprawdźmy, czy inne wydawnictwa w tym źródle, w tym roku, mają taką samą punktację:
                inne = Wydawnictwo_Ciagle.objects.filter(
                    rok=praca.rok,
                    zrodlo=praca.zrodlo,
                ).exclude(pk=praca.pk)

                can_set = True

                if inne.exists:
                    for elem in inne:
                        if (
                            elem.impact_factor != 0
                            and elem.impact_factor != impact_factor
                        ) or (elem.punkty_kbn != 0 and elem.punkty_kbn != punkty_kbn):
                            print(
                                f"Dla roku {praca.rok} i pracy {praca.tytul_oryginalny}, inny rekord czyli "
                                f"{elem.tytul_oryginalny} punkty sie roznia {impact_factor} vs {elem.impact_factor}, "
                                f"{punkty_kbn} vs {elem.punkty_kbn}. "
                            )
                            can_set = False

                if can_set:
                    praca.zrodlo.punktacja_zrodla_set.create(
                        rok=praca.rok,
                        impact_factor=impact_factor,
                        punkty_kbn=punkty_kbn,
                    )
                    praca.save()
                    print(
                        f"Tworze punktacje zrodla {praca.zrodlo} dla roku {praca.rok} na bazie rekordu "
                        f"{praca.tytul_oryginalny}, PK={punkty_kbn}, impact_factor={impact_factor}"
                    )
