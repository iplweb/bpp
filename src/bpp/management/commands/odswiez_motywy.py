"""Migracja wyglądu: przebudowa motywów z konfiguratora po aktualizacji BPP.

Zapisany CSS powstał z SCSS-a wersji BPP z chwili „Zastosuj”. Po
aktualizacji przebudowujemy go z zapisanych ustawień — administrator już je
zatwierdził, więc nie pytamy go ponownie. Uruchamiane przy starcie kontenera
(docker/appserver/entrypoint-appserver.sh), można też ręcznie.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from bpp.models import MotywWlasny
from bpp.motyw_kompilator import (
    BladKompilacjiMotywu,
    czekaj_na_kompilator,
    kompiluj,
)
from django_bpp.version import VERSION

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Przebudowuje motywy z konfiguratora wyglądu zapisane w starszej wersji BPP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wszystkie",
            action="store_true",
            help="Przebuduj wszystkie motywy, także zbudowane w bieżącej wersji.",
        )

    def handle(self, *args, wszystkie=False, **options):
        # Tylko zastosowane motywy; sam motyw roboczy czeka na „Zastosuj”.
        motywy = MotywWlasny.objects.select_related("uczelnia").exclude(css="")
        if not wszystkie:
            motywy = motywy.exclude(wersja_bpp=VERSION)

        if not motywy.exists():
            return
        if not czekaj_na_kompilator():
            raise CommandError(
                "Kompilator motywów nie odpowiada (serwis motyw-kompilator) — "
                "motywy zostają bez przebudowy."
            )

        nieudane = []
        for motyw in motywy:
            try:
                # Czeka na swoją kolej, gdyby akurat trwało „Zastosuj”.
                css = kompiluj(motyw.konfig, czekaj_s=180)
            except BladKompilacjiMotywu:
                # Jeden zepsuty motyw nie blokuje pozostałych; stary CSS zostaje.
                logger.exception("Nie udało się przebudować motywu %s", motyw)
                nieudane.append(str(motyw))
                continue
            motyw.css = css
            motyw.wersja_bpp = VERSION
            motyw.save(update_fields=["css", "skrot", "wersja_bpp", "zmieniono"])
            self.stdout.write(f"Przebudowano: {motyw} (wersja {VERSION}).")

        if nieudane:
            raise CommandError(
                "Nie udało się przebudować: " + ", ".join(nieudane) + " — patrz log."
            )
