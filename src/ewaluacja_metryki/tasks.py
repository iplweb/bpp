import logging
import sys

import rollbar
from celery import chord, group, shared_task
from django.utils import timezone

from bpp.models import Uczelnia
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

from .models import StatusGenerowania
from .utils import generuj_metryki

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def oblicz_metryki_dla_autora_task(
    self,
    ilosc_udzialow_id,
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=0.01,
    rodzaje_autora=None,
):
    """
    Celery task do obliczania metryki dla pojedynczego autora-dyscypliny.

    Args:
        ilosc_udzialow_id: ID obiektu IloscUdzialowDlaAutoraZaCalosc
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        rodzaje_autora: Lista rodzajów autorów do przetworzenia

    Returns:
        Dict z kluczami: status ("processed"/"skipped"/"error"), autor, dyscyplina
    """
    from decimal import Decimal

    from django.db.models import F

    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    from .utils import _process_single_author

    if rodzaje_autora is None:
        rodzaje_autora = ["N", "D", "B", "Z", " "]

    try:
        # Pobierz obiekt IloscUdzialowDlaAutoraZaCalosc
        ilosc_udzialow = IloscUdzialowDlaAutoraZaCalosc.objects.select_related(
            "autor", "dyscyplina_naukowa"
        ).get(pk=ilosc_udzialow_id)

        # Przetwórz pojedynczego autora
        result, msg = _process_single_author(
            ilosc_udzialow=ilosc_udzialow,
            idx=1,  # Not used in parallel mode
            total=1,  # Not used in parallel mode
            processed=0,  # Not used in parallel mode
            rodzaje_autora=rodzaje_autora,
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=Decimal(str(minimalny_pk)),
            progress_callback=None,  # No callback in parallel mode
            logger_output=None,
        )

        # Atomowo zwiększ licznik przetworzonych tasków
        StatusGenerowania.objects.update(
            liczba_przetworzonych=F("liczba_przetworzonych") + 1
        )

        return {
            "status": result,
            "autor": str(ilosc_udzialow.autor),
            "dyscyplina": ilosc_udzialow.dyscyplina_naukowa.nazwa,
            "message": msg,
        }

    except IloscUdzialowDlaAutoraZaCalosc.DoesNotExist:
        error_msg = (
            f"IloscUdzialowDlaAutoraZaCalosc o ID {ilosc_udzialow_id} nie istnieje"
        )
        logger.error(error_msg)
        # Atomowo zwiększ licznik przetworzonych tasków
        StatusGenerowania.objects.update(
            liczba_przetworzonych=F("liczba_przetworzonych") + 1
        )
        return {
            "status": "error",
            "autor": "Unknown",
            "dyscyplina": "Unknown",
            "message": error_msg,
        }
    except Exception as e:
        error_msg = f"Błąd przy przetwarzaniu ID {ilosc_udzialow_id}: {str(e)}"
        logger.error(error_msg)
        rollbar.report_exc_info(sys.exc_info())
        # Atomowo zwiększ licznik przetworzonych tasków
        StatusGenerowania.objects.update(
            liczba_przetworzonych=F("liczba_przetworzonych") + 1
        )
        return {
            "status": "error",
            "autor": "Unknown",
            "dyscyplina": "Unknown",
            "message": error_msg,
        }


@shared_task
def finalizuj_generowanie_metryk(results):
    """
    Callback task wywoływany po zakończeniu wszystkich tasków obliczania metryk.

    Args:
        results: Lista wyników z tasków oblicz_metryki_dla_autora_task

    Returns:
        Dict z podsumowaniem: processed, skipped, errors, total
    """
    status = StatusGenerowania.get_or_create()

    # Odśwież status z bazy danych aby pobrać aktualną wartość liczba_przetworzonych
    # zaktualizowaną atomowo przez poszczególne taski
    status.refresh_from_db()

    # Agreguj wyniki z results aby policzyć błędy
    processed = 0
    skipped = 0
    errors = 0

    for result in results:
        if result and isinstance(result, dict):
            result_status = result.get("status", "error")
            if result_status == "processed":
                processed += 1
            elif result_status == "skipped":
                skipped += 1
            elif result_status == "error":
                errors += 1
        else:
            # Jeśli wynik nie jest dictem, traktuj jako błąd
            errors += 1

    total = len(results)

    # Zakończ generowanie - używa liczba_przetworzonych już zaktualizowanej atomowo w bazie
    status.zakoncz_generowanie(liczba_bledow=errors)

    # Użyj rzeczywistej wartości z bazy (atomowo zaktualizowanej przez taski)
    actual_processed = status.liczba_przetworzonych

    logger.info(
        f"Zakończono równoległe generowanie metryk. "
        f"Przetworzono: {actual_processed}, pominięto: {skipped}, błędy: {errors}, "
        f"łącznie: {total}"
    )

    return {
        "success": True,
        "processed": actual_processed,
        "skipped": skipped,
        "errors": errors,
        "total": total,
        "message": f"Wygenerowano metryki dla {actual_processed} autorów (pominięto: {skipped}, błędy: {errors})",
    }


