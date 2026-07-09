from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from import_pracownikow.models import ImportPracownikow


class Command(BaseCommand):
    help = "Kasuje blob plik_xls importów starszych niż retencja (zostawia rekord)."

    def handle(self, *args, **options):
        dni = getattr(settings, "IMPORT_PRACOWNIKOW_RETENCJA_DNI", 90)
        prog = timezone.now() - timedelta(days=dni)
        qs = ImportPracownikow.objects.filter(created_on__lt=prog).exclude(plik_xls="")
        n = 0
        for imp in qs:
            imp.plik_xls.delete(save=False)
            imp.plik_xls = ""
            imp.save(update_fields=["plik_xls"])
            n += 1
        self.stdout.write(f"Skasowano blobów: {n}")
