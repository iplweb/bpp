"""
Funkcje zliczania autorów z duplikatami.
"""

from cacheops import cached

from bpp.models import Autor
from pbn_api.models import OsobaZInstytucji, Scientist

from .search import szukaj_kopii


@cached(timeout=5 * 60)
def count_authors_with_duplicates() -> int:
    """
    Zlicza wszystkich autorów (Scientist), którzy mają potencjalne duplikaty w systemie BPP.

    Returns:
        int: Liczba autorów z duplikatami
    """
    count = 0

    # Przeszukaj wszystkie rekordy OsobaZInstytucji
    for osoba_z_instytucji in OsobaZInstytucji.objects.select_related("personId").all():
        # Sprawdź czy istnieje Scientist dla tej osoby
        if not osoba_z_instytucji.personId:
            continue

        scientist = osoba_z_instytucji.personId

        # Sprawdź czy Scientist ma odpowiednik w BPP
        if not hasattr(scientist, "rekord_w_bpp") or not scientist.rekord_w_bpp:
            continue

        # Wyszukaj duplikaty dla tego autora
        duplikaty = szukaj_kopii(osoba_z_instytucji)

        # Jeśli znaleziono duplikaty, zwiększ licznik
        if duplikaty.exists():
            count += 1

    return count


def count_authors_with_lastname(search_term):
    """
    Zlicza autorów o nazwisku zawierającym wyszukiwany termin, którzy mają duplikaty.

    Args:
        search_term: część nazwiska do wyszukania

    Returns:
        liczba autorów z duplikatami pasujących do wyszukiwania
    """
    if not search_term:
        return 0

    count = 0

    # Wyszukaj autorów z BPP o nazwisku zawierającym wyszukiwany termin
    matching_authors = Autor.objects.filter(
        nazwisko__icontains=search_term
    ).select_related("pbn_uid", "pbn_uid__osobazinstytucji")

    for autor in matching_authors[:100]:
        scientist = autor.pbn_uid
        if scientist is None:
            continue

        # Sprawdź czy ma duplikaty
        try:
            if scientist.osobazinstytucji:
                duplikaty = szukaj_kopii(scientist.osobazinstytucji)
                if duplikaty.exists():
                    count += 1
        except Scientist.osobazinstytucji.RelatedObjectDoesNotExist:
            continue

    return count
