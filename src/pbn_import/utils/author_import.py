"""Author import utilities"""

from pbn_integrator.utils import integruj_autorow_z_uczelni, pobierz_ludzi_z_uczelni
from .base import ImportStepBase

from bpp.models import Uczelnia


class AuthorImporter(ImportStepBase):
    """Import authors from PBN"""

    step_name = "author_import"
    step_description = "Import autorów"

    def run(self):
        """Import authors"""
        uczelnia = Uczelnia.objects.get_default()

        if not uczelnia or not uczelnia.pbn_uid_id:
            self.log(
                "warning", "Nie znaleziono Uczelni z PBN UID, pomijanie importu autorów"
            )
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        # Download authors from PBN
        self.update_progress(0, 2, "Pobieranie autorów z PBN")
        self.log("info", f"Pobieranie autorów dla instytucji {uczelnia.pbn_uid_id}")

        # Create progress callback
        subtask_callback = self.create_subtask_progress("Pobieranie autorów")

        try:
            pobierz_ludzi_z_uczelni(
                self.client, uczelnia.pbn_uid_id, callback=subtask_callback
            )
            self.log("info", "Authors downloaded successfully")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać autorów")
        finally:
            self.clear_subtask_progress()

        # Integrate authors
        self.update_progress(1, 2, "Integrowanie autorów")
        self.log("info", "Integrating authors with university")

        # Create progress callback for integration phase
        integration_callback = self.create_subtask_progress(
            "Integrowanie autorów z uczelnią"
        )

        try:
            integruj_autorow_z_uczelni(
                self.client,
                uczelnia.pbn_uid_id,
                import_unexistent=True,
                callback=integration_callback,
            )

            # Clear the integration subtask progress
            self.clear_subtask_progress()

            # Update statistics if available
            if hasattr(self.session, "statistics"):
                # We could query the database for actual count
                from bpp.models import Autor

                stats = self.session.statistics
                stats.authors_imported = Autor.objects.filter(
                    pbn_uid_id__isnull=False
                ).count()
                stats.save()

            self.log("success", "Authors integrated successfully")

        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować autorów")
            if hasattr(self.session, "statistics"):
                self.session.statistics.authors_failed += 1
                self.session.statistics.save()

        self.update_progress(2, 2, "Zakończono import autorów")

        return {
            "authors_imported": True,
            "uczelnia_pbn_uid": uczelnia.pbn_uid_id,
            "error_count": len(self.errors),
        }
