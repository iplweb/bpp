"""Widoki weryfikacji bazy danych."""

import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

logger = logging.getLogger(__name__)


@login_required
def database_verification_view(request):
    """
    Wyświetla listę prac z autorami mającymi sloty poniżej 0.1 w latach 2022-2025.
    Takie sloty należy usunąć przed dalszymi krokami optymalizacji.
    """
    from bpp.models import Autor_Dyscyplina, Cache_Punktacja_Autora_Query

    # Pobierz autorów którzy mają przypisane dyscypliny w latach 2022-2025
    autorzy_z_dyscyplinami = set(
        Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
        .values_list("autor_id", flat=True)
        .distinct()
    )

    # Zapytanie o prace z problemowymi slotami
    problematic_records = (
        Cache_Punktacja_Autora_Query.objects.filter(
            slot__lt=Decimal("0.1"),
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
            autor_id__in=autorzy_z_dyscyplinami,
        )
        .select_related("rekord", "autor", "dyscyplina")
        .order_by("slot", "rekord__rok", "autor__nazwisko")
    )

    # Statystyki
    total_count = problematic_records.count()
    unique_works = problematic_records.values("rekord_id").distinct().count()
    unique_authors = problematic_records.values("autor_id").distinct().count()

    context = {
        "problematic_records": problematic_records,
        "total_count": total_count,
        "unique_works": unique_works,
        "unique_authors": unique_authors,
    }

    return render(
        request, "ewaluacja_optymalizacja/database_verification.html", context
    )
