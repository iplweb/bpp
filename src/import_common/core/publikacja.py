"""Matchowanie rekordów publikacji (Wydawnictwo_Zwarte / Wydawnictwo_Ciagle /
Rekord) po DOI, ISBN, public_uri, źródle i podobieństwie tytułu.

Sercem matchowania po tytule jest TrigramSimilarity nakładane na
zNORMALIZOWANY w bazie tytuł (`normalized_db_title`); kandydaci muszą
przekroczyć kombinację progu podobieństwa i kompatybilność numeru części.
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from bpp.models import Rekord, Wydawnictwo_Zwarte
from bpp.util import fail_if_seq_scan

from ..normalization import (
    extract_part_number,
    normalize_doi,
    normalize_isbn,
    normalize_public_uri,
    normalize_tytul_publikacji,
)
from .normalize_db import normalized_db_title

TITLE_LIMIT_SINGLE_WORD = 15
TITLE_LIMIT_MANY_WORDS = 25

MATCH_SIMILARITY_THRESHOLD = 0.95
MATCH_SIMILARITY_THRESHOLD_LOW = 0.90
MATCH_SIMILARITY_THRESHOLD_VERY_LOW = 0.80


def _part_numbers_compatible(title1: str | None, title2: str | None) -> bool:
    """Sprawdza czy numery części w tytułach są kompatybilne.

    Zwraca True jeśli:
    - Oba tytuły nie mają numeru części, LUB
    - Oba mają ten sam numer części
    - Którykolwiek z tytułów jest None (nie możemy sprawdzić)

    Zwraca False jeśli numery części się różnią.

    Ta funkcja zapobiega błędnemu matchowaniu publikacji takich jak
    "Tytuł cz. II" do "Tytuł cz. III" - to są różne publikacje.
    """
    if title1 is None or title2 is None:
        return True  # Nie możemy sprawdzić, zakładamy kompatybilność

    _, part1 = extract_part_number(title1)
    _, part2 = extract_part_number(title2)

    # Jeśli oba nie mają numeru części - OK
    if part1 is None and part2 is None:
        return True

    # Jeśli jeden ma, drugi nie - NIE matchuj
    if part1 is None or part2 is None:
        return False

    # Oba mają - muszą być identyczne
    return part1 == part2


def _is_title_long_enough(title: str | None) -> bool:
    """Sprawdza czy tytuł jest wystarczająco długi do matchowania."""
    if title is None:
        return False
    title_has_spaces = " " in title
    if title_has_spaces:
        return len(title) >= TITLE_LIMIT_MANY_WORDS
    return len(title) >= TITLE_LIMIT_SINGLE_WORD


def _check_candidate(candidate, title: str, threshold: float) -> bool:
    """Sprawdza czy kandydat spełnia próg podobieństwa i ma zgodny numer części."""
    if candidate.podobienstwo >= threshold:
        if _part_numbers_compatible(title, candidate.tytul_oryginalny):
            return True
    return False


def _try_match_pub_by_doi(klass, title, year, doi, doi_matchuj_tylko_nadrzedne, debug):
    """Próbuje dopasować publikację po DOI."""
    doi = normalize_doi(doi)
    if not doi:
        return None

    zapytanie = klass.objects.filter(doi__istartswith=doi, rok=year)
    if doi_matchuj_tylko_nadrzedne and hasattr(klass, "wydawnictwo_nadrzedne_id"):
        zapytanie = zapytanie.filter(wydawnictwo_nadrzedne_id=None)

    res = zapytanie.annotate(
        podobienstwo=TrigramSimilarity(normalized_db_title, title.lower())
    ).order_by("-podobienstwo")[:2]
    fail_if_seq_scan(res, debug)

    if res.exists():
        candidate = res.first()
        if _check_candidate(candidate, title, MATCH_SIMILARITY_THRESHOLD_VERY_LOW):
            return candidate
    return None


def _try_match_pub_by_zrodlo(klass, title, year, zrodlo):
    """Próbuje dopasować publikację po źródle."""
    if zrodlo is None or not hasattr(klass, "zrodlo"):
        return None
    try:
        return klass.objects.get(
            tytul_oryginalny__istartswith=title, rok=year, zrodlo=zrodlo
        )
    except klass.DoesNotExist:
        return None
    except klass.MultipleObjectsReturned:
        print(
            f"PPP ZZZ MultipleObjectsReturned title={title} rok={year} zrodlo={zrodlo}"
        )
        return None


def _build_isbn_query(klass, isbn_matchuj_tylko_nadrzedne):
    """Buduje zapytanie dla matchowania ISBN."""
    from django.contrib.contenttypes.models import ContentType

    zapytanie = klass.objects.exclude(isbn=None, e_isbn=None).exclude(
        isbn="", e_isbn=""
    )

    if not isbn_matchuj_tylko_nadrzedne:
        return zapytanie

    zapytanie = zapytanie.filter(wydawnictwo_nadrzedne_id=None)

    if klass == Rekord:
        zapytanie = zapytanie.filter(
            pk__in=[
                (ContentType.objects.get_for_model(Wydawnictwo_Zwarte).pk, x)
                for x in Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych()
            ]
        )
    elif klass == Wydawnictwo_Zwarte:
        zapytanie = zapytanie.filter(
            pk__in=Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych()
        )
    else:
        raise NotImplementedError(
            "Matchowanie po ISBN dla czegoś innego niż wydawnictwo zwarte nie opracowane"
        )

    return zapytanie


def _try_match_pub_by_isbn(klass, title, isbn, isbn_matchuj_tylko_nadrzedne, debug):
    """Próbuje dopasować publikację po ISBN."""
    if not isbn or not hasattr(klass, "isbn") or not hasattr(klass, "e_isbn"):
        return None

    ni = normalize_isbn(isbn)
    zapytanie = _build_isbn_query(klass, isbn_matchuj_tylko_nadrzedne)

    res = (
        zapytanie.filter(Q(isbn=ni) | Q(e_isbn=ni))
        .annotate(podobienstwo=TrigramSimilarity(normalized_db_title, title.lower()))
        .order_by("-podobienstwo")[:2]
    )
    fail_if_seq_scan(res, debug)

    if res.exists():
        candidate = res.first()
        if _check_candidate(candidate, title, MATCH_SIMILARITY_THRESHOLD_VERY_LOW):
            return candidate
    return None


def _try_match_pub_by_uri(klass, title, public_uri, debug):
    """Próbuje dopasować publikację po public_uri."""
    public_uri = normalize_public_uri(public_uri)
    if not public_uri:
        return None

    res = (
        klass.objects.filter(Q(www=public_uri) | Q(public_www=public_uri))
        .annotate(podobienstwo=TrigramSimilarity(normalized_db_title, title.lower()))
        .order_by("-podobienstwo")[:2]
    )
    fail_if_seq_scan(res, debug)

    if res.exists():
        candidate = res.first()
        if _check_candidate(candidate, title, MATCH_SIMILARITY_THRESHOLD):
            return candidate
    return None


def _isbn_matches(candidate, isbn):
    """Sprawdza czy ISBN kandydata pasuje do szukanego ISBN.

    Zwraca True jeśli:
    - Nie mamy ISBN do porównania (isbn=None)
    - Kandydat nie ma ISBN (akceptujemy)
    - ISBN są takie same
    """
    if isbn is None:
        return True

    # Normalizuj ISBN wejściowy
    ni = normalize_isbn(isbn)
    if not ni:
        return True

    # Jeśli kandydat nie ma ISBN, akceptujemy (może to być ten sam rekord)
    candidate_isbn = getattr(candidate, "isbn", None)
    candidate_e_isbn = getattr(candidate, "e_isbn", None)

    if not candidate_isbn and not candidate_e_isbn:
        return True

    # Sprawdź czy któryś ISBN pasuje
    normalized_candidate_isbns = []
    if candidate_isbn:
        normalized_candidate_isbns.append(normalize_isbn(candidate_isbn))
    if candidate_e_isbn:
        normalized_candidate_isbns.append(normalize_isbn(candidate_e_isbn))
    return ni in normalized_candidate_isbns


def _try_match_pub_by_title(klass, title, year, debug, isbn=None):
    """Próbuje dopasować publikację po podobieństwie tytułu.

    Jeśli podano isbn, sprawdza dodatkowo czy kandydat ma zgodny ISBN.
    Dzięki temu unika błędnego dopasowania rozdziałów z różnych książek
    o tym samym tytule i roku.
    """
    # Najpierw próba z istartswith
    res = (
        klass.objects.filter(tytul_oryginalny__istartswith=title, rok=year)
        .annotate(podobienstwo=TrigramSimilarity(normalized_db_title, title.lower()))
        .order_by("-podobienstwo")[:2]
    )
    fail_if_seq_scan(res, debug)

    if res.exists():
        candidate = res.first()
        if _check_candidate(candidate, title, MATCH_SIMILARITY_THRESHOLD):
            if _isbn_matches(candidate, isbn):
                return candidate

    # Ostatnia szansa - tylko po roku z niskim progiem
    res = (
        klass.objects.filter(rok=year)
        .annotate(podobienstwo=TrigramSimilarity(normalized_db_title, title.lower()))
        .order_by("-podobienstwo")[:2]
    )
    fail_if_seq_scan(res, debug)

    if res.exists():
        candidate = res.first()
        if _check_candidate(candidate, title, MATCH_SIMILARITY_THRESHOLD_LOW):
            if _isbn_matches(candidate, isbn):
                return candidate

    return None


def matchuj_publikacje(
    klass,
    title,
    year,
    doi=None,
    public_uri=None,
    isbn=None,
    zrodlo=None,
    DEBUG_MATCHOWANIE=False,
    isbn_matchuj_tylko_nadrzedne=True,
    doi_matchuj_tylko_nadrzedne=True,
):
    # Próba po DOI (przed normalizacją tytułu)
    if doi is not None:
        result = _try_match_pub_by_doi(
            klass, title, year, doi, doi_matchuj_tylko_nadrzedne, DEBUG_MATCHOWANIE
        )
        if result:
            return result

    title = normalize_tytul_publikacji(title)

    # Próba po źródle
    if _is_title_long_enough(title):
        result = _try_match_pub_by_zrodlo(klass, title, year, zrodlo)
        if result:
            return result

    # Próba po ISBN
    result = _try_match_pub_by_isbn(
        klass, title, isbn, isbn_matchuj_tylko_nadrzedne, DEBUG_MATCHOWANIE
    )
    if result:
        return result

    # Próba po URI
    result = _try_match_pub_by_uri(klass, title, public_uri, DEBUG_MATCHOWANIE)
    if result:
        return result

    # Próba po podobieństwie tytułu
    if _is_title_long_enough(title):
        result = _try_match_pub_by_title(
            klass, title, year, DEBUG_MATCHOWANIE, isbn=isbn
        )
        if result:
            return result

    return None
