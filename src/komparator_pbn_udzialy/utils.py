import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from tqdm import tqdm

from komparator_pbn_udzialy.models import BrakAutoraWPublikacji, RozbieznoscDyscyplinPBN
from pbn_api.exceptions import (
    BPPAutorNotFound,
    BPPAutorPublicationLinkNotFound,
    BPPPublicationNotFound,
)
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
            "missing_publication": 0,
            "missing_autor": 0,
            "missing_link": 0,
        }

    def clear_discrepancies(self):
        """Usuwa wszystkie istniejące rozbieżności i brakujących autorów."""
        count1 = RozbieznoscDyscyplinPBN.objects.all().delete()[0]
        count2 = BrakAutoraWPublikacji.objects.all().delete()[0]
        logger.info(f"Usunięto {count1} rozbieżności i {count2} brakujących autorów")
        return count1 + count2

    def save_missing_record(
        self,
        oswiadczenie: OswiadczenieInstytucji,
        typ: str,
        autor=None,
        publikacja=None,
    ):
        """
        Zapisuje brakujący rekord do bazy danych.

        Args:
            oswiadczenie: Oświadczenie PBN
            typ: Typ problemu (z BrakAutoraWPublikacji.TYP_*)
            autor: Autor z BPP (jeśli został znaleziony)
            publikacja: Publikacja z BPP (jeśli została znaleziona)
        """
        content_type = None
        object_id = None

        if publikacja is not None:
            content_type = ContentType.objects.get_for_model(publikacja.__class__)
            object_id = publikacja.pk

        dyscyplina_pbn = oswiadczenie.get_bpp_discipline()

        BrakAutoraWPublikacji.objects.update_or_create(
            oswiadczenie_instytucji=oswiadczenie,
            defaults={
                "pbn_scientist": oswiadczenie.personId,
                "autor": autor,
                "content_type": content_type,
                "object_id": object_id,
                "typ": typ,
                "dyscyplina_pbn": dyscyplina_pbn,
            },
        )

        logger.debug(f"Zapisano brak autora: typ={typ}, oswiadczenie={oswiadczenie.id}")

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
            # Próbujemy znaleźć odpowiedni rekord wydawnictwo_autor
            try:
                wydawnictwo_autor = oswiadczenie.get_bpp_wa_raises()
            except BPPPublicationNotFound:
                self.save_missing_record(
                    oswiadczenie=oswiadczenie,
                    typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
                    autor=None,
                    publikacja=None,
                )
                self.stats["missing_publication"] += 1
                return
            except BPPAutorNotFound:
                publikacja = oswiadczenie.get_bpp_publication()
                self.save_missing_record(
                    oswiadczenie=oswiadczenie,
                    typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
                    autor=None,
                    publikacja=publikacja,
                )
                self.stats["missing_autor"] += 1
                return
            except BPPAutorPublicationLinkNotFound:
                publikacja = oswiadczenie.get_bpp_publication()
                autor = oswiadczenie.get_bpp_autor()
                self.save_missing_record(
                    oswiadczenie=oswiadczenie,
                    typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
                    autor=autor,
                    publikacja=publikacja,
                )
                self.stats["missing_link"] += 1
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

        total_missing = (
            self.stats["missing_publication"]
            + self.stats["missing_autor"]
            + self.stats["missing_link"]
        )
        logger.info(
            f"Zakończono porównywanie. "
            f"Przetworzono: {self.stats['processed']}, "
            f"Rozbieżności: {self.stats['discrepancies_found']}, "
            f"Brak publikacji: {self.stats['missing_publication']}, "
            f"Brak autora: {self.stats['missing_autor']}, "
            f"Brak powiązania: {self.stats['missing_link']}, "
            f"(razem brakujących: {total_missing}), "
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
