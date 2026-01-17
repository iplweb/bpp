"""Statement (oświadczenia) import utilities"""

from bpp.models import Jednostka
from pbn_integrator.utils import (
    integruj_oswiadczenia_z_instytucji,
    pobierz_oswiadczenia_z_instytucji,
)

from .base import ImportStepBase
from .publication_import import PublicationImporter


class StatementImporter(ImportStepBase):
    """Import statements from PBN"""

    step_name = "statement_import"
    step_description = "Import oświadczeń"

    def __init__(self, session, client=None):
        super().__init__(session, client)
        self.publication_importer = PublicationImporter(session, client)

    def run(self):
        """Import statements"""
        # Download statements
        self.update_progress(0, 2, "Pobieranie oświadczeń z PBN")
        self.log("info", "Pobieranie oświadczeń z instytucji")

        # Create progress callback for sub-task tracking
        subtask_callback = self.create_subtask_progress("Pobieranie oświadczeń")

        try:
            pobierz_oswiadczenia_z_instytucji(self.client, callback=subtask_callback)
            self.log("info", "Statements downloaded successfully")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać oświadczeń")
        finally:
            self.clear_subtask_progress()

        # Integrate statements with callback for missing publications
        self.update_progress(1, 2, "Integrowanie oświadczeń")
        self.log("info", "Integrating statements")

        # Setup publication importer for any missing publications
        uczelnia = self.publication_importer._setup_uczelnia_and_jednostka()
        if not uczelnia:
            self.log(
                "warning",
                "Brak Uczelni z PBN UID, pomijanie integracji oświadczeń",
            )
            return {"statements_imported": False, "reason": "No Uczelnia PBN UID"}

        def missing_publication_callback(pbn_uid_id):
            """Import missing publication when found in statements"""
            self.log("info", f"Importing missing publication: {pbn_uid_id}")
            return self.publication_importer.import_single_publication(pbn_uid_id)

        # Pobierz jednostkę domyślną z konfiguracji sesji
        default_jednostka = None
        jednostka_id = self.session.config.get("default_jednostka_id")
        if jednostka_id:
            default_jednostka = Jednostka.objects.filter(pk=jednostka_id).first()

        try:
            integruj_oswiadczenia_z_instytucji(
                missing_publication_callback,
                default_jednostka=default_jednostka,
            )

            # Update statistics
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.statements_imported += 1
                stats.save()

            self.log("success", "Statements integrated successfully")

        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować oświadczeń")

        self.update_progress(2, 2, "Zakończono import oświadczeń")

        return {"statements_imported": True, "error_count": len(self.errors)}
