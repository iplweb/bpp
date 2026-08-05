import argparse

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    parse_informacje_as_dict,
    wez_zakres_stron,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = "Ustawia parametry strony, tom, nr zeszytu dla prac >= 2010 roku, jeżeli nie ustawione"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction)

    def ustaw_atrybut(self, obiekt, atrybut, wartosc):
        if wartosc is None:
            return

        obecny = getattr(obiekt, atrybut)
        if obecny is None or obecny == "":
            print(
                f"+{obiekt.pk}: {obiekt.tytul_oryginalny}: {atrybut} ustawione na {wartosc}"
            )
            setattr(obiekt, atrybut, wartosc)
            return True
        else:
            if obecny != wartosc:
                print(
                    f"-{obiekt.pk}: {obiekt.tytul_oryginalny}: {atrybut} obecny: {obecny}, "
                    f"ze szczegolow {wartosc}, nie zmieniam"
                )

    @transaction.atomic
    def handle(self, dry_run, *args, **options):
        for klass in (
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Patent,
        ):
            q = (
                klass.objects.exclude(szczegoly="")
                .exclude(szczegoly=None)
                .exclude(rok__lt=2010)
            )

            for rekord in q:
                res = parse_informacje_as_dict(rekord.informacje)

                save = False

                if self.ustaw_atrybut(rekord, "tom", res.get("tom")):
                    save = True

                if klass not in [Wydawnictwo_Zwarte]:
                    if self.ustaw_atrybut(rekord, "nr_zeszytu", res.get("numer")):
                        save = True

                strony = wez_zakres_stron(rekord.szczegoly)
                pole = "szczegoly"

                if strony:
                    if rekord.strony is not None and rekord.strony != "":
                        if rekord.strony != strony:
                            print(
                                f"-{rekord.pk}: {rekord.tytul_oryginalny} strony obecnie to {rekord.strony}, "
                                f"wartosc z pola {pole} to {strony} ({getattr(rekord,pole)}), nie zmieniam"
                            )
                    else:
                        print(
                            f"+{rekord.pk}: {rekord.tytul_oryginalny}: strony ustawione na {strony} "
                            f"na podstawie pola {pole} ({getattr(rekord, pole)})"
                        )

                        rekord.strony = strony
                        save = True

                if save and not dry_run:
                    rekord.save()
