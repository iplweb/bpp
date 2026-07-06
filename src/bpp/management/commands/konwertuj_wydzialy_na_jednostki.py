from django.core.management.base import BaseCommand
from django.db import transaction

from bpp.models import Jednostka, RodzajJednostki, Wydzial


class Command(BaseCommand):
    help = "Konwertuje Wydzial na ukryte wezly Jednostka (faza A, idempotentne)."

    @transaction.atomic
    def handle(self, *args, **options):
        rodzaj_wydzial = RodzajJednostki.objects.get(nazwa="Wydział")
        utworzone = 0
        for w in Wydzial.objects.all():
            if Jednostka.objects.filter(legacy_wydzial_id=w.id).exists():
                continue
            Jednostka.objects.create(
                nazwa=w.nazwa,
                skrot=w.skrot,
                skrot_nazwy=w.skrot_nazwy,
                opis=w.opis,
                adnotacje=w.adnotacje,
                poprzednie_nazwy=w.poprzednie_nazwy,
                pbn_id=w.pbn_id,
                uczelnia=w.uczelnia,
                rodzaj=rodzaj_wydzial,
                legacy_wydzial_id=w.id,
                parent=None,
                widoczna=False,
                aktualna=False,
                zezwalaj_na_ranking_autorow=w.zezwalaj_na_ranking_autorow,
                pokazuj_opis=w.pokazuj_opis,
                zarzadzaj_automatycznie=w.zarzadzaj_automatycznie,
                kolejnosc=max(0, w.kolejnosc),
            )
            utworzone += 1
        self.stdout.write(f"Utworzono {utworzone} wezlow-wydzialow.")
