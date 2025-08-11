from django.core.management import BaseCommand

from bpp.models import Uczelnia
from bpp.models.cache.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025


class Command(BaseCommand):
    """Wymusza przeliczenie liczby N dla uczelni"""

    def handle(self, *args, **options):
        oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=Uczelnia.objects.get_default())
