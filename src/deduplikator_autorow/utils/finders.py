"""
Funkcje wyszukiwania autorów z duplikatami.
"""

from bpp.models import Autor
from deduplikator_autorow.models import IgnoredScientist
from pbn_api.models import OsobaZInstytucji, Scientist

from .analysis import autor_ma_publikacje_z_lat
from .search import szukaj_kopii


def _ma_nowe_publikacje(rekord_w_bpp, duplikaty, limit: int) -> bool:
    """
    Czy główny autor (rekord_w_bpp) lub którykolwiek z pierwszych ``limit``
    duplikatów ma publikacje z lat 2022-2025.
    """
    if autor_ma_publikacje_z_lat(rekord_w_bpp):
        return True
    for duplikat in duplikaty[:limit]:
        if autor_ma_publikacje_z_lat(duplikat):
            return True
    return False


def _osoby_z_instytucji_query(excluded_authors: list[Scientist]):
    """
    Buduje queryset OsobaZInstytucji (posortowany po nazwisku) z wykluczeniem
    autorów jawnie wskazanych oraz ignorowanych (IgnoredScientist).
    """
    excluded_scientist_ids = [author.pk for author in excluded_authors]
    ignored_scientist_ids = list(
        IgnoredScientist.objects.values_list("scientist_id", flat=True)
    )

    osoby_query = (
        OsobaZInstytucji.objects.select_related("personId").all().order_by("lastName")
    )

    all_excluded_ids = excluded_scientist_ids + ignored_scientist_ids
    if all_excluded_ids:
        osoby_query = osoby_query.exclude(personId__pk__in=all_excluded_ids)

    return osoby_query


def znajdz_pierwszego_autora_z_duplikatami(
    excluded_authors: list[Scientist] | None = None,
) -> Scientist | None:
    """
    Znajduje pierwszego autora (Scientist), który ma możliwe duplikaty w systemie BPP.
    Priorytetyzuje autorów z publikacjami z lat 2022-2025.

    Funkcja iteruje przez wszystkie rekordy OsobaZInstytucji i dla każdego sprawdza,
    czy istnieją potencjalne duplikaty używając funkcji szukaj_kopii().

    Args:
        excluded_authors: Lista autorów (Scientist), którzy mają być wykluczeni
                         z wyszukiwania duplikatów. Domyślnie None.

    Returns:
        Optional[Scientist]: Pierwszy znaleziony autor z duplikatami lub None,
                            jeśli nie znaleziono żadnego autora z duplikatami.
    """
    if excluded_authors is None:
        excluded_authors = []

    # Przeszukaj wszystkie rekordy OsobaZInstytucji, wykluczając określonych
    # i ignorowanych autorów
    osoby_query = _osoby_z_instytucji_query(excluded_authors)

    # Zbierz autorów z duplikatami, podzielonych na dwie grupy
    autorzy_z_nowymi_publikacjami = []
    autorzy_bez_nowych_publikacji = []

    for osoba_z_instytucji in osoby_query:
        # Sprawdź czy istnieje Scientist dla tej osoby
        if not osoba_z_instytucji.personId:
            continue

        scientist = osoba_z_instytucji.personId

        # Sprawdź czy Scientist ma odpowiednik w BPP
        if not hasattr(scientist, "rekord_w_bpp") or not scientist.rekord_w_bpp:
            continue

        # Wyszukaj duplikaty dla tego autora
        duplikaty = szukaj_kopii(osoba_z_instytucji)

        if not duplikaty.exists():
            continue

        # Sprawdź czy główny autor lub któryś z pierwszych 10 duplikatów ma
        # publikacje z lat 2022-2025 i dodaj do odpowiedniej grupy
        if _ma_nowe_publikacje(scientist.rekord_w_bpp, duplikaty, 10):
            autorzy_z_nowymi_publikacjami.append(scientist)
        else:
            autorzy_bez_nowych_publikacji.append(scientist)

        # Jeśli mamy już 50 autorów z nowymi publikacjami, możemy zwrócić pierwszego
        # (optymalizacja dla dużych baz danych)
        if len(autorzy_z_nowymi_publikacjami) >= 50:
            return autorzy_z_nowymi_publikacjami[0]

    # Zwróć pierwszego autora z nowymi publikacjami, jeśli taki istnieje
    if autorzy_z_nowymi_publikacjami:
        return autorzy_z_nowymi_publikacjami[0]

    # W przeciwnym razie zwróć pierwszego autora bez nowych publikacji
    if autorzy_bez_nowych_publikacji:
        return autorzy_bez_nowych_publikacji[0]

    # Jeśli nie znaleziono żadnego autora z duplikatami
    return None


def _osoba_z_instytucji_autora(autor) -> OsobaZInstytucji | None:
    """
    Zwraca OsobaZInstytucji powiązaną z autorem przez pbn_uid (Scientist),
    albo None jeśli autor nie ma pbn_uid lub powiązanej OsobaZInstytucji.
    """
    if not autor.pbn_uid_id:
        return None
    try:
        return autor.pbn_uid.osobazinstytucji
    except Scientist.osobazinstytucji.RelatedObjectDoesNotExist:
        return None


def search_author_by_lastname(search_term, excluded_authors=None):
    """
    Wyszukuje pierwszego autora z duplikatami według części nazwiska.
    Priorytetyzuje autorów z publikacjami z lat 2022-2025.

    Args:
        search_term: część nazwiska do wyszukania
        excluded_authors: lista autorów do wykluczenia

    Returns:
        Scientist object lub None jeśli nie znaleziono
    """
    if not search_term:
        return None

    if excluded_authors is None:
        excluded_authors = []

    excluded_ids = [author.pk for author in excluded_authors if hasattr(author, "pk")]

    # Wyszukaj autorów z BPP o nazwisku zawierającym wyszukiwany termin
    matching_authors = (
        Autor.objects.filter(nazwisko__icontains=search_term)
        .exclude(pbn_uid_id__in=excluded_ids)
        .select_related("pbn_uid", "pbn_uid__osobazinstytucji")
    )

    # Zbierz autorów z duplikatami, podzielonych na dwie grupy
    autorzy_z_nowymi_publikacjami = []
    autorzy_bez_nowych_publikacji = []

    # Znajdź autorów z duplikatami i podziel ich na grupy
    for autor in matching_authors[:200]:  # Sprawdź więcej autorów niż poprzednio
        osoba_z_instytucji = _osoba_z_instytucji_autora(autor)
        if not osoba_z_instytucji:
            continue

        duplikaty = szukaj_kopii(osoba_z_instytucji)
        if not duplikaty.exists():
            continue

        # Sprawdź czy autor lub pierwszych 5 duplikatów ma publikacje 2022-2025
        if _ma_nowe_publikacje(autor, duplikaty, 5):
            autorzy_z_nowymi_publikacjami.append(autor.pbn_uid)
        else:
            autorzy_bez_nowych_publikacji.append(autor.pbn_uid)

        # Jeśli mamy już 20 autorów z nowymi publikacjami, możemy zwrócić pierwszego
        if len(autorzy_z_nowymi_publikacjami) >= 20:
            return autorzy_z_nowymi_publikacjami[0]

    # Zwróć pierwszego autora z nowymi publikacjami, jeśli taki istnieje
    if autorzy_z_nowymi_publikacjami:
        return autorzy_z_nowymi_publikacjami[0]

    # W przeciwnym razie zwróć pierwszego autora bez nowych publikacji
    if autorzy_bez_nowych_publikacji:
        return autorzy_bez_nowych_publikacji[0]

    return None
