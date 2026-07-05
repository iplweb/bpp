"""Source (journal) import utilities"""

from pbn_api.models import Journal
from pbn_integrator import importer
from pbn_integrator.utils import pobierz_zrodla_mnisw

from .base import ImportStepBase


class SourceImporter(ImportStepBase):
    """Import sources/journals from PBN"""

    step_name = "source_import"
    step_description = "Import źródeł (czasopism)"

    def download(self):
        """Pobierz źródła z PBN (MNiSW) do lustra."""
        self.update_progress(0, 1, "Pobieranie źródeł z PBN")
        self.log("info", "Pobieranie źródeł z MNiSW")
        subtask_callback = self.create_subtask_progress("Pobieranie źródeł MNiSW")
        try:
            pobierz_zrodla_mnisw(self.client, callback=subtask_callback)
            self.log("success", "Źródła pobrane pomyślnie")
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać źródeł")
            self.log("warning", "Kontynuacja z częściowymi danymi")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie źródeł")
        return {"sources_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj źródła z lustra do BPP."""
        if not Journal.objects.exists():
            self.log(
                "warning",
                "Brak pobranych źródeł — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Importowanie źródeł do bazy danych")
        self.log("info", "Importowanie źródeł do bazy danych")
        try:
            result = importer.importuj_zrodla()
            if hasattr(self.session, "statistics") and isinstance(result, (int, float)):
                stats = self.session.statistics
                stats.journals_imported = int(result)
                stats.save()
            self.log("success", "Źródła zaimportowane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować źródeł")
            raise
        self.update_progress(1, 1, "Zakończono import źródeł")
        return {"sources_imported": True, "error_count": len(self.errors)}
