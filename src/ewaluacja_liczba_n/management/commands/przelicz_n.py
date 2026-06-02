from django.core.management import BaseCommand

from bpp.models import Uczelnia
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025


class Command(BaseCommand):
    """Wymusza przeliczenie liczby N dla uczelni z użyciem nowej aplikacji ewaluacja_liczba_n"""

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--uczelnia-id",
            type=int,
            default=None,
            help="ID uczelni (domyślnie: pierwsza uczelnia w bazie)",
        )

    def handle(self, *args, **options):
        uczelnia_id = options.get("uczelnia_id")
        if uczelnia_id:
            uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
        else:
            uczelnia = Uczelnia.objects.get()

        self.stdout.write("Przeliczam liczby N dla uczelni...")
        oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
        self.stdout.write(self.style.SUCCESS("Przeliczono liczby N pomyślnie!"))
