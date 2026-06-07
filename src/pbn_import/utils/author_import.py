"""Author import utilities"""

from pbn_api.models import Scientist
from pbn_integrator.utils import integruj_autorow_z_uczelni, pobierz_ludzi_z_uczelni

from .base import ImportStepBase


class AuthorImporter(ImportStepBase):
    """Import authors from PBN"""

    step_name = "author_import"
    step_description = "Import autorów"

    def _resolve_uczelnia(self):
        """Zwróć uczelnię kontekstu importu lub None (z logiem) gdy brak pbn_uid."""
        uczelnia = self.uczelnia
        if not uczelnia or not uczelnia.pbn_uid_id:
            self.log(
                "warning",
                "Nie znaleziono Uczelni z PBN UID, pomijanie importu autorów",
            )
            return None
        return uczelnia

    def download(self):
        """Pobierz autorów uczelni z PBN do lustra."""
        uczelnia = self._resolve_uczelnia()
        if uczelnia is None:
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        self.update_progress(0, 1, "Pobieranie autorów z PBN")
        self.log("info", f"Pobieranie autorów dla instytucji {uczelnia.pbn_uid_id}")
        subtask_callback = self.create_subtask_progress("Pobieranie autorów")
        try:
            pobierz_ludzi_z_uczelni(
                self.client, uczelnia.pbn_uid_id, callback=subtask_callback
            )
            self.log("success", "Autorzy pobrani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać autorów")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie autorów")
        return {"authors_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zintegruj autorów z lustra do BPP (z uczelnią)."""
        uczelnia = self._resolve_uczelnia()
        if uczelnia is None:
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        if not Scientist.objects.exists():
            self.log(
                "warning",
                "Brak pobranych autorów — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )

        self.update_progress(0, 1, "Integrowanie autorów")
        self.log("info", "Integrating authors with university")
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
            self.clear_subtask_progress()
            if hasattr(self.session, "statistics"):
                from bpp.models import Autor

                stats = self.session.statistics
                stats.authors_imported = Autor.objects.filter(
                    pbn_uid_id__isnull=False
                ).count()
                stats.save()
            self.log("success", "Autorzy zintegrowani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować autorów")
            if hasattr(self.session, "statistics"):
                self.session.statistics.authors_failed += 1
                self.session.statistics.save()
        self.update_progress(1, 1, "Zakończono import autorów")
        return {
            "authors_imported": True,
            "uczelnia_pbn_uid": uczelnia.pbn_uid_id,
            "error_count": len(self.errors),
        }
