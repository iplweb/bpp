"""Matchowanie źródeł (czasopism) po ISSN/e-ISSN, mniswId i tytule."""

from django.db.models import Q

from bpp.models import Zrodlo

from ..normalization import normalize_tytul_zrodla


def _try_match_zrodlo_by_issn(issn: str | None, e_issn: str | None) -> Zrodlo | None:
    """Próbuje dopasować źródło po ISSN lub e-ISSN."""
    if issn is not None:
        try:
            return Zrodlo.objects.get(issn=issn)
        except (Zrodlo.DoesNotExist, Zrodlo.MultipleObjectsReturned):
            pass

    if e_issn is not None:
        try:
            return Zrodlo.objects.get(e_issn=e_issn)
        except (Zrodlo.DoesNotExist, Zrodlo.MultipleObjectsReturned):
            pass

    return None


def _try_match_zrodlo_by_mnisw_id(mnisw_id: int | str | None) -> Zrodlo | None:
    """Próbuje dopasować źródło po mniswId przez PBN Journal."""
    if mnisw_id is None:
        return None

    from pbn_api.models import Journal

    try:
        mnisw_id = int(mnisw_id) if isinstance(mnisw_id, str) else mnisw_id
    except (ValueError, TypeError):
        return None

    try:
        pbn_journal = Journal.objects.get(mniswId=mnisw_id)
        zrodlo = Zrodlo.objects.filter(pbn_uid=pbn_journal).first()
        if zrodlo:
            return zrodlo
    except Journal.DoesNotExist:
        pass
    except Journal.MultipleObjectsReturned:
        for pbn_journal in Journal.objects.filter(mniswId=mnisw_id):
            zrodlo = Zrodlo.objects.filter(pbn_uid=pbn_journal).first()
            if zrodlo:
                return zrodlo

    return None


def _try_match_zrodlo_by_title_single(
    elem: str, disable_skrot: bool, disable_fuzzy: bool
) -> Zrodlo | None:
    """Próbuje dopasować pojedynczy tytuł źródła."""
    elem = normalize_tytul_zrodla(elem)
    try:
        if disable_skrot:
            return Zrodlo.objects.get(nazwa__iexact=elem)
        return Zrodlo.objects.get(Q(nazwa__iexact=elem) | Q(skrot__iexact=elem))
    except Zrodlo.MultipleObjectsReturned:
        pass
    except Zrodlo.DoesNotExist:
        if not disable_fuzzy and elem.endswith("."):
            try:
                return Zrodlo.objects.get(
                    Q(nazwa__istartswith=elem[:-1]) | Q(skrot__istartswith=elem[:-1])
                )
            except (Zrodlo.DoesNotExist, Zrodlo.MultipleObjectsReturned):
                pass

    return None


def matchuj_zrodlo(
    s: str | None,
    issn: str | None = None,
    e_issn: str | None = None,
    mnisw_id: int | str | None = None,
    alt_nazwa=None,
    disable_fuzzy=False,
    disable_skrot=False,
    disable_title_matching=False,
) -> None | Zrodlo:
    if s is None or str(s) == "":
        return None

    result = _try_match_zrodlo_by_issn(issn, e_issn)
    if result:
        return result

    result = _try_match_zrodlo_by_mnisw_id(mnisw_id)
    if result:
        return result

    if not disable_title_matching:
        for elem in (s, alt_nazwa):
            if elem is None:
                continue
            result = _try_match_zrodlo_by_title_single(
                elem, disable_skrot, disable_fuzzy
            )
            if result:
                return result

    return None
