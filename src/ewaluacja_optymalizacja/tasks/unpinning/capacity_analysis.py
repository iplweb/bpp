"""
Analiza capacity-based unpinning dla optymalizacji ewaluacji.

Ten moduł implementuje algorytm unpinning oparty na regule pojemności (capacity rule):
dla każdej publikacji wieloautorskiej, zachowaj autora z NAJWIĘKSZĄ POZOSTAŁĄ POJEMNOŚCIĄ
(= 4.0 - current_slots), odpnij pozostałych.

Algorytm osiąga ~84% zgodności z decyzjami ludzkiego optymalizatora.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from bpp.models import Dyscyplina_Naukowa

logger = logging.getLogger(__name__)


@dataclass
class UnpinningCandidate:
    """Reprezentuje kandydata do unpinning wraz z metrykami."""

    publication_id: tuple  # (content_type_id, object_id)
    publication_title: str
    total_points: float
    keep_author_id: int
    keep_author_name: str
    keep_author_capacity: float  # Pozostała pojemność (4.0 - current_slots)
    keep_author_current_slots: float
    unpin_author_ids: list[int]
    unpin_author_names: list[str]
    unpin_author_slots: list[float]  # Obecne sloty autorów do odpięcia
    slot_gain: float  # Poprawa wartości slotu (np. 0.5 -> 1.0 = 0.5 gain)
    estimated_point_gain: float  # Szacowany zysk punktów


def calculate_author_slot_usage(
    author_id: int,
    dyscyplina: "Dyscyplina_Naukowa",
) -> tuple[float, float]:
    """
    Oblicz obecne użycie slotów dla autora w danej dyscyplinie.

    Args:
        author_id: ID autora
        dyscyplina: Obiekt Dyscyplina_Naukowa

    Returns:
        Tuple (current_slots, max_slots) gdzie:
        - current_slots: suma slotów z aktualnie przypisanych publikacji
        - max_slots: maksymalny limit slotów dla autora (zwykle 4.0)
    """
    from django.db.models import Sum

    from bpp.models import Cache_Punktacja_Autora_Query
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    # Pobierz limit slotów z IloscUdzialowDlaAutoraZaCalosc
    aggregated = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
        autor_id=author_id,
        dyscyplina_naukowa=dyscyplina,
    ).aggregate(total_slots=Sum("ilosc_udzialow"))

    if aggregated["total_slots"] is not None:
        max_slots = min(float(aggregated["total_slots"]), 4.0)
    else:
        max_slots = 4.0

    # Oblicz obecne użycie slotów z cache (publikacje z przypiętą dyscypliną)
    current_slots_agg = Cache_Punktacja_Autora_Query.objects.filter(
        autor_id=author_id,
        dyscyplina=dyscyplina,
        rekord__rok__gte=2022,
        rekord__rok__lte=2025,
    ).aggregate(total=Sum("slot"))

    current_slots = (
        float(current_slots_agg["total"])
        if current_slots_agg["total"] is not None
        else 0.0
    )

    return current_slots, max_slots


def calculate_author_capacity(
    author_id: int,
    dyscyplina: "Dyscyplina_Naukowa",
) -> float:
    """
    Oblicz pozostałą pojemność slotów dla autora (4.0 - użyte sloty).

    Args:
        author_id: ID autora
        dyscyplina: Obiekt Dyscyplina_Naukowa

    Returns:
        Pozostała pojemność (może być ujemna jeśli autor przekroczył limit)
    """
    current_slots, max_slots = calculate_author_slot_usage(author_id, dyscyplina)
    return max_slots - current_slots


def identify_unpinning_candidates(  # noqa: C901
    dyscyplina: "Dyscyplina_Naukowa",
) -> list[UnpinningCandidate]:
    """
    Analizuj wszystkie publikacje wieloautorskie i zidentyfikuj optymalne unpinning.

    Reguła (84% dokładności): Zachowaj autora z NAJWIĘKSZĄ POZOSTAŁĄ POJEMNOŚCIĄ.

    Args:
        dyscyplina: Obiekt Dyscyplina_Naukowa do analizy

    Returns:
        Lista obiektów UnpinningCandidate z rekomendacjami
    """
    from collections import defaultdict

    from bpp.models import Autor, Cache_Punktacja_Autora_Query, Rekord

    logger.info(f"Rozpoczynam analizę capacity-based unpinning dla {dyscyplina.nazwa}")

    # Pobierz wszystkie publikacje dla tej dyscypliny
    cache_entries = (
        Cache_Punktacja_Autora_Query.objects.filter(
            dyscyplina=dyscyplina,
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
        )
        .select_related("autor", "rekord")
        .exclude(pkdaut=0)
        .exclude(slot__lt=Decimal("0.1"))
    )

    # Grupuj publikacje po rekord_id
    pubs_by_rekord: dict[tuple, list] = defaultdict(list)
    for entry in cache_entries:
        pubs_by_rekord[entry.rekord_id].append(
            {
                "autor_id": entry.autor_id,
                "slot": float(entry.slot),
                "points": float(entry.pkdaut),
            }
        )

    logger.info(
        f"Znaleziono {len(pubs_by_rekord)} publikacji, "
        f"analizuję publikacje wieloautorskie..."
    )

    # Cache dla nazw autorów i pojemności
    author_names_cache: dict[int, str] = {}
    author_capacity_cache: dict[int, tuple[float, float]] = {}  # (current, max)

    def get_author_name(author_id: int) -> str:
        if author_id not in author_names_cache:
            try:
                autor = Autor.objects.get(pk=author_id)
                author_names_cache[author_id] = str(autor)
            except Autor.DoesNotExist:
                author_names_cache[author_id] = f"Autor #{author_id}"
        return author_names_cache[author_id]

    def get_author_capacity_info(
        author_id: int,
    ) -> tuple[float, float, float]:
        """Returns (current_slots, max_slots, remaining_capacity)"""
        if author_id not in author_capacity_cache:
            current, max_slots = calculate_author_slot_usage(author_id, dyscyplina)
            author_capacity_cache[author_id] = (current, max_slots)
        current, max_slots = author_capacity_cache[author_id]
        return current, max_slots, max_slots - current

    candidates = []

    # Cache dla tytułów publikacji
    rekord_ids = list(pubs_by_rekord.keys())
    rekord_titles = {}
    for rekord in Rekord.objects.filter(pk__in=rekord_ids):
        rekord_titles[rekord.pk] = rekord.tytul_oryginalny

    for rekord_id, authors_data in pubs_by_rekord.items():
        # Pomijaj publikacje jednoautorskie
        if len(authors_data) <= 1:
            continue

        # Pomijaj publikacje z tylko jednym unikalnym autorem
        distinct_authors = {a["autor_id"] for a in authors_data}
        if len(distinct_authors) <= 1:
            continue

        # Oblicz pojemność dla każdego autora
        authors_with_capacity = []
        for author_data in authors_data:
            author_id = author_data["autor_id"]
            current, max_slots, capacity = get_author_capacity_info(author_id)
            authors_with_capacity.append(
                {
                    "autor_id": author_id,
                    "slot": author_data["slot"],
                    "points": author_data["points"],
                    "current_slots": current,
                    "max_slots": max_slots,
                    "capacity": capacity,
                }
            )

        # Sortuj malejąco po pojemności - autor z największą pojemnością zachowuje
        authors_with_capacity.sort(key=lambda x: x["capacity"], reverse=True)

        # Pierwszy autor zachowuje publikację
        keeper = authors_with_capacity[0]
        to_unpin = authors_with_capacity[1:]

        # Pomijaj jeśli nie ma kogo odpiąć
        if not to_unpin:
            continue

        # Pomijaj jeśli keeper nie ma już miejsca na dodatkowy slot
        # (odpięcie nie da korzyści)
        if keeper["capacity"] <= 0:
            continue

        # Oblicz zysk slotu
        # Obecna wartość slotu = 1 / liczba_autorów
        # Po odpięciu = 1.0 (pełny slot dla keepera)
        current_slot_value = 1.0 / len(authors_data)
        new_slot_value = 1.0
        slot_gain = new_slot_value - current_slot_value

        # Szacowany zysk punktów = punkty publikacji * slot_gain
        # (zakładając że keeper ma miejsce na ten slot)
        total_points = sum(a["points"] for a in authors_data) / len(authors_data)
        estimated_point_gain = total_points * slot_gain

        candidates.append(
            UnpinningCandidate(
                publication_id=rekord_id,
                publication_title=rekord_titles.get(
                    rekord_id, f"Publikacja {rekord_id}"
                ),
                total_points=total_points,
                keep_author_id=keeper["autor_id"],
                keep_author_name=get_author_name(keeper["autor_id"]),
                keep_author_capacity=keeper["capacity"],
                keep_author_current_slots=keeper["current_slots"],
                unpin_author_ids=[a["autor_id"] for a in to_unpin],
                unpin_author_names=[get_author_name(a["autor_id"]) for a in to_unpin],
                unpin_author_slots=[a["current_slots"] for a in to_unpin],
                slot_gain=slot_gain,
                estimated_point_gain=estimated_point_gain,
            )
        )

    # Sortuj po szacowanym zysku punktów malejąco
    candidates.sort(key=lambda c: c.estimated_point_gain, reverse=True)

    logger.info(f"Znaleziono {len(candidates)} kandydatów do unpinning")

    return candidates


def apply_unpinning(
    candidates: list[UnpinningCandidate],
    dyscyplina: "Dyscyplina_Naukowa",
    dry_run: bool = True,
) -> dict:
    """
    Zastosuj decyzje unpinning w bazie danych.

    Args:
        candidates: Lista kandydatów do unpinning
        dyscyplina: Obiekt Dyscyplina_Naukowa
        dry_run: Jeśli True, cofnij transakcję na końcu (tylko podgląd)

    Returns:
        Słownik z podsumowaniem: {
            'total_candidates': int,
            'unpinned_count': int,
            'dry_run': bool
        }
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import (
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
    )

    # Pobierz ContentType IDs
    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    unpinned_count = 0
    errors = []

    with transaction.atomic():
        sid = transaction.savepoint() if dry_run else None

        for candidate in candidates:
            content_type_id, object_id = candidate.publication_id

            # Określ model na podstawie content_type
            if content_type_id == ct_ciagle.id:
                AutorModel = Wydawnictwo_Ciagle_Autor  # noqa: N806
            elif content_type_id == ct_zwarte.id:
                AutorModel = Wydawnictwo_Zwarte_Autor  # noqa: N806
            else:
                logger.warning(
                    f"Nieznany content_type_id {content_type_id} dla "
                    f"publikacji {candidate.publication_id}"
                )
                continue

            # Odpnij każdego autora z listy
            for author_id in candidate.unpin_author_ids:
                try:
                    updated = AutorModel.objects.filter(
                        rekord_id=object_id,
                        autor_id=author_id,
                        dyscyplina_naukowa=dyscyplina,
                        przypieta=True,
                    ).update(przypieta=False)

                    if updated > 0:
                        unpinned_count += updated
                        logger.debug(
                            f"Odpięto autora {author_id} z publikacji {object_id}"
                        )
                except Exception as e:
                    error_msg = (
                        f"Błąd przy odpinaniu autora {author_id} "
                        f"z publikacji {object_id}: {e}"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)

        if dry_run and sid is not None:
            transaction.savepoint_rollback(sid)
            logger.info(
                f"Dry-run: cofnięto transakcję, odpięto by {unpinned_count} przypisań"
            )
        else:
            logger.info(f"Zastosowano unpinning dla {unpinned_count} przypisań")

    return {
        "total_candidates": len(candidates),
        "unpinned_count": unpinned_count,
        "dry_run": dry_run,
        "errors": errors,
    }


