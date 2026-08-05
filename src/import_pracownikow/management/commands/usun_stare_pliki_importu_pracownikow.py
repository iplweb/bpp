from django.core.management.base import BaseCommand

from import_pracownikow.tasks import usun_stare_pliki_importu


class Command(BaseCommand):
    help = "Kasuje blob plik_xls importów starszych niż retencja (zostawia rekord)."

    def handle(self, *args, **options):
        # Logika żyje w tasks.usun_stare_pliki_importu — ta sama ścieżka kodu,
        # co zadanie cykliczne Celery, żeby komenda i beat nie mogły się
        # rozjechać.
        n = usun_stare_pliki_importu()
        self.stdout.write(f"Skasowano blobów: {n}")
