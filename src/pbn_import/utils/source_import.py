"""Source (journal) import utilities"""

from pbn_integrator import importer
from pbn_integrator.utils import pobierz_zrodla_mnisw

from .base import ImportStepBase


class SourceImporter(ImportStepBase):
    """Import sources/journals from PBN"""

    step_name = "source_import"
    step_description = "Import źródeł (czasopism)"

    def run(self):
        """Import sources"""
        # Download sources from PBN
        self.update_progress(0, 2, "Pobieranie źródeł z PBN")
        self.log("info", "Pobieranie źródeł z MNiSW")

        # Create progress callback for sub-task tracking
        subtask_callback = self.create_subtask_progress("Pobieranie źródeł MNiSW")

        try:
            pobierz_zrodla_mnisw(self.client, callback=subtask_callback)
            self.log("info", "Źródła pobrane pomyślnie")
        except Exception as e:
            # Use the new method that handles authorization errors properly
            self.handle_pbn_error(e, "Nie udało się pobrać źródeł")
            # If we're here, it's not an authorization error
            self.log("warning", "Kontynuacja z częściowymi danymi")
        finally:
            # Clear subtask progress when done
            self.clear_subtask_progress()

        # Import sources to database
        self.update_progress(1, 2, "Importowanie źródeł do bazy danych")
        self.log("info", "Importowanie źródeł do bazy danych")

        try:
            result = importer.importuj_zrodla()

            # Get statistics if available
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                # Assuming result contains count
                if isinstance(result, (int, float)):
                    stats.journals_imported = int(result)
                    stats.save()

            self.log("success", "Źródła zaimportowane pomyślnie")

        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować źródeł")
            # This is also critical, so raise
            raise

        self.update_progress(2, 2, "Zakończono import źródeł")

        return {"sources_imported": True, "error_count": len(self.errors)}
