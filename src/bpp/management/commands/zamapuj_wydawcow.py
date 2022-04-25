from denorm import denorms
from django.core.management import BaseCommand
from django.db import transaction

from bpp.const import PBN_MIN_ROK
from bpp.models import Praca_Doktorska, Praca_Habilitacyjna, Wydawca, Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = "Znajduje wydawców indeksowanych"

    @transaction.atomic
    def handle(self, *args, **options):
        for wydawca in Wydawca.objects.all():
            for klass in Wydawnictwo_Zwarte, Praca_Doktorska, Praca_Habilitacyjna:

                for model in klass.objects.filter(
                    wydawca=None, rok__gte=PBN_MIN_ROK
                ).filter(wydawca_opis__istartswith=wydawca.nazwa):

                    stare_wydawnictwo = model.wydawnictwo
                    model.wydawca = wydawca
                    model.wydawca_opis = model.wydawca_opis[
                        len(wydawca.nazwa) :
                    ].strip()
                    if stare_wydawnictwo.strip().lower() != model.wydawnictwo.lower():
                        print(
                            f"Nie zgadza mi sie: rekord {model} stare wydawnictwo z nowym: "
                            f"{stare_wydawnictwo} != {model.wydawnictwo}, nie zapisuję"
                        )
                    else:
                        if stare_wydawnictwo != wydawca.nazwa:
                            print(
                                "Ciąg znaków %r przypisuję do indeksowanego wydawcy ID %i nazwa %r (%r ID %s)"
                                % (
                                    stare_wydawnictwo,
                                    wydawca.pk,
                                    wydawca.nazwa,
                                    model.pk,
                                    model.tytul_oryginalny,
                                )
                            )
                        model.save()

        denorms.flush()