def format_unpinning_preview(
    candidates: list[UnpinningCandidate],
    max_display: int = 20,
) -> str:
    """
    Sformatuj podgląd rekomendacji unpinning do wyświetlenia.

    Args:
        candidates: Lista kandydatów do unpinning
        max_display: Maksymalna liczba kandydatów do wyświetlenia

    Returns:
        Sformatowany tekst z podsumowaniem i szczegółami
    """
    if not candidates:
        return "Brak kandydatów do unpinning."

    lines = []

    # Nagłówek
    lines.append("=" * 80)
    lines.append("ANALIZA CAPACITY-BASED UNPINNING")
    lines.append("=" * 80)

    # Podsumowanie
    total_slot_gain = sum(c.slot_gain for c in candidates)
    total_point_gain = sum(c.estimated_point_gain for c in candidates)
    total_authors_to_unpin = sum(len(c.unpin_author_ids) for c in candidates)

    lines.append(f"Znaleziono {len(candidates)} publikacji do optymalizacji")
    lines.append(f"Łączna liczba autorów do odpięcia: {total_authors_to_unpin}")
    lines.append(f"Szacowana poprawa slotów: +{total_slot_gain:.2f}")
    lines.append(f"Szacowany zysk punktów: +{total_point_gain:.1f}")
    lines.append("")

    # Szczegóły
    lines.append("SZCZEGÓŁY (posortowane wg szacowanego zysku):")
    lines.append("-" * 80)

    for i, c in enumerate(candidates[:max_display], 1):
        title_short = (
            c.publication_title[:50] + "..."
            if len(c.publication_title) > 50
            else c.publication_title
        )
        lines.append(f"\n{i}. {title_short}")
        lines.append(
            f"   Zachowaj: {c.keep_author_name} "
            f"(pojemność: {c.keep_author_capacity:.2f}, "
            f"sloty: {c.keep_author_current_slots:.2f})"
        )
        lines.append(f"   Odpnij: {', '.join(c.unpin_author_names)}")
        lines.append(
            f"   Zysk slotu: {c.slot_gain:.2f}, Szac. punkty: +{c.estimated_point_gain:.1f}"
        )

    if len(candidates) > max_display:
        lines.append(f"\n... i {len(candidates) - max_display} więcej")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)
