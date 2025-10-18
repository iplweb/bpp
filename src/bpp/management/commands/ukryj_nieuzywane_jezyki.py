from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Jezyk,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Zrodlo,
)


class Command(BaseCommand):
    help = "Ukrywa nieużywane języki (ustawia Jezyk.widoczny = False)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko wyświetl co zostanie ukryte, bez zapisywania zmian",
        )

    @transaction.atomic
    def handle(self, dry_run, *args, **options):
        self.stdout.write("Przetwarzanie języków...")

        # Najpierw ukryj wszystkie języki
        wszystkie = Jezyk.objects.all()
        liczba_wszystkich = wszystkie.count()
        liczba_widocznych_przed = wszystkie.filter(widoczny=True).count()

        if not dry_run:
            wszystkie.update(widoczny=False)
            self.stdout.write(f"  Ukryto wszystkie {liczba_wszystkich} języków")

        # Znajdź używane języki
        uzywane_ids = set()

        # Ze źródeł
        self.stdout.write("  Sprawdzam źródła...")
        for z in Zrodlo.objects.exclude(jezyk=None).values_list("jezyk_id", flat=True):
            uzywane_ids.add(z)

        # Z wydawnictw ciągłych
        self.stdout.write("  Sprawdzam wydawnictwa ciągłe...")
        for jezyk_id in Wydawnictwo_Ciagle.objects.exclude(jezyk=None).values_list(
            "jezyk_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Wydawnictwo_Ciagle.objects.exclude(jezyk_alt=None).values_list(
            "jezyk_alt_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Wydawnictwo_Ciagle.objects.exclude(jezyk_orig=None).values_list(
            "jezyk_orig_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)

        # Z wydawnictw zwartych
        self.stdout.write("  Sprawdzam wydawnictwa zwarte...")
        for jezyk_id in Wydawnictwo_Zwarte.objects.exclude(jezyk=None).values_list(
            "jezyk_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Wydawnictwo_Zwarte.objects.exclude(jezyk_alt=None).values_list(
            "jezyk_alt_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Wydawnictwo_Zwarte.objects.exclude(jezyk_orig=None).values_list(
            "jezyk_orig_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)

        # Z prac doktorskich
        self.stdout.write("  Sprawdzam prace doktorskie...")
        for jezyk_id in Praca_Doktorska.objects.exclude(jezyk=None).values_list(
            "jezyk_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Praca_Doktorska.objects.exclude(jezyk_alt=None).values_list(
            "jezyk_alt_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Praca_Doktorska.objects.exclude(jezyk_orig=None).values_list(
            "jezyk_orig_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)

        # Z prac habilitacyjnych
        self.stdout.write("  Sprawdzam prace habilitacyjne...")
        for jezyk_id in Praca_Habilitacyjna.objects.exclude(jezyk=None).values_list(
            "jezyk_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Praca_Habilitacyjna.objects.exclude(jezyk_alt=None).values_list(
            "jezyk_alt_id", flat=True
        ):
            uzywane_ids.add(jezyk_id)
        for jezyk_id in Praca_Habilitacyjna.objects.exclude(
            jezyk_orig=None
        ).values_list("jezyk_orig_id", flat=True):
            uzywane_ids.add(jezyk_id)

        # Pokaż używane języki
        if uzywane_ids:
            uzywane = Jezyk.objects.filter(id__in=uzywane_ids)
            if not dry_run:
                uzywane.update(widoczny=True)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  Oznaczono jako widoczne {len(uzywane_ids)} używanych języków"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  Znaleziono {len(uzywane_ids)} używanych języków (zostaną oznaczone jako widoczne)"
                    )
                )

        nieuzywane_count = liczba_wszystkich - len(uzywane_ids)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nPodsumowanie (tryb testowy):"
                    f"\n  Wszystkich języków: {liczba_wszystkich}"
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
                    f"\n  Wszystkich języków: {liczba_wszystkich}"
                    f"\n  Widocznych po operacji: {len(uzywane_ids)}"
                    f"\n  Ukrytych: {nieuzywane_count}"
                )
            )
