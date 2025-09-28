from decimal import Decimal

from django.db import transaction

from .models import MetrykaAutora

from bpp.models import Autor_Dyscyplina


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
