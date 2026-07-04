from django.core.management.base import BaseCommand
from django.utils import timezone

from bpp.models import Jednostka, Wydzial


class Command(BaseCommand):
    help = "Read-only skan kolizji/anomalii przed konwersją Wydzial→Jednostka."

    def handle(self, *args, **options):
        problemy = 0
        dzis = timezone.now().date()

        jedn_nazwy = set(Jednostka.objects.values_list("nazwa", flat=True))
        jedn_skroty = set(Jednostka.objects.values_list("skrot", flat=True))
        jedn_slugi = set(Jednostka.objects.values_list("slug", flat=True))

        for w in Wydzial.objects.all():
            if w.nazwa in jedn_nazwy:
                problemy += 1
                self.stdout.write(f"KOLIZJA nazwa: {w.nazwa}")
            if w.skrot in jedn_skroty:
                problemy += 1
                self.stdout.write(f"KOLIZJA skrot: {w.skrot}")
            if w.slug in jedn_slugi:
                problemy += 1
                self.stdout.write(f"KOLIZJA slug: {w.slug}")
            if w.kolejnosc < 0:
                problemy += 1
                self.stdout.write(f"UJEMNA kolejnosc: {w.nazwa} = {w.kolejnosc}")
            if w.zamkniecie and w.zamkniecie > dzis:
                problemy += 1
                self.stdout.write(f"ZAMKNIECIE w przyszlosci: {w.nazwa}")

        self.stdout.write(f"Znaleziono {problemy} problemow.")
