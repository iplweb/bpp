"""Matchowanie autorów po identyfikatorach (BPP id / ORCID / PBN UID /
system kadrowy / PBN id) oraz po imieniu+nazwisku z kontekstem
(jednostka, tytuł).
"""

from django.contrib.postgres.lookups import Unaccent
from django.db.models import Q
from django.db.models.functions import Lower

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_common.normalization import (
    polish_english_first_name_variants,
    remove_polish_diacritics,
)


def _try_get_autor_by_bpp_id(bpp_id: int | None) -> Autor | None:
    """Próbuje pobrać autora po bpp_id."""
    if bpp_id is None:
        return None
    try:
        return Autor.objects.get(pk=bpp_id)
    except Autor.DoesNotExist:
        return None


def _try_get_autor_by_orcid(orcid: str | None) -> Autor | None:
    """Próbuje pobrać autora po ORCID."""
    if not orcid:
        return None
    try:
        return Autor.objects.get(orcid__iexact=orcid.strip())
    except Autor.DoesNotExist:
        return None


def _try_get_autor_by_pbn_uid_id(pbn_uid_id: str | None) -> Autor | None:
    """Próbuje pobrać autora po pbn_uid_id."""
    if pbn_uid_id is None or pbn_uid_id.strip() == "":
        return None
    return Autor.objects.filter(pbn_uid_id=pbn_uid_id).first()


def _try_get_autor_by_system_kadrowy_id(system_kadrowy_id) -> Autor | None:
    """Próbuje pobrać autora po system_kadrowy_id."""
    if system_kadrowy_id is None:
        return None
    try:
        return Autor.objects.get(system_kadrowy_id=int(system_kadrowy_id))
    except (TypeError, ValueError, Autor.DoesNotExist):
        return None


def _try_get_autor_by_pbn_id(pbn_id) -> Autor | None:
    """Próbuje pobrać autora po pbn_id."""
    if pbn_id is None:
        return None
    if isinstance(pbn_id, str):
        pbn_id = pbn_id.strip()
    try:
        return Autor.objects.get(pbn_id=int(pbn_id))
    except (TypeError, ValueError, Autor.DoesNotExist):
        return None


def _try_match_autor_by_direct_ids(
    bpp_id: int | None,
    orcid: str | None,
    pbn_uid_id: str | None,
    system_kadrowy_id: int | None,
    pbn_id: int | None,
) -> Autor | None:
    """Próbuje dopasować autora po różnych identyfikatorach."""
    return (
        _try_get_autor_by_bpp_id(bpp_id)
        or _try_get_autor_by_orcid(orcid)
        or _try_get_autor_by_pbn_uid_id(pbn_uid_id)
        or _try_get_autor_by_system_kadrowy_id(system_kadrowy_id)
        or _try_get_autor_by_pbn_id(pbn_id)
    )


def _build_autor_name_query(nazwisko: str, imiona: str) -> Q:
    """Buduje podstawowe zapytanie Q dla nazwiska i imion."""
    return Q(
        Q(nazwisko__iexact=nazwisko) | Q(poprzednie_nazwiska__icontains=nazwisko),
        imiona__iexact=imiona,
    )


def _try_match_autor_by_name(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka | None,
    tytul_str: str | None,
) -> Autor | None:
    """Próbuje dopasować autora po imieniu i nazwisku."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    queries = [
        _build_autor_name_query(nazwisko, imiona),
        _build_autor_name_query(nazwisko, imiona.split(" ")[0]),
    ]

    if tytul_str:
        queries.extend([q & Q(tytul__skrot=tytul_str) for q in queries[:]])

    for qry in queries:
        try:
            return Autor.objects.get(qry)
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        if jednostka is not None:
            try:
                return Autor.objects.get(qry & Q(aktualna_jednostka=jednostka))
            except (Autor.MultipleObjectsReturned, Autor.DoesNotExist):
                pass

    return None


def _try_match_autor_in_jednostka(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka,
    tytul_str: str | None,
) -> Autor | None:
    """Szuka autora wśród przypisanych do jednostki."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    base_query = Q(
        Q(autor__nazwisko__iexact=nazwisko)
        | Q(autor__poprzednie_nazwiska__icontains=nazwisko),
        autor__imiona__iexact=imiona,
    )
    queries = [base_query]
    if tytul_str:
        queries.append(base_query & Q(autor__tytul__skrot=tytul_str))

    for qry in queries:
        try:
            return jednostka.autor_jednostka_set.get(qry).autor
        except (Autor_Jednostka.MultipleObjectsReturned, Autor_Jednostka.DoesNotExist):
            pass

    return None


