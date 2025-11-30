"""
Data loading functions for evaluation optimization.

This module contains functions for loading publication and author data
from the database.
"""

from decimal import Decimal

from django.db.models import Sum
from tqdm import tqdm

from bpp import const
from bpp.models import Cache_Punktacja_Autora_Query, Dyscyplina_Naukowa
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

from .data_structures import Pub


def generate_pub_data(dyscyplina_nazwa: str, verbose: bool = False) -> list[Pub]:
    """
    Generate publication data from cache_punktacja_autora table.

    Args:
        dyscyplina_nazwa: Name of the scientific discipline to filter by
        verbose: Show progress bar if True

    Returns:
        List of Pub objects with data from database
    """
    # Get discipline object
    try:
        dyscyplina = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)
    except Dyscyplina_Naukowa.DoesNotExist as e:
        raise ValueError(
            f"Discipline '{dyscyplina_nazwa}' not found in database"
        ) from e

    # Query cache data for years 2022-2025 and given discipline
    cache_entries = (
        Cache_Punktacja_Autora_Query.objects.filter(
            dyscyplina=dyscyplina,
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
        )
        .select_related(
            "autor",
            "rekord",
        )
        .exclude(pkdaut=0)  # Exclude publications with 0 points
        .exclude(slot__lt=Decimal("0.1"))  # Exclude publications with 0 slots
    )

    # Build a dictionary mapping autor_id to jest_w_n status
    # Query all authors' rodzaj_autora for this discipline
    autor_jest_w_n = {}
    autor_ids = cache_entries.values_list("autor_id", flat=True).distinct()

    for autor_id in autor_ids:
        record = (
            IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                autor_id=autor_id,
                dyscyplina_naukowa=dyscyplina,
            )
            .select_related("rodzaj_autora")
            .order_by("-ilosc_udzialow")
            .first()
        )

        # Default to False if no record or no rodzaj_autora
        if record and record.rodzaj_autora:
            autor_jest_w_n[autor_id] = record.rodzaj_autora.jest_w_n
        else:
            autor_jest_w_n[autor_id] = False

    pubs = []
    iterator = tqdm(cache_entries) if verbose else cache_entries
    for entry in iterator:
        rekord = entry.rekord

        # Determine publication kind based on charakter_ogolny
        charakter_ogolny = rekord.charakter_formalny.charakter_ogolny
        if charakter_ogolny == const.CHARAKTER_OGOLNY_ARTYKUL:
            kind = "article"
        elif charakter_ogolny == const.CHARAKTER_OGOLNY_KSIAZKA:
            kind = "monography"
        else:
            # Skip other types (chapters, etc.)
            continue

        # Count authors with pinned disciplines
        author_count = rekord.original.autorzy_set.filter(
            dyscyplina_naukowa__isnull=False, przypieta=True
        ).count()

        pub = Pub(
            id=entry.rekord_id,  # This is already a tuple
            author=entry.autor_id,
            kind=kind,
            points=float(entry.pkdaut),
            base_slots=round(float(entry.slot), 2),  # Round to 2 decimal places
            author_count=author_count,
            jest_w_n=autor_jest_w_n.get(entry.autor_id, False),
        )
        pubs.append(pub)

    return pubs


def load_author_slot_limits(authors: list[int], dyscyplina_obj, log_func) -> dict:
    """
    Load per-author slot limits from database.

    Args:
        authors: List of author IDs
        dyscyplina_obj: Dyscyplina_Naukowa object
        log_func: Function to call for logging

    Returns:
        Dictionary mapping author_id to {"total": float, "mono": float}
    """
    log_func("Loading author slot limits from database...")
    author_slot_limits = {}
    custom_limit_count = 0

    for author_id in authors:
        # Aggregate slot limits across all rodzaj_autora types for this author
        aggregated = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
            autor_id=author_id,
            dyscyplina_naukowa=dyscyplina_obj,
        ).aggregate(
            total_slots=Sum("ilosc_udzialow"),
            total_mono_slots=Sum("ilosc_udzialow_monografie"),
        )

        if aggregated["total_slots"] is not None:
            # Apply regulatory caps: max 4.0 total, max 2.0 monographs
            total = min(round(float(aggregated["total_slots"]), 2), 4.0)
            mono = min(round(float(aggregated["total_mono_slots"]), 2), 2.0)

            author_slot_limits[author_id] = {"total": total, "mono": mono}
            custom_limit_count += 1
        else:
            # Use default limits if not specified
            author_slot_limits[author_id] = {"total": 4.0, "mono": 2.0}

    log_func(f"Found custom slot limits for {custom_limit_count} authors")
    return author_slot_limits
