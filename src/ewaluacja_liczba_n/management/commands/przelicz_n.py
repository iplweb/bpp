from django.core.management import BaseCommand

from bpp.models import Uczelnia
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025


class Command(BaseCommand):
    """Wymusza przeliczenie liczby N dla uczelni z użyciem nowej aplikacji ewaluacja_liczba_n"""

    def handle(self, *args, **options):
        self.stdout.write("Przeliczam liczby N dla uczelni...")
        oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=Uczelnia.objects.get_default())
        self.stdout.write(self.style.SUCCESS("Przeliczono liczby N pomyślnie!"))
