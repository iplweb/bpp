import logging

from denorm import denorms
from django.core.management import BaseCommand
from django.db import transaction

from bpp.const import PBN_MIN_ROK
from bpp.models import Praca_Doktorska, Praca_Habilitacyjna, Wydawca, Wydawnictwo_Zwarte

logger = logging.getLogger("pbn_import")


class Command(BaseCommand):
    help = "Znajduje wydawców indeksowanych"

    @transaction.atomic
    def handle(self, *args, **options):
        wydawcy = list(Wydawca.objects.all())
        total = len(wydawcy)
        logger.info(f"Mapowanie wydawców: {total} wydawców do przetworzenia")

        for i, wydawca in enumerate(wydawcy, 1):
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
                                f"Ciąg znaków {stare_wydawnictwo!r} przypisuję do "
                                f"indeksowanego wydawcy ID {wydawca.pk} nazwa "
                                f"{wydawca.nazwa!r} ({model.pk!r} ID "
                                f"{model.tytul_oryginalny})"
                            )
                        model.save()

            if i % 50 == 0 or i == total:
                logger.info(f"  Mapowanie wydawców: {i}/{total}")

        logger.info("Mapowanie wydawców: odświeżanie denormalizacji...")
        denorms.flush()
        logger.info("Mapowanie wydawców: zakończone")
