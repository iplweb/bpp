"""Publication import utilities"""

from pbn_api.models import Publication
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.utils import (
    integruj_publikacje_instytucji,
    pobierz_publikacje_z_instytucji,
    zapisz_publikacje_instytucji_v2,
)
from .base import CancelledException, ImportStepBase

from bpp.models import (
    Jednostka,
    Rekord,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)


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
        # Get default unit
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

        total_steps = 5 if self.delete_existing else 4
        current_step = 0

        # Delete existing if requested
        if self.delete_existing:
            if self.check_cancelled():
                return {"cancelled": True}

            self.update_progress(
                current_step, total_steps, "Usuwanie istniejących publikacji PBN"
            )
            self.log("warning", "Usuwanie istniejących publikacji PBN")

            deleted_zwarte = Wydawnictwo_Zwarte.objects.exclude(
                pbn_uid_id=None
            ).delete()[0]
            deleted_ciagle = Wydawnictwo_Ciagle.objects.exclude(
                pbn_uid_id=None
            ).delete()[0]

            self.log(
                "info",
                f"Usunięto {deleted_zwarte} monografii i {deleted_ciagle} artykułów",
            )
            current_step += 1

        # Check cancellation before downloading
        if self.check_cancelled():
            return {"cancelled": True}

        # Download publications
        self.update_progress(current_step, total_steps, "Pobieranie publikacji z PBN")
        self.log("info", "Pobieranie publikacji z instytucji")

        # Create progress callback for download
        download_callback = self.create_subtask_progress(
            "Pobieranie publikacji instytucji"
        )

        try:
            pobierz_publikacje_z_instytucji(self.client, callback=download_callback)
            self.log("info", "Publikacje pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać publikacji")
        finally:
            # Don't clear subtask immediately - let it show completion briefly
            pass
        current_step += 1

        # Check cancellation before downloading v2
        if self.check_cancelled():
            return {"cancelled": True}

        # Clear the download subtask progress before starting v2 download
        self.clear_subtask_progress()

        # Download publications v2
        self.update_progress(
            current_step, total_steps, "Pobieranie publikacji z PBN (v2)"
        )
        self.log("info", "Pobieranie publikacji z instytucji (wersja 2)")

        # Create progress callback for v2 download
        download_v2_callback = self.create_subtask_progress(
            "Pobieranie publikacji instytucji (v2)"
        )

        try:
            self._download_publications_v2_with_callback(download_v2_callback)
            self.log("info", "Publikacje v2 pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać publikacji v2")
        finally:
            # Clear subtask progress
            self.clear_subtask_progress()
        current_step += 1

        # Check cancellation before importing
        if self.check_cancelled():
            return {"cancelled": True}

        # Import publications
        self.update_progress(current_step, total_steps, "Importowanie publikacji")
        self.log("info", "Importowanie publikacji do bazy danych")

        try:
            # We need to wrap the import function to add cancellation checking
            self._import_publications_with_cancellation()

            # Update statistics
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
        current_step += 1

        # Check cancellation before integrating
        if self.check_cancelled():
            return {"cancelled": True}

        # Integrate publications
        self.update_progress(current_step, total_steps, "Integrowanie publikacji")
        self.log("info", "Integrowanie publikacji")

        try:
            integruj_publikacje_instytucji(use_threads=True)
            self.log("success", "Publikacje zintegrowane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować publikacji")

        self.update_progress(total_steps, total_steps, "Zakończono import publikacji")

        return {
            "publications_imported": True,
            "default_jednostka": self.default_jednostka.nazwa,
            "error_count": len(self.errors),
        }

    def _import_publications_with_cancellation(self):
        """Import publications with cancellation checking"""
        from bpp.util import pbar

        # Get publications to import (same logic as importuj_publikacje_instytucji)
        niechciane = list(Rekord.objects.values_list("pbn_uid_id", flat=True))
        chciane = Publication.objects.all().exclude(pk__in=niechciane)

        total = chciane.count()
        self.log("info", f"Znaleziono {total} publikacji do importu")

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
        """Download publications v2 with progress tracking"""
        from bpp.util import pbar

        # Get the result object from the API
        res = self.client.get_institution_publications_v2()
        total = res.count()

        self.log("info", f"Znaleziono {total} publikacji w wersji 2 API")

        # Process publications with progress tracking
        downloaded_count = 0
        failed_count = 0

        # Use pbar for consistent progress tracking
        for i, elem in enumerate(
            pbar(res, count=total, label="Pobieranie publikacji v2", callback=callback)
        ):
            # Check cancellation every 10 items
            if i % 10 == 0:
                if self.check_cancelled():
                    self.log(
                        "warning",
                        f"Pobieranie v2 anulowane po {downloaded_count} publikacjach",
                    )
                    raise CancelledException("Import został anulowany")

            try:
                zapisz_publikacje_instytucji_v2(self.client, elem)
                downloaded_count += 1
            except Exception as e:
                failed_count += 1
                self.handle_error(
                    e,
                    f"Nie udało się zapisać publikacji v2: {elem.get('id', 'unknown')}",
                )
                # Continue with next publication

        self.log(
            "info",
            f"Pobrano {downloaded_count} publikacji v2, {failed_count} niepowodzeń",
        )

    def import_single_publication(self, pbn_uid_id):
        """Import a single publication by PBN UID"""
        return importuj_publikacje_po_pbn_uid_id(
            pbn_uid_id,
            client=self.client,
            default_jednostka=self.default_jednostka,
        )
