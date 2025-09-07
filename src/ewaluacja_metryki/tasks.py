import logging

from celery import shared_task

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
        rodzaje_autora: Lista rodzajów autorów do przetworzenia (domyślnie ['N'])
    """
    if rodzaje_autora is None:
        rodzaje_autora = ["N"]
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
        # Pobierz całkowitą liczbę autorów do przetworzenia
        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

        total_count = IloscUdzialowDlaAutoraZaCalosc.objects.all().count()

        # Oznacz rozpoczęcie
        status.rozpocznij_generowanie(
            task_id=self.request.id, liczba_do_przetworzenia=total_count
        )
        logger.info(
            f"Rozpoczęto generowanie metryk dla {total_count} autorów (task_id: {self.request.id})"
        )

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

        # Krok 2: Przygotuj do obliczania metryk
        from decimal import Decimal

        from django.db import transaction

        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
        from ewaluacja_metryki.models import MetrykaAutora

        # Pobierz autorów do przetworzenia
        ilosc_udzialow_qs = IloscUdzialowDlaAutoraZaCalosc.objects.all()
        total = ilosc_udzialow_qs.count()

        logger.info(f"Znaleziono {total} autorów do przetworzenia")
        status.liczba_do_przetworzenia = total
        status.ostatni_komunikat = f"Znaleziono {total} autorów do przetworzenia"
        status.save()

        if nadpisz:
            MetrykaAutora.objects.all().delete()

        processed = 0
        skipped = 0
        errors = 0

        # Przetwarzaj autorów po kolei z aktualizacją statusu
        for idx, ilosc_udzialow in enumerate(
            ilosc_udzialow_qs.select_related("autor", "dyscyplina_naukowa"), 1
        ):
            autor = ilosc_udzialow.autor
            dyscyplina = ilosc_udzialow.dyscyplina_naukowa
            slot_maksymalny = ilosc_udzialow.ilosc_udzialow

            # Aktualizuj progress bar dla każdego autora
            status.liczba_przetworzonych = processed
            status.ostatni_komunikat = (
                f"Przetwarzanie {autor} - {dyscyplina.nazwa} ({idx}/{total})"
            )
            status.save()

            # Aktualizuj Celery task state
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total,
                    "message": f"Przetwarzanie {autor} - {dyscyplina.nazwa}",
                },
            )

            try:
                with transaction.atomic():
                    # Sprawdź rodzaj_autora
                    from bpp.models import Autor_Dyscyplina

                    autor_dyscyplina = (
                        Autor_Dyscyplina.objects.filter(
                            autor=autor, dyscyplina_naukowa=dyscyplina
                        )
                        .order_by("-rok")
                        .first()
                    )

                    if (
                        not autor_dyscyplina
                        or autor_dyscyplina.rodzaj_autora not in rodzaje_autora
                    ):
                        skipped += 1
                        logger.debug(
                            f"Pominięto {autor} - {dyscyplina.nazwa}: rodzaj_autora = "
                            f"'{autor_dyscyplina.rodzaj_autora if autor_dyscyplina else 'brak danych'}'"
                        )
                        continue

                    # Pobierz główną jednostkę autora
                    jednostka = autor.aktualna_jednostka

                    # Oblicz metryki algorytmem plecakowym
                    (
                        punkty_nazbierane,
                        prace_nazbierane_ids,
                        slot_nazbierany,
                    ) = autor.zbieraj_sloty(
                        zadany_slot=slot_maksymalny,
                        rok_min=rok_min,
                        rok_max=rok_max,
                        minimalny_pk=Decimal(str(minimalny_pk)),
                        dyscyplina_id=dyscyplina.pk,
                    )

                    # Oblicz metryki dla wszystkich prac
                    (
                        punkty_wszystkie,
                        prace_wszystkie_ids,
                        slot_wszystkie,
                    ) = autor.zbieraj_sloty(
                        zadany_slot=slot_maksymalny,
                        rok_min=rok_min,
                        rok_max=rok_max,
                        minimalny_pk=Decimal(str(minimalny_pk)),
                        dyscyplina_id=dyscyplina.pk,
                        akcja="wszystko",
                    )

                    # Utwórz lub zaktualizuj metrykę
                    metryka, created = MetrykaAutora.objects.update_or_create(
                        autor=autor,
                        dyscyplina_naukowa=dyscyplina,
                        defaults={
                            "jednostka": jednostka,
                            "slot_maksymalny": slot_maksymalny,
                            "slot_nazbierany": Decimal(str(slot_nazbierany)),
                            "punkty_nazbierane": Decimal(str(punkty_nazbierane)),
                            "prace_nazbierane": prace_nazbierane_ids,
                            "slot_wszystkie": Decimal(str(slot_wszystkie)),
                            "punkty_wszystkie": Decimal(str(punkty_wszystkie)),
                            "prace_wszystkie": prace_wszystkie_ids,
                            "liczba_prac_wszystkie": len(prace_wszystkie_ids),
                            "rok_min": rok_min,
                            "rok_max": rok_max,
                        },
                    )

                    processed += 1
                    logger.debug(
                        f"[{processed}/{total}] {'utworzono' if created else 'zaktualizowano'} "
                        f"metrykę dla {autor} - {dyscyplina.nazwa}"
                    )

            except Exception as e:
                logger.error(
                    f"Błąd przy przetwarzaniu {autor} - {dyscyplina.nazwa}: {str(e)}"
                )
                errors += 1

        liczba_przetworzonych = processed
        liczba_bledow = errors

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
