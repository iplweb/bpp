import logging

from celery import shared_task
from django.core.management import call_command

from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025
from .models import StatusGenerowania

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
):
    """
    Celery task do generowania metryk ewaluacyjnych.

    Args:
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        nadpisz: Czy nadpisywać istniejące metryki
        przelicz_liczbe_n: Czy przeliczać liczbę N przed generowaniem metryk (domyślnie True)
    """
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
        # Oznacz rozpoczęcie
        status.rozpocznij_generowanie(task_id=self.request.id)
        logger.info(f"Rozpoczęto generowanie metryk (task_id: {self.request.id})")

        # Krok 1: Przelicz liczby N jeśli włączone
        if przelicz_liczbe_n:
            logger.info("Przeliczanie liczby N dla uczelni...")
            status.ostatni_komunikat = "Przeliczanie liczby N..."
            status.save()

            try:
                uczelnia = Uczelnia.objects.get_default()
                oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
                logger.info("Przeliczono liczby N pomyślnie")
            except Exception as e:
                logger.warning(f"Błąd przy przeliczaniu liczby N: {str(e)}")
                # Kontynuuj mimo błędu

        # Krok 2: Wywołaj management command
        from io import StringIO

        out = StringIO()

        status.ostatni_komunikat = "Obliczanie metryk ewaluacyjnych..."
        status.save()

        call_command(
            "oblicz_metryki",
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=minimalny_pk,
            nadpisz=nadpisz,
            bez_liczby_n=True,  # Już przeliczone powyżej
            stdout=out,
        )

        output = out.getvalue()

        # Parsuj wynik aby wyciągnąć statystyki
        liczba_przetworzonych = 0
        liczba_bledow = 0

        for line in output.split("\n"):
            if "Zakończono:" in line:
                # Próbuj wyciągnąć liczby z linii podsumowania
                import re

                match = re.search(r"przetworzono (\d+).*błędy (\d+)", line)
                if match:
                    liczba_przetworzonych = int(match.group(1))
                    liczba_bledow = int(match.group(2))
                    break

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
