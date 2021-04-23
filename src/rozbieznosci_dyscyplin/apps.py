import sys
import warnings

from django.apps import AppConfig
from django.db import ProgrammingError


class RozbieznosciDyscyplinConfig(AppConfig):
    name = "rozbieznosci_dyscyplin"

    def ready(self):
        # Sprawdź, czy utworzone zostały widoki, z których korzysta ta aplikacja.
        # W pewnych warunkach z powodu braku możliwości wpływu na kolejność migracji
        # może dojść do sytuacji, gdzie zostaną usunięte (np przy ponownym tworzeniu
        # tabeli bpp_rekord_mat) a nie bardzo mamy możliwość napisania testów automatycznych
        # uwzględniających kolejność migracji (mpasternak, 2.04.2021)

        from rozbieznosci_dyscyplin.models import (
            BrakPrzypisaniaView,
            RozbieznePrzypisaniaView,
            RozbieznosciView,
        )

        if ("migrate" not in sys.argv) and ("makemigrations" not in sys.argv):
            for klass in (
                BrakPrzypisaniaView,
                RozbieznePrzypisaniaView,
                RozbieznosciView,
            ):
                try:
                    klass.objects.first()
                except ProgrammingError:
                    warnings.warn(
                        "Jeden lub wszystkie z widoków dla aplikacji rozbieznosc_dyscyplin nie istnieje. "
                        "Prawdopodobnie moze miec to zwiazek z niedokonczona migracja. Prosze o weryfikacje. "
                    )