def _try_match_autor_by_polish_english_variants(
    imiona: str,
    nazwisko: str,
    jednostka: Jednostka | None,
) -> Autor | None:
    """Fallback dla wariantów pisowni polsko-angielskiej.

    Stosuje ``unaccent`` na nazwisku po stronie bazy (Marańda↔Maranda)
    oraz regułę ``v↔w`` na pierwszym imieniu (Eva↔Ewa, Viktor↔Wiktor).
    Wymaga ``CREATE EXTENSION unaccent`` (instalowane przez migrację
    0001_fulltext).

    Zwraca autora tylko gdy istnieje **dokładnie jeden** kandydat —
    przy ambiguity decyzja należy do użytkownika.
    """
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()
    if not imiona or not nazwisko:
        return None

    first = imiona.split()[0]
    variants_norm = {v.lower() for v in polish_english_first_name_variants(first)}
    if not variants_norm:
        return None

    nazwisko_norm = remove_polish_diacritics(nazwisko).lower()

    imie_q = Q()
    for v in variants_norm:
        imie_q |= Q(im_n=v) | Q(im_n__startswith=v + " ")

    qs = (
        Autor.objects.annotate(
            naz_n=Lower(Unaccent("nazwisko")),
            im_n=Lower(Unaccent("imiona")),
        )
        .filter(naz_n=nazwisko_norm)
        .filter(imie_q)
    )

    if jednostka is not None:
        qs_j = qs.filter(aktualna_jednostka=jednostka)
        results = list(qs_j[:2])
        if len(results) == 1:
            return results[0]

    results = list(qs[:2])
    if len(results) == 1:
        return results[0]
    return None


def _try_match_autor_with_orcid_or_tytul(imiona: str, nazwisko: str) -> Autor | None:
    """Ostatnia próba - szuka autora z ORCIDem lub tytułem."""
    imiona = (imiona or "").strip()
    nazwisko = (nazwisko or "").strip()

    base_query = _build_autor_name_query(nazwisko, imiona)

    # Próba z ORCIDem i tytułem
    try:
        return Autor.objects.get(
            base_query, orcid__isnull=False, tytul_id__isnull=False
        )
    except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
        pass

    # Próba tylko z tytułem
    try:
        return Autor.objects.get(base_query, tytul_id__isnull=False)
    except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
        pass

    return None


def matchuj_autora(
    imiona: str | None,
    nazwisko: str | None,
    jednostka: Jednostka | None = None,
    bpp_id: int | None = None,
    pbn_uid_id: str | None = None,
    system_kadrowy_id: int | None = None,
    pbn_id: int | None = None,
    orcid: str | None = None,
    tytul_str: Tytul | None = None,
):
    # Najpierw próba po identyfikatorach
    result = _try_match_autor_by_direct_ids(
        bpp_id, orcid, pbn_uid_id, system_kadrowy_id, pbn_id
    )
    if result:
        return result

    # Próba po imieniu i nazwisku
    result = _try_match_autor_by_name(imiona, nazwisko, jednostka, tytul_str)
    if result:
        return result

    # Szukanie w jednostce (niekoniecznie aktualnej)
    if jednostka:
        result = _try_match_autor_in_jednostka(imiona, nazwisko, jednostka, tytul_str)
        if result:
            return result

    # Warianty pisowni PL↔EN (diakrytyki + v↔w na imieniu)
    result = _try_match_autor_by_polish_english_variants(imiona, nazwisko, jednostka)
    if result:
        return result

    # Ostatnia próba - autor z ORCIDem lub tytułem
    return _try_match_autor_with_orcid_or_tytul(imiona, nazwisko)
