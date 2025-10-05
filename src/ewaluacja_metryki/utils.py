import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from .models import MetrykaAutora

from bpp.models import Autor_Dyscyplina

logger = logging.getLogger(__name__)


def oblicz_metryki_dla_autora(
    autor,
    dyscyplina,
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=Decimal("0.01"),
    slot_maksymalny=None,
):
    """
    Oblicza metryki ewaluacyjne dla pojedynczego autora i dyscypliny.

    Args:
        autor: Obiekt Autor
        dyscyplina: Obiekt Dyscyplina_Naukowa
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        slot_maksymalny: Maksymalny slot dla autora (jeśli None, pobierany z IloscUdzialowDlaAutoraZaCalosc)

    Returns:
        Tuple (metryka, created) - obiekt MetrykaAutora i bool czy został utworzony
    """
    # Jeśli nie podano slot_maksymalny, pobierz z IloscUdzialowDlaAutoraZaCalosc
    if slot_maksymalny is None:
        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

        try:
            ilosc_udzialow = IloscUdzialowDlaAutoraZaCalosc.objects.get(
                autor=autor, dyscyplina_naukowa=dyscyplina
            )
            slot_maksymalny = ilosc_udzialow.ilosc_udzialow
        except IloscUdzialowDlaAutoraZaCalosc.DoesNotExist:
            # Jeśli nie ma wpisu, użyj domyślnej wartości 4
            slot_maksymalny = 4

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
        minimalny_pk=minimalny_pk,
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
        minimalny_pk=minimalny_pk,
        dyscyplina_id=dyscyplina.pk,
        akcja="wszystko",
    )

    # Calculate derived fields that would normally be calculated in save()
    # This is necessary because update_or_create doesn't trigger custom save() logic
    slot_nazbierany_decimal = Decimal(str(slot_nazbierany))
    slot_wszystkie_decimal = Decimal(str(slot_wszystkie))
    punkty_nazbierane_decimal = Decimal(str(punkty_nazbierane))
    punkty_wszystkie_decimal = Decimal(str(punkty_wszystkie))

    # Calculate averages
    if slot_nazbierany_decimal and slot_nazbierany_decimal > 0:
        srednia_za_slot_nazbierana = punkty_nazbierane_decimal / slot_nazbierany_decimal
    else:
        srednia_za_slot_nazbierana = Decimal("0")

    if slot_wszystkie_decimal and slot_wszystkie_decimal > 0:
        srednia_za_slot_wszystkie = punkty_wszystkie_decimal / slot_wszystkie_decimal
    else:
        srednia_za_slot_wszystkie = Decimal("0")

    # Calculate slot utilization percentage
    if slot_maksymalny and slot_maksymalny > 0:
        procent_wykorzystania_slotow = (slot_nazbierany_decimal / slot_maksymalny) * 100
    else:
        procent_wykorzystania_slotow = Decimal("0")

    # Utwórz lub zaktualizuj metrykę
    with transaction.atomic():
        metryka, created = MetrykaAutora.objects.update_or_create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            defaults={
                "jednostka": jednostka,
                "slot_maksymalny": slot_maksymalny,
                "slot_nazbierany": slot_nazbierany_decimal,
                "punkty_nazbierane": punkty_nazbierane_decimal,
                "prace_nazbierane": prace_nazbierane_ids,
                "slot_wszystkie": slot_wszystkie_decimal,
                "punkty_wszystkie": punkty_wszystkie_decimal,
                "prace_wszystkie": prace_wszystkie_ids,
                "liczba_prac_wszystkie": len(prace_wszystkie_ids),
                "rok_min": rok_min,
                "rok_max": rok_max,
                # Include calculated fields to ensure they're updated
                "srednia_za_slot_nazbierana": srednia_za_slot_nazbierana,
                "srednia_za_slot_wszystkie": srednia_za_slot_wszystkie,
                "procent_wykorzystania_slotow": procent_wykorzystania_slotow,
            },
        )

    return metryka, created


def przelicz_metryki_dla_publikacji(publikacja, rok_min=2022, rok_max=2025):
    """
    Przelicza metryki dla wszystkich autorów danej publikacji z przypisanymi dyscyplinami.

    UWAGA: Przelicza metryki dla WSZYSTKICH autorów, niezależnie od tego czy ich dyscyplina
    jest przypięta czy nie. Jest to konieczne, ponieważ zmiana statusu przypięcia jednego
    autora wpływa na dystrybucję slotów i punktów dla wszystkich pozostałych autorów.

    Args:
        publikacja: Obiekt publikacji (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji

    Returns:
        Lista tuple (autor, dyscyplina, metryka) dla przeliczonych metryk
    """
    results = []

    # Zbierz wszystkich unikalnych autorów z tej publikacji
    autorzy_do_przeliczenia = set()

    # Pobierz wszystkich autorów z dyscyplinami dla tej publikacji
    # NIE wykluczamy autorów bez dyscyplin - pobieramy wszystkich
    for autor_assignment in publikacja.autorzy_set.all():
        if autor_assignment.dyscyplina_naukowa is not None:
            autorzy_do_przeliczenia.add(
                (autor_assignment.autor, autor_assignment.dyscyplina_naukowa)
            )

    # Przelicz metryki dla wszystkich autorów
    for autor, dyscyplina in autorzy_do_przeliczenia:
        # Sprawdź czy autor ma rodzaj_autora='N' dla tego roku
        try:
            autor_dyscyplina = Autor_Dyscyplina.objects.get(
                autor=autor, rok=publikacja.rok, dyscyplina_naukowa=dyscyplina
            )

            if autor_dyscyplina.rodzaj_autora == "N":
                metryka, _ = oblicz_metryki_dla_autora(
                    autor=autor, dyscyplina=dyscyplina, rok_min=rok_min, rok_max=rok_max
                )
                results.append((autor, dyscyplina, metryka))
        except Autor_Dyscyplina.DoesNotExist:
            print(autor, "nie ma")
            # Jeśli nie ma wpisu Autor_Dyscyplina dla tego roku, pomiń
            continue

    return results


