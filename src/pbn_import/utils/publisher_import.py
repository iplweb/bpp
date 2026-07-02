"""Publisher import utilities"""

import logging

from bpp.util import zaloguj_polkniety_wyjatek
from pbn_api.models import Publisher
from pbn_integrator import importer
from pbn_integrator.utils import pobierz_wydawcow_mnisw

from .base import ImportStepBase

logger = logging.getLogger(__name__)


class PublisherImporter(ImportStepBase):
    """Import publishers from PBN"""

    step_name = "publisher_import"
    step_description = "Import wydawców"

    def download(self):
        """Pobierz wydawców z PBN (MNiSW) do lustra."""
        self.update_progress(0, 1, "Pobieranie wydawców z PBN")
        self.log("info", "Pobieranie wydawców z MNiSW")
        try:
            pobierz_wydawcow_mnisw(self.client)
            self.log("success", "Wydawcy pobrani pomyślnie")
        except Exception as e:
            zaloguj_polkniety_wyjatek(
                "Nie udało się pobrać wydawców z MNiSW",
                logger=logger,
                do_rollbar=False,  # Rollbar już w handle_error
            )
            self.handle_error(e, "Nie udało się pobrać wydawców")
        self.update_progress(1, 1, "Zakończono pobieranie wydawców")
        return {"publishers_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj wydawców z lustra do BPP."""
        if not Publisher.objects.exists():
            self.log(
                "warning",
                "Brak pobranych wydawców — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Importowanie wydawców do bazy danych")
        self.log("info", "Importowanie wydawców do bazy danych")
        subtask_callback = self.create_subtask_progress("Importowanie wydawców")
        try:
            result = importer.importuj_wydawcow(callback=subtask_callback)
            if hasattr(self.session, "statistics") and isinstance(result, (int, float)):
                stats = self.session.statistics
                stats.publishers_imported = int(result)
                stats.save()
            self.log("success", "Wydawcy zaimportowani pomyślnie")
        except Exception as e:
            zaloguj_polkniety_wyjatek(
                "Nie udało się zaimportować wydawców do bazy danych",
                logger=logger,
                do_rollbar=False,  # Rollbar już w handle_error
            )
            self.handle_error(e, "Nie udało się zaimportować wydawców")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono import wydawców")
        return {"publishers_imported": True, "error_count": len(self.errors)}
