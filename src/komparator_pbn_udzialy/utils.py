import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from tqdm import tqdm

from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN
from pbn_api.models import OswiadczenieInstytucji

logger = logging.getLogger(__name__)


class KomparatorDyscyplinPBN:
    """
    Klasa porównująca dyscypliny między BPP a PBN.
    Identyfikuje rozbieżności między dyscyplinami w rekordach Wydawnictwo_*_Autor
    a oświadczeniami w PBN (OswiadczenieInstytucji).
    """

    def __init__(self, clear_existing=False, show_progress=True):
        """
        Inicjalizacja komparatora.

        Args:
            clear_existing: Czy wyczyścić istniejące rozbieżności przed porównaniem
            show_progress: Czy pokazywać pasek postępu
        """
        self.clear_existing = clear_existing
        self.show_progress = show_progress
        self.stats = {
            "processed": 0,
            "discrepancies_found": 0,
            "errors": 0,
            "skipped": 0,
        }

    def clear_discrepancies(self):
        """Usuwa wszystkie istniejące rozbieżności z bazy danych."""
        count = RozbieznoscDyscyplinPBN.objects.all().delete()[0]
        logger.info(f"Usunięto {count} istniejących rozbieżności")
        return count

    def get_wydawnictwo_autor_for_oswiadczenie(
        self, oswiadczenie: OswiadczenieInstytucji
    ) -> object | None:
        """
        Znajduje odpowiedni rekord Wydawnictwo_*_Autor dla danego oświadczenia PBN.

        Args:
            oswiadczenie: Oświadczenie z PBN

        Returns:
            Instancja Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor lub None
        """
        try:
            # Używamy metody z modelu OswiadczenieInstytucji
            return oswiadczenie.get_bpp_wa()
        except Exception as e:
            logger.debug(
                f"Nie znaleziono wydawnictwo_autor dla oświadczenia {oswiadczenie.id}: {e}"
            )
            return None

    def compare_disciplines(
        self,
        wydawnictwo_autor,
        oswiadczenie: OswiadczenieInstytucji,
    ) -> bool:
        """
        Porównuje dyscypliny między rekordem BPP a oświadczeniem PBN.

        Args:
            wydawnictwo_autor: Rekord Wydawnictwo_*_Autor z BPP
            oswiadczenie: Oświadczenie z PBN

        Returns:
            True jeśli znaleziono rozbieżność, False w przeciwnym wypadku
        """
        # Dyscyplina w BPP
        dyscyplina_bpp = wydawnictwo_autor.dyscyplina_naukowa

        # Dyscyplina w PBN (używamy metody z modelu)
        dyscyplina_pbn = oswiadczenie.get_bpp_discipline()

        # Sprawdzamy czy dyscypliny są różne
        # Uwzględniamy przypadki gdy jedna lub obie są None
        if dyscyplina_bpp == dyscyplina_pbn:
            return False

        # Mamy rozbieżność - zapisujemy ją
        return self.save_discrepancy(
            wydawnictwo_autor=wydawnictwo_autor,
            oswiadczenie=oswiadczenie,
            dyscyplina_bpp=dyscyplina_bpp,
            dyscyplina_pbn=dyscyplina_pbn,
        )

    def save_discrepancy(
        self,
        wydawnictwo_autor,
        oswiadczenie: OswiadczenieInstytucji,
        dyscyplina_bpp,
        dyscyplina_pbn,
    ) -> bool:
        """
        Zapisuje znalezioną rozbieżność do bazy danych.

        Args:
            wydawnictwo_autor: Rekord Wydawnictwo_*_Autor
            oswiadczenie: Oświadczenie PBN
            dyscyplina_bpp: Dyscyplina z BPP
            dyscyplina_pbn: Dyscyplina z PBN

        Returns:
            True jeśli zapisano pomyślnie, False w przeciwnym wypadku
        """
        try:
            # Określamy content_type dla GenericForeignKey
            content_type = ContentType.objects.get_for_model(
                wydawnictwo_autor.__class__
            )

            # Używamy update_or_create aby uniknąć duplikatów
            obj, created = RozbieznoscDyscyplinPBN.objects.update_or_create(
                content_type=content_type,
                object_id=wydawnictwo_autor.id,
                oswiadczenie_instytucji=oswiadczenie,
                defaults={
                    "dyscyplina_bpp": dyscyplina_bpp,
                    "dyscyplina_pbn": dyscyplina_pbn,
                },
            )

            if created:
                logger.debug(
                    f"Zapisano rozbieżność dla {wydawnictwo_autor} - "
                    f"BPP: {dyscyplina_bpp}, PBN: {dyscyplina_pbn}"
                )
            else:
                logger.debug(f"Zaktualizowano rozbieżność dla {wydawnictwo_autor}")

            return True

        except Exception as e:
            logger.error(f"Błąd podczas zapisywania rozbieżności: {e}")
            return False

    def process_oswiadczenie(self, oswiadczenie: OswiadczenieInstytucji):
        """
        Przetwarza pojedyncze oświadczenie PBN.

        Args:
            oswiadczenie: Oświadczenie do przetworzenia
        """
        try:
            # Znajdujemy odpowiedni rekord wydawnictwo_autor
            wydawnictwo_autor = self.get_wydawnictwo_autor_for_oswiadczenie(
                oswiadczenie
            )

            if wydawnictwo_autor is None:
                # Brak publikacji po stronie BPP - pomijamy
                self.stats["skipped"] += 1
                return

            # Porównujemy dyscypliny
            if self.compare_disciplines(wydawnictwo_autor, oswiadczenie):
                self.stats["discrepancies_found"] += 1

            self.stats["processed"] += 1

        except Exception as e:
            logger.error(
                f"Błąd podczas przetwarzania oświadczenia {oswiadczenie.id}: {e}"
            )
            self.stats["errors"] += 1

    @transaction.atomic
    def run(self):
        """
        Główna metoda uruchamiająca porównanie.
        Przetwarza wszystkie oświadczenia PBN i identyfikuje rozbieżności.

        Returns:
            Słownik ze statystykami przetwarzania
        """
        logger.info("Rozpoczynam porównywanie dyscyplin BPP-PBN")

        # Opcjonalnie czyścimy istniejące rozbieżności
        if self.clear_existing:
            self.clear_discrepancies()

        # Pobieramy wszystkie oświadczenia z PBN
        # Używamy select_related dla optymalizacji
        oswiadczenia = OswiadczenieInstytucji.objects.select_related(
            "publicationId"
        ).prefetch_related("personId")

        total = oswiadczenia.count()
        logger.info(f"Znaleziono {total} oświadczeń do przetworzenia")

        # Przetwarzamy oświadczenia
        iterator = tqdm(oswiadczenia, total=total, disable=not self.show_progress)

        for oswiadczenie in iterator:
            self.process_oswiadczenie(oswiadczenie)

            if self.show_progress:
                iterator.set_description(
                    f"Przetworzono: {self.stats['processed']}, "
                    f"Rozbieżności: {self.stats['discrepancies_found']}"
                )

        logger.info(
            f"Zakończono porównywanie. "
            f"Przetworzono: {self.stats['processed']}, "
            f"Znaleziono rozbieżności: {self.stats['discrepancies_found']}, "
            f"Pominięto: {self.stats['skipped']}, "
            f"Błędy: {self.stats['errors']}"
        )

        return self.stats


def porownaj_dyscypliny_pbn(clear_existing=False, show_progress=True):
    """
    Funkcja pomocnicza do uruchomienia porównania.

    Args:
        clear_existing: Czy wyczyścić istniejące rozbieżności
        show_progress: Czy pokazywać pasek postępu

    Returns:
        Statystyki przetwarzania
    """
    komparator = KomparatorDyscyplinPBN(
        clear_existing=clear_existing,
        show_progress=show_progress,
    )
    return komparator.run()