def generuj_metryki(
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=Decimal("0.01"),
    nadpisz=True,
    rodzaje_autora=None,
    progress_callback=None,
    logger_output=None,
    ilosc_udzialow_queryset=None,
):
    """
    Generuje metryki ewaluacyjne dla autorów.

    Wspólna funkcja używana przez zadanie Celery i komendę zarządzającą.

    Args:
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji
        minimalny_pk: Minimalny próg punktów
        nadpisz: Czy nadpisywać istniejące metryki
        rodzaje_autora: Lista rodzajów autorów do przetworzenia (domyślnie wszystkie)
        progress_callback: Funkcja callback do raportowania postępu (opcjonalne)
        logger_output: Obiekt do logowania wiadomości (opcjonalne, np. self.stdout z komendy)
        ilosc_udzialow_queryset: Opcjonalny queryset IloscUdzialowDlaAutoraZaCalosc (domyślnie wszystkie)

    Returns:
        Dict z kluczami:
            - processed: liczba przetworzonych autorów
            - skipped: liczba pominiętych autorów
            - errors: liczba błędów
            - total: całkowita liczba autorów do przetworzenia
    """
    if rodzaje_autora is None:
        rodzaje_autora = ["N", "D", "Z", " "]

    # Obsługa "brak danych" - dodaj możliwe reprezentacje
    if " " in rodzaje_autora:
        rodzaje_autora = list(rodzaje_autora)  # Skopiuj listę
        rodzaje_autora.append(None)
        rodzaje_autora.append("")

    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    # Pobierz autorów do przetworzenia
    if ilosc_udzialow_queryset is None:
        ilosc_udzialow_qs = IloscUdzialowDlaAutoraZaCalosc.objects.all()
    else:
        ilosc_udzialow_qs = ilosc_udzialow_queryset

    total = ilosc_udzialow_qs.count()

    logger.info(f"Znaleziono {total} autorów do przetworzenia")
    if logger_output:
        logger_output.write(f"Znaleziono {total} autorów do przetworzenia")

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

        # Wywołaj progress callback jeśli jest dostępny
        if progress_callback:
            try:
                progress_callback(
                    current=idx,
                    total=total,
                    autor=autor,
                    dyscyplina=dyscyplina,
                    processed=processed,
                )
            except Exception:
                pass  # Ignore errors in progress reporting

        try:
            with transaction.atomic():
                # Sprawdź rodzaj_autora
                autor_dyscyplina = (
                    Autor_Dyscyplina.objects.filter(
                        Q(autor=autor)
                        & (
                            Q(dyscyplina_naukowa=dyscyplina)
                            | Q(subdyscyplina_naukowa=dyscyplina)
                        )
                    )
                    .order_by("-rok")
                    .first()
                )

                # Sprawdź czy rodzaj autora jest na liście do przetworzenia
                if (
                    not autor_dyscyplina
                    or autor_dyscyplina.rodzaj_autora not in rodzaje_autora
                ):
                    skipped += 1
                    msg = (
                        f"Pominięto {autor} - {dyscyplina.nazwa}: rodzaj_autora = "
                        f"'{autor_dyscyplina.rodzaj_autora if autor_dyscyplina else 'autor_dyscyplina=None'}'"
                    )
                    logger.info(msg)
                    if logger_output:
                        logger_output.write(msg)
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
                    minimalny_pk=minimalny_pk,
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
                    minimalny_pk=minimalny_pk,
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
                action = "utworzono" if created else "zaktualizowano"
                msg = (
                    f"[{processed}/{total}] {action} metrykę dla {autor} - {dyscyplina.nazwa}: "
                    f"nazbierane {punkty_nazbierane:.2f} pkt / {slot_nazbierany:.2f} slotów, "
                    f"średnia {metryka.srednia_za_slot_nazbierana:.2f} pkt/slot"
                )
                logger.debug(msg)

        except Exception as e:
            errors += 1
            msg = f"Błąd przy przetwarzaniu {autor} - {dyscyplina.nazwa}: {str(e)}"
            logger.error(msg)
            if logger_output:
                logger_output.write(msg)

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "total": total,
    }
