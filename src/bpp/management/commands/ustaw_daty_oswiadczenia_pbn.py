"""
Management command do ustawiania daty oświadczenia PBN dla autorów publikacji.

Polecenie ustawia datę oświadczenia (data_oswiadczenia) w obiektach
Wydawnictwo_Ciagle_Autor oraz Wydawnictwo_Zwarte_Autor na datę utworzenia
nadrzędnego rekordu (rekord.utworzono) dla rekordów, gdzie data oświadczenia
jest pusta (NULL).
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor


class Command(BaseCommand):
    help = """
    Ustawia datę oświadczenia PBN dla autorów publikacji na datę utworzenia rekordu.

    Polecenie aktualizuje pole data_oswiadczenia w obiektach Wydawnictwo_Ciagle_Autor
    oraz Wydawnictwo_Zwarte_Autor, ustawiając je na datę utworzenia nadrzędnego rekordu
    (rekord.utworzono) dla wszystkich rekordów, gdzie data oświadczenia jest pusta oraz
    gdzie rok opublikowania rekordu jest większy lub równy 2022.

    Przykład użycia:
        python src/manage.py ustawienie_daty_oswiadczenia_pbn
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Wyświetl tylko informacje o rekordach do zaktualizowania, nie wykonuj zmian",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "TRYB TESTOWY - żadne zmiany nie zostaną zapisane w bazie danych"
                )
            )

        for klass in Wydawnictwo_Ciagle_Autor.objects, Wydawnictwo_Zwarte_Autor.objects:
            objs = klass.filter(
                data_oswiadczenia__isnull=True, rekord__rok__gte=2022
            ).select_related("rekord")

            for obj in tqdm(objs, desc=str(klass)):
                obj.data_oswiadczenia = obj.rekord.utworzono.date()
                obj.save()

        if dry_run:
            # Anuluj transakcję w trybie testowym
            raise transaction.TransactionManagementError(
                "Dry run mode - rollback transaction"
            )
