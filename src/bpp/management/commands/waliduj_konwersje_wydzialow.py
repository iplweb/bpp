from django.core.management.base import BaseCommand
from django.utils import timezone

from bpp.models import Jednostka, Wydzial


class Command(BaseCommand):
    help = "Read-only skan kolizji/anomalii przed konwersją Wydzial→Jednostka."

    def handle(self, *args, **options):
        problemy = 0
        dzis = timezone.now().date()

        # Węzły już skonwertowane (legacy_wydzial_id wskazuje na Wydzial, z
        # którego powstały) mają z definicji tę samą nazwę/skrót/slug/pbn_id
        # co swój Wydzial-źródło -- to nie jest kolizja, tylko efekt
        # poprzedniej (idempotentnej) konwersji. Wykluczamy je ze zbiorów
        # porównawczych, żeby ponowne uruchomienie walidatora po konwersji
        # nie raportowało fałszywych kolizji.
        jednostki_nieskonwertowane = Jednostka.objects.filter(
            legacy_wydzial_id__isnull=True
        )

        jedn_nazwy = set(jednostki_nieskonwertowane.values_list("nazwa", flat=True))
        jedn_skroty = set(jednostki_nieskonwertowane.values_list("skrot", flat=True))
        jedn_slugi = set(jednostki_nieskonwertowane.values_list("slug", flat=True))
        jedn_skroty_nazw = set(
            jednostki_nieskonwertowane.exclude(skrot_nazwy__isnull=True)
            .exclude(skrot_nazwy="")
            .values_list("skrot_nazwy", flat=True)
        )
        jedn_pbn_idy = set(
            jednostki_nieskonwertowane.exclude(pbn_id__isnull=True).values_list(
                "pbn_id", flat=True
            )
        )

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
            if w.skrot_nazwy and w.skrot_nazwy in jedn_skroty_nazw:
                problemy += 1
                self.stdout.write(f"KOLIZJA skrot_nazwy: {w.skrot_nazwy}")
            if w.pbn_id is not None and w.pbn_id in jedn_pbn_idy:
                problemy += 1
                self.stdout.write(f"KOLIZJA pbn_id: {w.pbn_id}")
            if w.kolejnosc < 0:
                problemy += 1
                self.stdout.write(f"UJEMNA kolejnosc: {w.nazwa} = {w.kolejnosc}")
            if w.zamkniecie and w.zamkniecie > dzis:
                problemy += 1
                self.stdout.write(f"ZAMKNIECIE w przyszlosci: {w.nazwa}")

        self.stdout.write(f"Znaleziono {problemy} problemow.")
