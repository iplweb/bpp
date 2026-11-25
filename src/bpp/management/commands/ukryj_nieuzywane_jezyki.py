from django.core.management import BaseCommand
from django.db import transaction

from bpp.admin.nieuzywane import nieuzywane
from bpp.models import Jezyk


class Command(BaseCommand):
    help = (
        "Ukrywa nieużywane języki (ustawia Jezyk.widoczny = False). To samo "
        "robi akcja „Ukryj wszystkie nieużywane” w Dane systemowe → Języki. "
        "Język jest używany, gdy wskazuje na niego cokolwiek w bazie "
        "(publikacja, streszczenie, tytuł, źródło…). Języków używanych "
        "polecenie nie rusza — także tych, które ktoś ukrył ręcznie."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko wyświetl co zostanie ukryte, bez zapisywania zmian",
        )

    @transaction.atomic
    def handle(self, dry_run, *args, **options):
        do_ukrycia = nieuzywane(Jezyk.objects.filter(widoczny=True))
        nazwy = list(do_ukrycia.order_by("nazwa").values_list("nazwa", flat=True))

        for nazwa in nazwy:
            self.stdout.write(f"  {nazwa}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Tryb testowy (--dry-run): {len(nazwy)} nieużywanych "
                    f"języków zostałoby ukrytych. Nic nie zostało zmienione."
                )
            )
            return

        ukryto = do_ukrycia.update(widoczny=False)
        self.stdout.write(
            self.style.SUCCESS(
                f"Ukryto {ukryto} nieużywanych języków. Widocznych pozostało: "
                f"{Jezyk.objects.filter(widoczny=True).count()}."
            )
        )
