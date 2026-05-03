"""Helpery filtrów do listy publikacji w przeglądarce."""

from bpp.models import (
    Autor_Dyscyplina,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)


def _apply_dyscyplina_nieprzypisana_filter(ciagle_qs, zwarte_qs, filters):
    """Zastosuj filtr po dyscyplinie nieprzypisanej.

    Filtr znajduje publikacje gdzie:
    1. Autor jest DWUDYSCYPLINOWCEM (ma zarówno główną jak i subdyscyplinę)
    2. Ma dyscyplinę X w profilu (główną lub sub) na dany rok
    3. ALE publikacja ma przypisaną dyscyplinę Y (INNĄ niż X)

    Celem jest znajdowanie "niewykorzystanych możliwości" - autorów
    dwudyscyplinowców, którzy mogli użyć dyscypliny X, ale przypisali Y.
    """
    from django.db.models import Q

    dyscyplina_nieprzypisana = filters.get("dyscyplina_nieprzypisana")
    rok = filters.get("rok")

    if not dyscyplina_nieprzypisana:
        return ciagle_qs, zwarte_qs

    dyscyplina_nieprzypisana_id = int(dyscyplina_nieprzypisana)
    lata_filtra = [int(rok)] if rok else [2022, 2023, 2024, 2025]

    # Znajdz DWUDYSCYPLINOWCÓW z dana dyscyplina (glowna lub subdyscyplina)
    # Wymagamy subdyscyplina_naukowa__isnull=False - autor musi mieć dwie dyscypliny
    autorzy_dwudyscyplinowcy = Autor_Dyscyplina.objects.filter(
        Q(dyscyplina_naukowa_id=dyscyplina_nieprzypisana_id)
        | Q(subdyscyplina_naukowa_id=dyscyplina_nieprzypisana_id),
        rok__in=lata_filtra,
        subdyscyplina_naukowa__isnull=False,
    ).values_list("autor_id", flat=True)

    # Filtruj publikacje gdzie autor ma INNĄ dyscyplinę przypisaną
    # Wykluczamy publikacje gdzie przypisana dyscyplina = szukana dyscyplina
    ciagle_with_dysc = (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor_id__in=autorzy_dwudyscyplinowcy,
            afiliuje=True,
            zatrudniony=True,
        )
        .exclude(dyscyplina_naukowa_id=dyscyplina_nieprzypisana_id)
        .values_list("rekord_id", flat=True)
    )
    ciagle_qs = ciagle_qs.filter(pk__in=ciagle_with_dysc)

    zwarte_with_dysc = (
        Wydawnictwo_Zwarte_Autor.objects.filter(
            autor_id__in=autorzy_dwudyscyplinowcy,
            afiliuje=True,
            zatrudniony=True,
        )
        .exclude(dyscyplina_naukowa_id=dyscyplina_nieprzypisana_id)
        .values_list("rekord_id", flat=True)
    )
    zwarte_qs = zwarte_qs.filter(pk__in=zwarte_with_dysc)

    return ciagle_qs, zwarte_qs


def _build_base_filter(filters):
    """Zbuduj bazowy filtr dla publikacji."""
    from decimal import Decimal, InvalidOperation

    rok = filters.get("rok")
    punkty_od = filters.get("punkty_od")
    punkty_do = filters.get("punkty_do")

    base_filter = {"rok__in": [2022, 2023, 2024, 2025]}
    if rok:
        base_filter["rok"] = int(rok)

    if punkty_od:
        try:
            base_filter["punkty_kbn__gte"] = Decimal(punkty_od)
        except InvalidOperation:
            pass  # Ignoruj nieprawidłowe wartości
    if punkty_do:
        try:
            base_filter["punkty_kbn__lte"] = Decimal(punkty_do)
        except InvalidOperation:
            pass  # Ignoruj nieprawidłowe wartości

    return base_filter


def _build_author_filter(filters, reported_ids):
    """Zbuduj filtr dla autorów publikacji."""
    dyscyplina = filters.get("dyscyplina")
    nazwisko = (filters.get("nazwisko") or "").strip()

    author_filter = {
        "afiliuje": True,
        "zatrudniony": True,
        "dyscyplina_naukowa_id__in": reported_ids,
    }
    if dyscyplina:
        author_filter["dyscyplina_naukowa_id"] = int(dyscyplina)
    if nazwisko:
        author_filter["autor__nazwisko__icontains"] = nazwisko

    return author_filter
