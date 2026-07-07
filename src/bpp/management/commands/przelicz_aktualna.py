"""Faza B / issue #438 — IV-1: ręczne przeliczenie ``Jednostka.aktualna``.

Re-runnable komenda stosująca FINALNĄ logikę ``aktualna`` (patrz
``bpp.models.jednostka.wylicz_aktualna``) na WSZYSTKICH jednostkach —
przydatna po masowych zmianach historii ``Jednostka_Rodzic`` lub do
naprawy driftu. Daje IDENTYCZNY wynik co jednorazowe przeliczenie w
migracji ``0462`` (obie wołają tę samą logikę derywacji).
"""

from django.core.management.base import BaseCommand

from bpp.models.jednostka import przelicz_aktualna_wszystkich


class Command(BaseCommand):
    help = "Przelicza pole Jednostka.aktualna z historii (Jednostka_Rodzic)."

    def handle(self, *args, **options):
        zmienione = przelicz_aktualna_wszystkich()
        self.stdout.write(
            self.style.SUCCESS(
                f"Przeliczono aktualna dla wszystkich jednostek "
                f"({zmienione} zmienionych)."
            )
        )
