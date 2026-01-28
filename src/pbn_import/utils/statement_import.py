"""Statement (oświadczenia) import utilities"""

from django.contrib.contenttypes.models import ContentType

from bpp.models import Jednostka, Rekord
from pbn_api.models import OswiadczenieInstytucji
from pbn_integrator.utils import (
    integruj_oswiadczenia_z_instytucji,
    pobierz_brakujace_publikacje_batch,
    pobierz_oswiadczenia_z_instytucji,
)

from ..models import ImportInconsistency
from .base import ImportStepBase
from .publication_import import PublicationImporter


class StatementImporter(ImportStepBase):
    """Import statements from PBN"""

    step_name = "statement_import"
    step_description = "Import oświadczeń"

    def __init__(self, session, client=None):
        super().__init__(session, client)
        self.publication_importer = PublicationImporter(session, client)

    def _create_inconsistency_callback(self):
        """Create callback for recording statement integration inconsistencies."""
        session = self.session

        def inconsistency_callback(
            inconsistency_type,
            pbn_publication=None,
            pbn_author=None,
            bpp_publication=None,
            bpp_author=None,
            discipline=None,
            message="",
            action_taken="",
            **kwargs,
        ):
            """Record an inconsistency found during statement integration."""
            try:
                # Get content type for BPP publication to enable URL generation
                bpp_publication_content_type = None
                if bpp_publication:
                    bpp_publication_content_type = ContentType.objects.get_for_model(
                        bpp_publication
                    )

                ImportInconsistency.objects.create(
                    session=session,
                    inconsistency_type=inconsistency_type,
                    pbn_publication_id=(
                        str(pbn_publication.mongoId) if pbn_publication else ""
                    ),
                    pbn_publication_title=(
                        str(pbn_publication.title) if pbn_publication else ""
                    ),
                    pbn_author_id=str(pbn_author.pk) if pbn_author else "",
                    pbn_author_name=(
                        f"{pbn_author.lastName} {pbn_author.name}" if pbn_author else ""
                    ),
                    pbn_discipline=str(discipline) if discipline else "",
                    bpp_publication_id=bpp_publication.pk if bpp_publication else None,
                    bpp_publication_content_type=bpp_publication_content_type,
                    bpp_publication_title=(
                        str(bpp_publication.tytul_oryginalny) if bpp_publication else ""
                    ),
                    bpp_author_id=bpp_author.pk if bpp_author else None,
                    bpp_author_name=str(bpp_author) if bpp_author else "",
                    message=message,
                    action_taken=action_taken,
                )
            except Exception as e:
                # Log the error but don't fail the import
                self.log(
                    "warning",
                    f"Błąd podczas zapisu nieścisłości: {e}",
                    {"inconsistency_type": inconsistency_type, "message": message},
                )

        return inconsistency_callback

    def run(self):
        """Import statements"""
        # Step 1: Download statements
        self.update_progress(0, 3, "Pobieranie oświadczeń z PBN")
        self.log("info", "Pobieranie oświadczeń z instytucji")

        # Create progress callback for sub-task tracking
        subtask_callback = self.create_subtask_progress("Pobieranie oświadczeń")

        try:
            pobierz_oswiadczenia_z_instytucji(self.client, callback=subtask_callback)
            self.log("info", "Oświadczenia pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać oświadczeń")
        finally:
            self.clear_subtask_progress()

        # Setup publication importer for any missing publications
        uczelnia = self.publication_importer._setup_uczelnia_and_jednostka()
        if not uczelnia:
            self.log(
                "warning",
                "Brak Uczelni z PBN UID, pomijanie integracji oświadczeń",
            )
            return {"statements_imported": False, "reason": "No Uczelnia PBN UID"}

        # Pobierz jednostkę domyślną z konfiguracji sesji
        default_jednostka = None
        jednostka_id = self.session.config.get("default_jednostka_id")
        if jednostka_id:
            default_jednostka = Jednostka.objects.filter(pk=jednostka_id).first()

        # Step 2: Download missing publications in batch (NEW STEP)
        self.update_progress(1, 3, "Pobieranie brakujących publikacji")
        result = self._download_missing_publications(default_jednostka)
        if result:
            self.log(
                "info",
                f"Pobrano {result['downloaded']} brakujących publikacji "
                f"({result['failed']} błędów)",
            )

        # Step 3: Integrate statements (no longer needs missing publication callback)
        self.update_progress(2, 3, "Integrowanie oświadczeń")
        self.log("info", "Integrowanie oświadczeń")

        try:
            # Create inconsistency callback to log issues found during integration
            inconsistency_callback = self._create_inconsistency_callback()

            # Pass None for missing_publication_callback - publications already downloaded
            integruj_oswiadczenia_z_instytucji(
                missing_publication_callback=None,
                inconsistency_callback=inconsistency_callback,
                default_jednostka=default_jednostka,
            )

            # Log inconsistency summary
            inconsistency_count = self.session.inconsistencies.count()
            if inconsistency_count > 0:
                self.log(
                    "warning",
                    f"Znaleziono {inconsistency_count} nieścisłości podczas "
                    f"integracji oświadczeń",
                )

            # Update statistics
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.statements_imported += 1
                stats.save()

            self.log("success", "Oświadczenia zintegrowane pomyślnie")

        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować oświadczeń")

        self.update_progress(3, 3, "Zakończono import oświadczeń")

        return {"statements_imported": True, "error_count": len(self.errors)}

    def _download_missing_publications(self, default_jednostka):
        """Download missing publications referenced in statements.

        Identifies publications that exist in statements but not in BPP,
        then downloads and imports them in batch using ThreadPoolExecutor.

        Args:
            default_jednostka: Default unit for authors without affiliations.

        Returns:
            Dict with download statistics or None if no missing publications.
        """
        # Find all publication IDs referenced in statements
        stmt_pbn_uids = set(
            OswiadczenieInstytucji.objects.values_list(
                "publicationId_id", flat=True
            ).distinct()
        )

        if not stmt_pbn_uids:
            self.log("info", "Brak oświadczeń - pomijam pobieranie publikacji")
            return None

        # Find existing publications in BPP
        existing = set(
            Rekord.objects.exclude(pbn_uid_id=None).values_list("pbn_uid_id", flat=True)
        )

        # Calculate missing publications
        missing = stmt_pbn_uids - existing

        if not missing:
            self.log("info", "Wszystkie publikacje z oświadczeń istnieją w BPP")
            return {"downloaded": 0, "failed": 0, "errors": []}

        self.log(
            "info", f"Znaleziono {len(missing)} brakujących publikacji do pobrania"
        )

        # Create progress callback for batch download
        subtask_callback = self.create_subtask_progress(
            "Pobieranie brakujących publikacji"
        )

        try:
            result = pobierz_brakujace_publikacje_batch(
                client=self.client,
                missing_pbn_uids=missing,
                default_jednostka=default_jednostka,
                max_workers=8,
                callback=subtask_callback,
            )

            # Log any errors
            for error in result.get("errors", [])[:10]:  # Limit to first 10 errors
                self.log("warning", f"Błąd pobierania: {error}")

            if len(result.get("errors", [])) > 10:
                self.log(
                    "warning",
                    f"... i {len(result['errors']) - 10} kolejnych błędów",
                )

            return result

        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać brakujących publikacji")
            return None
        finally:
            self.clear_subtask_progress()
