"""Widoki weryfikacji bazy danych."""

import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from ewaluacja_common.okres import okres_dla_request

from ..okres import filtr_lat

logger = logging.getLogger(__name__)


@login_required
def database_verification_view(request):
    """
    Wyświetla listę prac z autorami mającymi sloty poniżej 0.1 w latach
    wybranego okresu ewaluacji. Takie sloty należy usunąć przed dalszymi
    krokami optymalizacji.
    """
    from bpp.models import Autor_Dyscyplina, Cache_Punktacja_Autora_Query

    okres = okres_dla_request(request)

    # Pobierz autorów którzy mają przypisane dyscypliny w latach okresu
    autorzy_z_dyscyplinami = set(
        Autor_Dyscyplina.objects.filter(**filtr_lat(okres))
        .values_list("autor_id", flat=True)
        .distinct()
    )

    # Zapytanie o prace z problemowymi slotami
    problematic_records = (
        Cache_Punktacja_Autora_Query.objects.filter(
            slot__lt=Decimal("0.1"),
            **filtr_lat(okres, "rekord__"),
            autor_id__in=autorzy_z_dyscyplinami,
        )
        .select_related("rekord", "autor", "dyscyplina")
        .order_by("slot", "rekord__rok", "autor__nazwisko")
    )

    # Statystyki
    total_count = problematic_records.count()
    unique_works = problematic_records.values("rekord_id").distinct().count()
    unique_authors = problematic_records.values("autor_id").distinct().count()

    # Prace z dyscypliną naukową ustawioną, ale bez przypięcia (przypieta=False)
    nieprzypiete_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
        dyscyplina_naukowa__isnull=False,
        przypieta=False,
        **filtr_lat(okres, "rekord__"),
    ).select_related("rekord", "autor", "dyscyplina_naukowa")

    nieprzypiete_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
        dyscyplina_naukowa__isnull=False,
        przypieta=False,
        **filtr_lat(okres, "rekord__"),
    ).select_related("rekord", "autor", "dyscyplina_naukowa")

    # Liczba publikacji z lat okresu, gdzie autor ma dyscyplinę, ale brak daty
    # oświadczenia
    brak_oswiadczenia_ciagle_count = (
        Wydawnictwo_Ciagle.objects.filter(
            **filtr_lat(okres),
            autorzy_set__dyscyplina_naukowa__isnull=False,
            autorzy_set__data_oswiadczenia__isnull=True,
        )
        .distinct()
        .count()
    )

    brak_oswiadczenia_zwarte_count = (
        Wydawnictwo_Zwarte.objects.filter(
            **filtr_lat(okres),
            autorzy_set__dyscyplina_naukowa__isnull=False,
            autorzy_set__data_oswiadczenia__isnull=True,
        )
        .distinct()
        .count()
    )

    context = {
        "okres": okres,
        "problematic_records": problematic_records,
        "total_count": total_count,
        "unique_works": unique_works,
        "unique_authors": unique_authors,
        "nieprzypiete_ciagle": nieprzypiete_ciagle,
        "nieprzypiete_zwarte": nieprzypiete_zwarte,
        "brak_oswiadczenia_ciagle_count": brak_oswiadczenia_ciagle_count,
        "brak_oswiadczenia_zwarte_count": brak_oswiadczenia_zwarte_count,
    }

    return render(
        request, "ewaluacja_optymalizacja/database_verification.html", context
    )
