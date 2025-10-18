"""Conference import utilities"""

from pbn_integrator.utils import pobierz_konferencje

from .base import ImportStepBase


class ConferenceImporter(ImportStepBase):
    """Import conferences from PBN"""

    step_name = "conference_import"
    step_description = "Import konferencji"

    def run(self):
        """Import conferences"""
        self.update_progress(0, 1, "Pobieranie konferencji z PBN")
        self.log("info", "Pobieranie konferencji z PBN")

        # Create progress callback
        subtask_callback = self.create_subtask_progress("Pobieranie konferencji")

        try:
            pobierz_konferencje(self.client, callback=subtask_callback)

            # Update statistics if available
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.conferences_imported += 1  # Increment counter
                stats.save()

            self.log("success", "Conferences imported successfully")

        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować konferencji")
        finally:
            self.clear_subtask_progress()

        self.update_progress(1, 1, "Zakończono import konferencji")

        return {"conferences_imported": True, "error_count": len(self.errors)}
