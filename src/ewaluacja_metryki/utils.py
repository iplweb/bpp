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

    # Utwórz lub zaktualizuj metrykę
    with transaction.atomic():
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

    return metryka, created


def przelicz_metryki_dla_publikacji(publikacja, rok_min=2022, rok_max=2025):
    """
    Przelicza metryki dla wszystkich autorów danej publikacji z przypisanymi dyscyplinami.

    Args:
        publikacja: Obiekt publikacji (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)
        rok_min: Początkowy rok okresu ewaluacji
        rok_max: Końcowy rok okresu ewaluacji

    Returns:
        Lista tuple (autor, dyscyplina, metryka) dla przeliczonych metryk
    """
    results = []

    # Pobierz wszystkich autorów z dyscyplinami dla tej publikacji
    for autor_assignment in publikacja.autorzy_set.exclude(dyscyplina_naukowa=None):
        autor = autor_assignment.autor
        dyscyplina = autor_assignment.dyscyplina_naukowa

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
