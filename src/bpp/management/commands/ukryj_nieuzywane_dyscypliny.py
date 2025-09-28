from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Autor_Dyscyplina,
    Autorzy,
    Dyscyplina_Naukowa,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)


class Command(BaseCommand):
    help = "Ukrywa nieużywane dyscypliny naukowe (ustawia Dyscyplina_Naukowa.widoczna = False)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko wyświetl co zostanie ukryte, bez zapisywania zmian",
        )

    @transaction.atomic
    def handle(self, dry_run, *args, **options):

        self.stdout.write("Przetwarzanie dyscyplin naukowych...")

        # Najpierw ukryj wszystkie dyscypliny
        wszystkie = Dyscyplina_Naukowa.objects.all()
        liczba_wszystkich = wszystkie.count()
        liczba_widocznych_przed = wszystkie.filter(widoczna=True).count()

        if not dry_run:
            wszystkie.update(widoczna=False)
            self.stdout.write(f"  Ukryto wszystkie {liczba_wszystkich} dyscyplin")

        # Znajdź używane dyscypliny
        uzywane_ids = set()

        # Z tabeli Autor_Dyscyplina
        self.stdout.write("  Sprawdzam przypisania dyscyplin do autorów...")
        for dyscyplina_id in Autor_Dyscyplina.objects.exclude(
            dyscyplina_naukowa=None
        ).values_list("dyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        for dyscyplina_id in Autor_Dyscyplina.objects.exclude(
            subdyscyplina_naukowa=None
        ).values_list("subdyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        # Z tabeli Autorzy (cache autorów)
        self.stdout.write("  Sprawdzam cache autorów...")
        for dyscyplina_id in Autorzy.objects.exclude(
            dyscyplina_naukowa=None
        ).values_list("dyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        # Z wydawnictw ciągłych - autorzy
        for dyscyplina_id in Wydawnictwo_Ciagle_Autor.objects.exclude(
            dyscyplina_naukowa=None
        ).values_list("dyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        # Z wydawnictw zwartych - autorzy
        for dyscyplina_id in Wydawnictwo_Zwarte_Autor.objects.exclude(
            dyscyplina_naukowa=None
        ).values_list("dyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        # Z patentów - autorzy
        self.stdout.write("  Sprawdzam patenty...")
        for dyscyplina_id in Patent_Autor.objects.exclude(
            dyscyplina_naukowa=None
        ).values_list("dyscyplina_naukowa_id", flat=True):
            uzywane_ids.add(dyscyplina_id)

        # Pokaż używane dyscypliny
        if uzywane_ids:
            uzywane = Dyscyplina_Naukowa.objects.filter(id__in=uzywane_ids)
            if not dry_run:
                uzywane.update(widoczna=True)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  Oznaczono jako widoczne {len(uzywane_ids)} używanych dyscyplin"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  Znaleziono {len(uzywane_ids)} używanych dyscyplin (zostaną oznaczone jako widoczne)"
                    )
                )

        nieuzywane_count = liczba_wszystkich - len(uzywane_ids)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nPodsumowanie (tryb testowy):"
                    f"\n  Wszystkich dyscyplin: {liczba_wszystkich}"
                    f"\n  Obecnie widocznych: {liczba_widocznych_przed}"
                    f"\n  Używanych (będą widoczne): {len(uzywane_ids)}"
                    f"\n  Nieużywanych (będą ukryte): {nieuzywane_count}"
                    f"\n\nTo był tryb testowy (--dry-run). Żadne zmiany nie zostały zapisane."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nPodsumowanie:"
                    f"\n  Wszystkich dyscyplin: {liczba_wszystkich}"
                    f"\n  Widocznych po operacji: {len(uzywane_ids)}"
                    f"\n  Ukrytych: {nieuzywane_count}"
                )
            )
