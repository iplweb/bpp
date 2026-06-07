"""Conference import utilities"""

from pbn_api.models import Conference
from pbn_integrator.utils import integruj_konferencje, pobierz_konferencje

from .base import ImportStepBase


class ConferenceImporter(ImportStepBase):
    """Import conferences from PBN"""

    step_name = "conference_import"
    step_description = "Import konferencji"

    def download(self):
        """Pobierz konferencje z PBN do lustra."""
        self.update_progress(0, 1, "Pobieranie konferencji z PBN")
        self.log("info", "Pobieranie konferencji z PBN")
        subtask_callback = self.create_subtask_progress("Pobieranie konferencji")
        try:
            pobierz_konferencje(self.client, callback=subtask_callback)
            self.log("success", "Konferencje pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać konferencji")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie konferencji")
        return {"conferences_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zintegruj lustro konferencji do BPP."""
        if not Conference.objects.exists():
            self.log(
                "warning",
                "Brak pobranych konferencji — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Integracja konferencji")
        subtask_callback = self.create_subtask_progress("Integracja konferencji")
        try:
            liczba = integruj_konferencje(callback=subtask_callback)
            self.log("success", f"Zintegrowano {liczba} konferencji")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować konferencji")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono integrację konferencji")
        return {"conferences_imported": True, "error_count": len(self.errors)}