@shared_task(bind=True)
def generuj_metryki_task_parallel(
    self,
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=0.01,
    nadpisz=True,
    przelicz_liczbe_n=True,
    rodzaje_autora=None,
):
    """
    Celery task do równoległego generowania metryk ewaluacyjnych.

    Uruchamia wiele tasków równolegle (po jednym dla każdego autora-dyscypliny),
    co pozwala wykorzystać wiele workerów Celery jednocześnie.

    Args:
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        nadpisz: Czy nadpisywać istniejące metryki
        przelicz_liczbe_n: Czy przeliczać liczbę N przed generowaniem metryk (domyślnie True)
        rodzaje_autora: Lista rodzajów autorów do przetworzenia (domyślnie ['N', 'D', 'B', 'Z', ' '])
    """
    if rodzaje_autora is None:
        rodzaje_autora = ["N", "D", "B", "Z", " "]

    status = StatusGenerowania.get_or_create()

    try:
        # Krok 1: Przelicz liczby N jeśli włączone
        if przelicz_liczbe_n:
            logger.info("Przeliczanie liczby N dla uczelni...")
            status.ostatni_komunikat = "Przeliczanie liczby N..."
            status.save()

            uczelnia = Uczelnia.objects.get_default()
            oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
            logger.info("Przeliczono liczby N pomyślnie")

        # Krok 2: Pobierz wszystkie IDs autorów-dyscyplin do przetworzenia
        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

        from .models import MetrykaAutora

        ids_list = list(
            IloscUdzialowDlaAutoraZaCalosc.objects.values_list("id", flat=True)
        )
        total_count = len(ids_list)

        logger.info(
            f"Rozpoczęto równoległe generowanie metryk dla {total_count} autorów "
            f"(task_id: {self.request.id})"
        )

        # Krok 3: Usuń stare metryki jeśli nadpisz=True
        if nadpisz:
            deleted_count = MetrykaAutora.objects.all().count()
            MetrykaAutora.objects.all().delete()
            logger.info(f"Usunięto {deleted_count} starych metryk")

        # Krok 4: Zainicjuj status generowania
        status.rozpocznij_generowanie(
            task_id=self.request.id, liczba_do_przetworzenia=total_count
        )

        # Krok 5: Utwórz group pojedynczych tasków
        task_group = group(
            [
                oblicz_metryki_dla_autora_task.s(
                    ilosc_udzialow_id=autor_id,
                    rok_min=rok_min,
                    rok_max=rok_max,
                    minimalny_pk=minimalny_pk,
                    rodzaje_autora=rodzaje_autora,
                )
                for autor_id in ids_list
            ]
        )

        # Krok 6: Uruchom chord (group + callback) i zapisz group_id
        job = chord(task_group)(finalizuj_generowanie_metryk.s())

        # Group ID jest dostępny w job.parent
        group_id = job.parent.id if hasattr(job, "parent") and job.parent else None

        logger.info(
            f"Utworzono chord z {total_count} taskami. Chord ID: {job.id}, Group ID: {group_id}"
        )

        return {
            "success": True,
            "message": f"Uruchomiono równoległe generowanie metryk dla {total_count} autorów",
            "total": total_count,
            "task_id": self.request.id,
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(
            f"Błąd podczas uruchamiania równoległego generowania metryk: {str(e)}"
        )
        rollbar.report_exc_info(sys.exc_info())

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

    # NOTE: Sprawdzanie w_trakcie przeniesione do widoku UruchomGenerowanie
    # Status jest ustawiany w widoku przed uruchomieniem taska, więc tutaj nie sprawdzamy

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

        # Status już jest ustawiony przez widok, tylko zaktualizuj liczbę jeśli się zmieniła
        if status.liczba_do_przetworzenia != total_count:
            status.liczba_do_przetworzenia = total_count
            status.save()

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

        # Odśwież status z bazy (może być zaktualizowany przez progress_callback)
        status.refresh_from_db()

        # Oznacz zakończenie (zakoncz_generowanie używa już zaktualizowanej liczba_przetworzonych z bazy)
        status.zakoncz_generowanie(liczba_bledow=liczba_bledow)

        logger.info(
            f"Zakończono generowanie metryk. "
            f"Przetworzono: {status.liczba_przetworzonych}, błędy: {liczba_bledow}"
        )

        return {
            "success": True,
            "message": f"Wygenerowano metryki dla {status.liczba_przetworzonych} autorów",
            "przetworzonych": status.liczba_przetworzonych,
            "bledow": liczba_bledow,
            "data_zakonczenia": (
                status.data_zakonczenia.isoformat() if status.data_zakonczenia else None
            ),
        }

    except Exception as e:
        logger.error(f"Błąd podczas generowania metryk: {str(e)}")
        rollbar.report_exc_info(sys.exc_info())

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
