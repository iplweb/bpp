"""
Funkcje wyszukiwania autorów z duplikatami.
"""

from bpp.models import Autor
from deduplikator_autorow.models import IgnoredAuthor
from pbn_api.models import OsobaZInstytucji, Scientist

from .analysis import autor_ma_publikacje_z_lat
from .search import szukaj_kopii


def znajdz_pierwszego_autora_z_duplikatami(  # noqa: C901
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

    # Pobierz IDs wykluczonych autorów
    excluded_scientist_ids = [author.pk for author in excluded_authors]

    # Pobierz IDs ignorowanych autorów
    ignored_scientist_ids = list(
        IgnoredAuthor.objects.values_list("scientist_id", flat=True)
    )

    # Przeszukaj wszystkie rekordy OsobaZInstytucji, wykluczając określonych autorów
    osoby_query = (
        OsobaZInstytucji.objects.select_related("personId").all().order_by("lastName")
    )

    # Exclude both explicitly excluded and ignored authors
    all_excluded_ids = excluded_scientist_ids + ignored_scientist_ids
    if all_excluded_ids:
        osoby_query = osoby_query.exclude(personId__pk__in=all_excluded_ids)

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

        # Jeśli znaleziono duplikaty
        if duplikaty.exists():
            # Sprawdź czy główny autor lub któryś z duplikatów ma publikacje z lat 2022-2025
            ma_nowe_publikacje = autor_ma_publikacje_z_lat(scientist.rekord_w_bpp)

            # Sprawdź również duplikaty
            if not ma_nowe_publikacje:
                for duplikat in duplikaty[
                    :10
                ]:  # Sprawdź pierwsze 10 duplikatów dla wydajności
                    if autor_ma_publikacje_z_lat(duplikat):
                        ma_nowe_publikacje = True
                        break

            # Dodaj do odpowiedniej listy
            if ma_nowe_publikacje:
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


def search_author_by_lastname(search_term, excluded_authors=None):  # noqa: C901
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
        # Sprawdź czy autor ma odpowiednik w Scientist
        if autor.pbn_uid_id:
            try:
                if autor.pbn_uid.osobazinstytucji:
                    duplikaty = szukaj_kopii(autor.pbn_uid.osobazinstytucji)
                    if duplikaty.exists():
                        # Sprawdź czy autor lub jego duplikaty mają publikacje z lat 2022-2025
                        ma_nowe_publikacje = autor_ma_publikacje_z_lat(autor)

                        # Sprawdź również duplikaty
                        if not ma_nowe_publikacje:
                            for duplikat in duplikaty[
                                :5
                            ]:  # Sprawdź pierwsze 5 duplikatów
                                if autor_ma_publikacje_z_lat(duplikat):
                                    ma_nowe_publikacje = True
                                    break

                        # Dodaj do odpowiedniej listy
                        if ma_nowe_publikacje:
                            autorzy_z_nowymi_publikacjami.append(autor.pbn_uid)
                        else:
                            autorzy_bez_nowych_publikacji.append(autor.pbn_uid)

                        # Jeśli mamy już 20 autorów z nowymi publikacjami, możemy zwrócić pierwszego
                        if len(autorzy_z_nowymi_publikacjami) >= 20:
                            return autorzy_z_nowymi_publikacjami[0]

            except Scientist.osobazinstytucji.RelatedObjectDoesNotExist:
                continue

    # Zwróć pierwszego autora z nowymi publikacjami, jeśli taki istnieje
    if autorzy_z_nowymi_publikacjami:
        return autorzy_z_nowymi_publikacjami[0]

    # W przeciwnym razie zwróć pierwszego autora bez nowych publikacji
    if autorzy_bez_nowych_publikacji:
        return autorzy_bez_nowych_publikacji[0]

    return None
