import logging

from celery import shared_task

from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025
from .models import StatusGenerowania
from .utils import generuj_metryki

from django.utils import timezone

from bpp.models import Uczelnia

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generuj_metryki_task(
    self,
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=0.01,
    nadpisz=True,
    przelicz_liczbe_n=True,
    rodzaje_autora=None,
):
    """
    Celery task do generowania metryk ewaluacyjnych.

    Args:
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        nadpisz: Czy nadpisywać istniejące metryki
        przelicz_liczbe_n: Czy przeliczać liczbę N przed generowaniem metryk (domyślnie True)
        rodzaje_autora: Lista rodzajów autorów do przetworzenia (domyślnie ['N', 'D', 'Z', ' '])
    """
    if rodzaje_autora is None:
        rodzaje_autora = ["N", "D", "B", "Z", " "]
    status = StatusGenerowania.get_or_create()

    # Sprawdź czy inne generowanie nie jest w trakcie
    if status.w_trakcie:
        logger.warning("Generowanie metryk jest już w trakcie")
        return {
            "success": False,
            "message": "Generowanie jest już w trakcie",
            "task_id": status.task_id,
        }

    try:
        # Krok 1: Przelicz liczby N jeśli włączone
        if przelicz_liczbe_n:
            logger.info("Przeliczanie liczby N dla uczelni...")
            status.ostatni_komunikat = "Przeliczanie liczby N..."
            status.save()

            uczelnia = Uczelnia.objects.get_default()
            oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
            logger.info("Przeliczono liczby N pomyślnie")

        # Krok 2: Oblicz metryki używając wspólnej funkcji
        from decimal import Decimal

        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

        total_count = IloscUdzialowDlaAutoraZaCalosc.objects.all().count()

        # Oznacz rozpoczęcie
        status.rozpocznij_generowanie(
            task_id=self.request.id, liczba_do_przetworzenia=total_count
        )
        logger.info(
            f"Rozpoczęto generowanie metryk dla {total_count} autorów (task_id: {self.request.id})"
        )

        # Callback do aktualizacji statusu
        def update_progress(current, total, autor, dyscyplina, processed):
            status.liczba_przetworzonych = processed
            status.ostatni_komunikat = (
                f"Przetwarzanie {autor} - {dyscyplina.nazwa} ({current}/{total})"
            )
            status.save()

            # Aktualizuj Celery task state
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": current,
                    "total": total,
                    "message": f"Przetwarzanie {autor} - {dyscyplina.nazwa}",
                },
            )

        # Wywołaj wspólną funkcję generuj_metryki
        wynik = generuj_metryki(
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=Decimal(str(minimalny_pk)),
            nadpisz=nadpisz,
            rodzaje_autora=rodzaje_autora,
            progress_callback=update_progress,
        )

        liczba_przetworzonych = wynik["processed"]
        liczba_bledow = wynik["errors"]

        # Oznacz zakończenie
        status.zakoncz_generowanie(
            liczba_przetworzonych=liczba_przetworzonych, liczba_bledow=liczba_bledow
        )

        logger.info(
            f"Zakończono generowanie metryk. Przetworzono: {liczba_przetworzonych}, błędy: {liczba_bledow}"
        )

        return {
            "success": True,
            "message": f"Wygenerowano metryki dla {liczba_przetworzonych} autorów",
            "przetworzonych": liczba_przetworzonych,
            "bledow": liczba_bledow,
            "data_zakonczenia": (
                status.data_zakonczenia.isoformat() if status.data_zakonczenia else None
            ),
        }

    except Exception as e:
        logger.error(f"Błąd podczas generowania metryk: {str(e)}")

        # Oznacz błąd
        status.w_trakcie = False
        status.data_zakonczenia = timezone.now()
        status.ostatni_komunikat = f"Błąd: {str(e)}"
        status.save()

        return {
            "success": False,
            "message": f"Błąd podczas generowania: {str(e)}",
            "error": str(e),
        }
