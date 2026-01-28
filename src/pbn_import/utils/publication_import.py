"""Publication import utilities"""

from bpp.models import (
    Dyscyplina_Naukowa,
    Jednostka,
    Rekord,
    Rodzaj_Zrodla,
    Uczelnia,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from pbn_api.models import Publication
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.utils import (
    pobierz_publikacje_z_instytucji,
    pobierz_publikacje_z_instytucji_v2,
)

from .base import CancelledException, ImportStepBase


class PublicationImporter(ImportStepBase):
    """Import publications from PBN"""

    step_name = "publication_import"
    step_description = "Import publikacji"

    def __init__(self, session, client=None, delete_existing=False):
        super().__init__(session, client)
        self.delete_existing = delete_existing
        self.default_jednostka = None

    def run(self):
        """Import publications"""
        # Setup uczelnia and jednostka
        uczelnia = self._setup_uczelnia_and_jednostka()
        if uczelnia is None:
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        total_steps = 4 if self.delete_existing else 3
        current_step = 0

        # Delete existing if requested
        if self.delete_existing:
            result = self._delete_existing_publications(current_step, total_steps)
            if result:
                return result
            current_step += 1

        # Download publications
        result = self._download_publications(current_step, total_steps, uczelnia)
        if result:
            return result
        current_step += 1

        # Download publications v2
        result = self._download_publications_v2(current_step, total_steps)
        if result:
            return result
        current_step += 1

        # Import publications
        result = self._import_publications(current_step, total_steps)
        if result:
            return result

        self.update_progress(total_steps, total_steps, "Zakończono import publikacji")

        return {
            "publications_imported": True,
            "default_jednostka": self.default_jednostka.nazwa,
            "error_count": len(self.errors),
        }

    def _setup_uczelnia_and_jednostka(self):
        """Setup uczelnia and default jednostka for import."""
        uczelnia = Uczelnia.objects.get_default()

        if not uczelnia or not uczelnia.pbn_uid_id:
            self.log(
                "warning",
                "Nie znaleziono Uczelni z PBN UID, pomijanie importu autorów",
            )
            return None

        jednostka_id = self.session.config.get("default_jednostka_id")
        if jednostka_id:
            self.default_jednostka = Jednostka.objects.get(pk=jednostka_id)
        else:
            self.default_jednostka = Jednostka.objects.filter(
                nazwa="Jednostka Domyślna"
            ).first()

        if not self.default_jednostka:
            raise ValueError(
                "Nie znaleziono domyślnej jednostki dla importu publikacji"
            )

        # Ensure OpenAccess version exists
        Wersja_Tekstu_OpenAccess.objects.get_or_create(nazwa="Inna", skrot="OTHER")

        return uczelnia

    def _delete_existing_publications(self, current_step, total_steps):
        """Delete existing publications if requested. Returns result dict if cancelled."""
        if self.check_cancelled():
            return {"cancelled": True}

        self.update_progress(
            current_step, total_steps, "Usuwanie istniejących publikacji PBN"
        )
        self.log("warning", "Usuwanie istniejących publikacji PBN")

        deleted_zwarte = Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None).delete()[0]
        deleted_ciagle = Wydawnictwo_Ciagle.objects.exclude(pbn_uid_id=None).delete()[0]

        self.log(
            "info",
            f"Usunięto {deleted_zwarte} monografii i {deleted_ciagle} artykułów",
        )
        return None

    def _download_publications(self, current_step, total_steps, uczelnia):
        """Download publications from PBN. Returns result dict if cancelled."""
        if self.check_cancelled():
            return {"cancelled": True}

        self.update_progress(current_step, total_steps, "Pobieranie publikacji z PBN")
        self.log("info", f"Pobieranie publikacji z instytucji {uczelnia.pbn_uid_id}")

        download_callback = self.create_subtask_progress(
            "Pobieranie publikacji instytucji"
        )

        try:
            pobierz_publikacje_z_instytucji(self.client, callback=download_callback)
            self.log("info", "Publikacje pobrane pomyślnie")
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać publikacji")
        return None

    def _download_publications_v2(self, current_step, total_steps):
        """Download publications v2 from PBN. Returns result dict if cancelled."""
        if self.check_cancelled():
            return {"cancelled": True}

        self.clear_subtask_progress()

        self.update_progress(
            current_step, total_steps, "Pobieranie publikacji z PBN (v2)"
        )
        self.log("info", "Pobieranie publikacji z instytucji (wersja 2)")

        download_v2_callback = self.create_subtask_progress(
            "Pobieranie publikacji instytucji (v2)"
        )

        try:
            self._download_publications_v2_with_callback(download_v2_callback)
            self.log("info", "Publikacje v2 pobrane pomyślnie")
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać publikacji v2")
        finally:
            self.clear_subtask_progress()
        return None

    def _import_publications(self, current_step, total_steps):
        """Import publications to database. Returns result dict if cancelled."""
        if self.check_cancelled():
            return {"cancelled": True}

        self.update_progress(current_step, total_steps, "Importowanie publikacji")
        self.log("info", "Importowanie publikacji do bazy danych")

        try:
            self._import_publications_with_cancellation()

            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.publications_imported = (
                    Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None).count()
                    + Wydawnictwo_Ciagle.objects.exclude(pbn_uid_id=None).count()
                )
                stats.save()

            self.log("success", "Publikacje zaimportowane pomyślnie")

        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować publikacji")
            if hasattr(self.session, "statistics"):
                self.session.statistics.publications_failed += 1
                self.session.statistics.save()
        return None

    def _import_publications_with_cancellation(self):
        """Import publications with cancellation checking"""
        from bpp.util import pbar

        # Get publications to import (same logic as importuj_publikacje_instytucji)
        niechciane = list(Rekord.objects.values_list("pbn_uid_id", flat=True))
        chciane = Publication.objects.all().exclude(pk__in=niechciane)

        total = chciane.count()
        self.log("info", f"Znaleziono {total} publikacji do importu")

        # Create cache ONCE before loop
        rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
        dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

        # Create subtask progress callback for import phase
        import_callback = self.create_subtask_progress(
            "Importowanie publikacji do bazy"
        )

        # Import publications with cancellation checking
        imported_count = 0
        failed_count = 0

        # Use pbar with callback to properly show subtask progress
        for i, pbn_publication in enumerate(
            pbar(
                chciane,
                count=total,
                label="Importowanie publikacji do bazy",
                callback=import_callback,
            )
        ):
            # Check cancellation every 10 publications
            if i % 10 == 0:
                if self.check_cancelled():
                    self.log(
                        "warning",
                        f"Import anulowany po {imported_count} publikacjach",
                    )
                    raise CancelledException("Import został anulowany")

            try:
                ret = importuj_publikacje_po_pbn_uid_id(
                    pbn_publication.mongoId,
                    client=self.client,
                    default_jednostka=self.default_jednostka,
                    rodzaj_periodyk=rodzaj_periodyk,
                    dyscypliny_cache=dyscypliny_cache,
                )
                if ret:
                    imported_count += 1
            except Exception as e:
                failed_count += 1
                self.handle_error(
                    e,
                    f"Nie udało się zaimportować publikacji {pbn_publication.mongoId}",
                )
                # Continue with next publication

        self.log(
            "info",
            f"Zaimportowano {imported_count} publikacji, {failed_count} niepowodzeń",
        )

    def _download_publications_v2_with_callback(self, callback):
        """Download publications v2 with progress tracking using parallel threads."""
        # Use threaded download for better performance
        pobierz_publikacje_z_instytucji_v2(
            self.client,
            callback=callback,
            use_threads=True,
        )

    def import_single_publication(self, pbn_uid_id):
        """Import a single publication by PBN UID"""
        return importuj_publikacje_po_pbn_uid_id(
            pbn_uid_id,
            client=self.client,
            default_jednostka=self.default_jednostka,
        )
