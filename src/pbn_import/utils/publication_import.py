"""Publication import utilities"""

import logging

from bpp.models import (
    Dyscyplina_Naukowa,
    Rekord,
    Rodzaj_Zrodla,
    Wersja_Tekstu_OpenAccess,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.util import zaloguj_polkniety_wyjatek
from pbn_api.models import Publication
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.utils import (
    pobierz_publikacje_z_instytucji,
    pobierz_publikacje_z_instytucji_v2,
)

from .base import CancelledException, ImportStepBase
from .institution_import import resolve_default_jednostka, resolve_default_jezyk

logger = logging.getLogger(__name__)


class PublicationImporter(ImportStepBase):
    """Import publications from PBN"""

    step_name = "publication_import"
    step_description = "Import publikacji"

    def __init__(self, session, client=None, delete_existing=False, uczelnia=None):
        super().__init__(session, client, uczelnia=uczelnia)
        self.delete_existing = delete_existing
        self.default_jednostka = None
        self.default_jezyk = None

    def download(self):
        """Pobierz publikacje instytucji (v1 + v2) z PBN do lustra."""
        uczelnia = self._setup_uczelnia_and_jednostka()
        if uczelnia is None:
            return {"publications_imported": False, "reason": "No Uczelnia PBN UID"}

        result = self._download_publications(0, 2, uczelnia)
        if result:
            return result
        result = self._download_publications_v2(1, 2)
        if result:
            return result

        self.update_progress(2, 2, "Zakończono pobieranie publikacji")
        return {"publications_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj publikacje z lustra do BPP (opcjonalnie po skasowaniu)."""
        uczelnia = self._setup_uczelnia_and_jednostka()
        if uczelnia is None:
            return {"publications_imported": False, "reason": "No Uczelnia PBN UID"}

        if not Publication.objects.exists():
            self.log(
                "warning",
                "Brak pobranych publikacji — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )

        total_steps = 2 if self.delete_existing else 1
        current_step = 0
        if self.delete_existing:
            result = self._delete_existing_publications(current_step, total_steps)
            if result:
                return result
            current_step += 1

        result = self._import_publications(current_step, total_steps)
        if result:
            return result

        self.update_progress(total_steps, total_steps, "Zakończono import publikacji")
        return {
            "publications_imported": True,
            "default_jednostka": (
                self.default_jednostka.nazwa if self.default_jednostka else None
            ),
            "error_count": len(self.errors),
        }

    def _setup_uczelnia_and_jednostka(self, uczelnia=None):
        """Setup uczelnia and default jednostka for import."""
        if uczelnia is None:
            uczelnia = self.uczelnia

        if not uczelnia or not uczelnia.pbn_uid_id:
            self.log(
                "warning",
                "Nie znaleziono Uczelni z PBN UID, pomijanie importu autorów",
            )
            return None

        # Multi-hosted: domyślna jednostka pochodzi z wyboru na formularzu
        # nowego importu (config) albo — gdy go brak — z uczelnia-aware
        # find-or-create. NIE zgadujemy już po samej nazwie bez filtra uczelni.
        # Działa też gdy import startuje od późniejszego kroku (np. źródeł),
        # z pominięciem kroku institution_setup, który dawniej był JEDYNYM
        # miejscem zapisującym ``default_jednostka_id``.
        self.default_jednostka = resolve_default_jednostka(self.session, uczelnia)

        if not self.default_jednostka:
            raise ValueError(
                "Nie znaleziono domyślnej jednostki dla importu publikacji"
            )

        # Domyślny język dla publikacji bez (poprawnego) ``mainLanguage`` —
        # wybór z formularza nowego importu albo polski. Patrz pobierz_jezyk().
        self.default_jezyk = resolve_default_jezyk(self.session)

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
            zaloguj_polkniety_wyjatek(
                "Nie udało się pobrać publikacji z instytucji "
                f"(pbn_uid={uczelnia.pbn_uid_id})",
                logger=logger,
                do_rollbar=False,  # Rollbar już w handle_error
            )
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
            zaloguj_polkniety_wyjatek(
                "Nie udało się pobrać publikacji z instytucji (wersja 2)",
                logger=logger,
                do_rollbar=False,  # Rollbar już w handle_error
            )
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
            zaloguj_polkniety_wyjatek(
                "Nie udało się zaimportować publikacji do bazy danych",
                logger=logger,
                do_rollbar=False,  # Rollbar już w handle_error
            )
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
                    domyslny_jezyk=self.default_jezyk,
                )
                if ret:
                    imported_count += 1
            except Exception as e:
                zaloguj_polkniety_wyjatek(
                    f"Nie udało się zaimportować publikacji {pbn_publication.mongoId}",
                    logger=logger,
                    do_rollbar=False,  # Rollbar już w handle_error
                )
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
