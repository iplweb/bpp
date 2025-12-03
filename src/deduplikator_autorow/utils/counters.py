"""
Funkcje zliczania autorów z duplikatami.
"""

from django.db.models import Q

from ..models import DuplicateCandidate, DuplicateScanRun


def get_latest_completed_scan():
    """
    Pobiera ostatnie zakończone skanowanie.

    Returns:
        DuplicateScanRun lub None
    """
    return (
        DuplicateScanRun.objects.filter(status=DuplicateScanRun.Status.COMPLETED)
        .order_by("-finished_at")
        .first()
    )


def get_latest_scan_stats():
    """
    Pobiera statystyki ostatniego skanowania.

    Returns:
        dict z kluczami: scan, pending_count, total_count lub None jeśli brak skanów
    """
    scan = get_latest_completed_scan()
    if not scan:
        return None

    pending_count = DuplicateCandidate.objects.filter(
        scan_run=scan, status=DuplicateCandidate.Status.PENDING
    ).count()

    total_count = DuplicateCandidate.objects.filter(scan_run=scan).count()

    return {
        "scan": scan,
        "pending_count": pending_count,
        "total_count": total_count,
    }


def count_authors_with_duplicates() -> int:
    """
    Zlicza liczbę oczekujących kandydatów na duplikaty z ostatniego skanowania.

    Zwraca liczbę unikalnych autorów głównych, którzy mają pending duplikaty.

    Returns:
        int: Liczba autorów z duplikatami do sprawdzenia
    """
    scan = get_latest_completed_scan()
    if not scan:
        return 0

    # Zlicz unikalne wartości main_autor dla kandydatów PENDING
    return (
        DuplicateCandidate.objects.filter(
            scan_run=scan, status=DuplicateCandidate.Status.PENDING
        )
        .values("main_autor")
        .distinct()
        .count()
    )


def count_pending_candidates() -> int:
    """
    Zlicza wszystkie oczekujące kandydaty na duplikaty.

    Returns:
        int: Liczba kandydatów do sprawdzenia
    """
    scan = get_latest_completed_scan()
    if not scan:
        return 0

    return DuplicateCandidate.objects.filter(
        scan_run=scan, status=DuplicateCandidate.Status.PENDING
    ).count()


def count_authors_with_lastname(search_term: str) -> int:
    """
    Zlicza autorów o nazwisku zawierającym wyszukiwany termin, którzy mają duplikaty.

    Wyszukuje w zapisanych wynikach skanowania (DuplicateCandidate).

    Args:
        search_term: część nazwiska do wyszukania

    Returns:
        liczba autorów z duplikatami pasujących do wyszukiwania
    """
    if not search_term:
        return 0

    scan = get_latest_completed_scan()
    if not scan:
        return 0

    # Wyszukaj autorów pasujących do search_term (zarówno głównych jak i duplikatów)
    # w zapisanych nazwach kandydatów
    matching_candidates = DuplicateCandidate.objects.filter(
        scan_run=scan,
        status=DuplicateCandidate.Status.PENDING,
    ).filter(
        Q(main_autor_name__icontains=search_term)
        | Q(duplicate_autor_name__icontains=search_term)
    )

    # Zlicz unikalne wartości main_autor
    return matching_candidates.values("main_autor").distinct().count()


def get_candidates_for_author(autor_id: int):
    """
    Pobiera wszystkich kandydatów na duplikaty dla danego autora głównego.

    Args:
        autor_id: ID autora głównego (bpp.Autor)

    Returns:
        QuerySet z DuplicateCandidate lub pusty QuerySet
    """
    scan = get_latest_completed_scan()
    if not scan:
        return DuplicateCandidate.objects.none()

    return DuplicateCandidate.objects.filter(
        scan_run=scan,
        main_autor_id=autor_id,
        status=DuplicateCandidate.Status.PENDING,
    ).order_by("-confidence_score")


def search_candidates_by_lastname(search_term: str, limit: int = 100):
    """
    Wyszukuje kandydatów na duplikaty po nazwisku.

    Args:
        search_term: część nazwiska do wyszukania
        limit: maksymalna liczba wyników

    Returns:
        QuerySet z DuplicateCandidate
    """
    if not search_term:
        return DuplicateCandidate.objects.none()

    scan = get_latest_completed_scan()
    if not scan:
        return DuplicateCandidate.objects.none()

    return (
        DuplicateCandidate.objects.filter(
            scan_run=scan,
            status=DuplicateCandidate.Status.PENDING,
        )
        .filter(
            Q(main_autor_name__icontains=search_term)
            | Q(duplicate_autor_name__icontains=search_term)
        )
        .select_related("main_autor", "duplicate_autor")
        .order_by("-confidence_score")[:limit]
    )
