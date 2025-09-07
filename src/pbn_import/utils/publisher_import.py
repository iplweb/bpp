"""Publisher import utilities"""

from pbn_integrator import importer
from pbn_integrator.utils import pobierz_wydawcow_mnisw
from .base import ImportStepBase


class PublisherImporter(ImportStepBase):
    """Import publishers from PBN"""

    step_name = "publisher_import"
    step_description = "Import wydawców"

    def run(self):
        """Import publishers"""
        # Download publishers from PBN
        self.update_progress(0, 2, "Pobieranie wydawców z PBN")
        self.log("info", "Pobieranie wydawców z MNiSW")

        try:
            pobierz_wydawcow_mnisw(self.client)
            self.log("info", "Publishers downloaded successfully")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać wydawców")
            # Continue anyway - might have partial data

        # Import publishers to database
        self.update_progress(1, 2, "Importowanie wydawców do bazy danych")
        self.log("info", "Importing publishers to database")

        try:
            result = importer.importuj_wydawcow()

            # Update statistics if available
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                if isinstance(result, (int, float)):
                    stats.publishers_imported = int(result)
                    stats.save()

            self.log("success", "Publishers imported successfully")

        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować wydawców")

        self.update_progress(2, 2, "Zakończono import wydawców")

        return {"publishers_imported": True, "error_count": len(self.errors)}
