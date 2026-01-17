import dateutil
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q, Value
from django.db.models.functions import Lower, Replace, Trim

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Rekord,
    Tytul,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydzial,
    Wymiar_Etatu,
    Zrodlo,
)
from bpp.util import fail_if_seq_scan

from .normalization import (
    extract_part_number,
    normalize_doi,
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_isbn,
    normalize_kod_dyscypliny,
    normalize_nazwa_dyscypliny,
    normalize_nazwa_jednostki,
    normalize_nazwa_wydawcy,
    normalize_public_uri,
    normalize_tytul_naukowy,
    normalize_tytul_publikacji,
    normalize_tytul_zrodla,
    normalize_wymiar_etatu,
)


def matchuj_wydzial(nazwa: str | None):
    if nazwa is None:
        return

    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


def matchuj_tytul(tytul: str, create_if_not_exist=False) -> Tytul:
    """
    Dostaje tytuł: pełną nazwę albo skrót
    """

    try:
        return Tytul.objects.get(nazwa__iexact=tytul)
    except (Tytul.DoesNotExist, Tytul.MultipleObjectsReturned):
        return Tytul.objects.get(skrot=normalize_tytul_naukowy(tytul))


def matchuj_funkcja_autora(funkcja_autora: str) -> Funkcja_Autora:
    funkcja_autora = normalize_funkcja_autora(funkcja_autora)
    return Funkcja_Autora.objects.get(
        Q(nazwa__iexact=funkcja_autora) | Q(skrot__iexact=funkcja_autora)
    )


def matchuj_grupa_pracownicza(grupa_pracownicza: str) -> Grupa_Pracownicza:
    grupa_pracownicza = normalize_grupa_pracownicza(grupa_pracownicza)
    return Grupa_Pracownicza.objects.get(nazwa__iexact=grupa_pracownicza)


def matchuj_wymiar_etatu(wymiar_etatu: str) -> Wymiar_Etatu:
    wymiar_etatu = normalize_wymiar_etatu(wymiar_etatu)
    return Wymiar_Etatu.objects.get(nazwa__iexact=wymiar_etatu)


def wytnij_skrot(jednostka):
    if jednostka.find("(") >= 0 and jednostka.find(")") >= 0:
        jednostka, skrot = jednostka.split("(", 2)
        jednostka = jednostka.strip()
        skrot = skrot[:-1].strip()
        return jednostka, skrot

    return jednostka, None


def matchuj_jednostke(nazwa, wydzial=None):
    if nazwa is None:
        return

    nazwa = normalize_nazwa_jednostki(nazwa)
    skrot = nazwa

    if "(" in nazwa and ")" in nazwa:
        nazwa_bez_nawiasow, skrot = wytnij_skrot(nazwa)
        try:
            return Jednostka.objects.get(skrot=skrot)
        except Jednostka.DoesNotExist:
            pass

    try:
        return Jednostka.objects.get(Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa))
    except Jednostka.DoesNotExist:
        if nazwa.endswith("."):
            nazwa = nazwa[:-1].strip()

        try:
            return Jednostka.objects.get(
                Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa)
            )
        except Jednostka.MultipleObjectsReturned as e:
            if wydzial is None:
                raise e

        return Jednostka.objects.get(
            Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa),
            Q(wydzial__nazwa__iexact=wydzial),
        )

    except Jednostka.MultipleObjectsReturned as e:
        if wydzial is None:
            raise e

        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa),
            Q(wydzial__nazwa__iexact=wydzial),
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

    # Ostatnia próba - autor z ORCIDem lub tytułem
    return _try_match_autor_with_orcid_or_tytul(imiona, nazwisko)


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


def matchuj_dyscypline(kod, nazwa):
    if nazwa:
        for nazwa_kandydat in [nazwa, nazwa.split("(", 2)[0]]:
            nazwa_znormalizowana = normalize_nazwa_dyscypliny(nazwa_kandydat)
            try:
                return Dyscyplina_Naukowa.objects.get(nazwa=nazwa_znormalizowana)
            except Dyscyplina_Naukowa.DoesNotExist:
                pass
            except Dyscyplina_Naukowa.MultipleObjectsReturned:
                pass

    if kod:
        kod = normalize_kod_dyscypliny(kod)
        try:
            return Dyscyplina_Naukowa.objects.get(kod=kod)
        except Dyscyplina_Naukowa.DoesNotExist:
            pass
        except Dyscyplina_Naukowa.MultipleObjectsReturned:
            pass


def matchuj_wydawce(nazwa, pbn_uid_id=None, similarity=0.9):
    nazwa = normalize_nazwa_wydawcy(nazwa)
    try:
        return Wydawca.objects.get(nazwa=nazwa, alias_dla_id=None)
    except Wydawca.DoesNotExist:
        pass

    if pbn_uid_id is not None:
        try:
            return Wydawca.objects.get(pbn_uid_id=pbn_uid_id)
        except Wydawca.DoesNotExist:
            pass

    loose = (
        Wydawca.objects.annotate(similarity=TrigramSimilarity("nazwa", nazwa))
        .filter(similarity__gte=similarity)
        .order_by("-similarity")[:5]
    )
    if loose.count() > 0 and loose.count() < 2:
        return loose.first()


TITLE_LIMIT_SINGLE_WORD = 15
TITLE_LIMIT_MANY_WORDS = 25

MATCH_SIMILARITY_THRESHOLD = 0.95
MATCH_SIMILARITY_THRESHOLD_LOW = 0.90
MATCH_SIMILARITY_THRESHOLD_VERY_LOW = 0.80

# Znormalizowany tytuł w bazie danych -- wyrzucony ciąg znaków [online], podwójne
# spacje pozamieniane na pojedyncze, trim całości
normalized_db_title = Trim(
    Replace(
        Replace(Lower("tytul_oryginalny"), Value(" [online]"), Value("")),
        Value("  "),
        Value(" "),
    )
)

# Znormalizowany skrót nazwy źródła -- wyrzucone spacje i kropki, trim, zmniejszone
# znaki
normalized_db_zrodlo_skrot = Trim(
    Replace(
        Replace(
            Replace(Lower("skrot"), Value(" "), Value("")),
            Value("-"),
            Value(""),
        ),
        Value("."),
        Value(""),
    )
)


def normalize_zrodlo_skrot_for_db_lookup(s):
    return s.lower().replace(" ", "").strip().replace("-", "").replace(".", "")


def normalize_date(s):
    if s is None:
        return s

    if isinstance(s, str):
        s = s.strip()

        if not s:
            return

        return dateutil.parser.parse(s)

    return s


# Znormalizowany skrot zrodla do wyszukiwania -- wyrzucone wszystko procz kropek
normalized_db_zrodlo_nazwa = Trim(
    Replace(Lower("nazwa"), Value(" "), Value("")),
)


def normalize_zrodlo_nazwa_for_db_lookup(s):
    return s.lower().replace(" ", "").strip()


normalized_db_isbn = Trim(Replace(Lower("isbn"), Value("-"), Value("")))


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


def _try_match_pub_by_title(klass, title, year, debug):
    """Próbuje dopasować publikację po podobieństwie tytułu."""
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
        result = _try_match_pub_by_title(klass, title, year, DEBUG_MATCHOWANIE)
        if result:
            return result

    return None


def normalize_kod_dyscypliny_pbn(kod):
    if kod is None:
        raise ValueError("kod = None")

    if kod.find(".") == -1:
        # Nie ma kropki, wiec juz znormalizowany
        return kod

    k1, k2 = (int(x) for x in kod.split(".", 2))
    return f"{k1}{k2:02}"


def matchuj_aktualna_dyscypline_pbn(kod, nazwa):
    kod = normalize_kod_dyscypliny_pbn(kod)

    from django.utils import timezone

    from pbn_api.models import Discipline

    d = timezone.now().date()
    parent_group_args = (
        Q(parent_group__validityDateFrom__lte=d),
        Q(parent_group__validityDateTo=None) | Q(parent_group__validityDateTo__gt=d),
    )

    try:
        return Discipline.objects.get(*parent_group_args, code=kod)
    except Discipline.DoesNotExist:
        pass

    try:
        return Discipline.objects.get(*parent_group_args, name=nazwa)
    except Discipline.DoesNotExist:
        pass


def matchuj_nieaktualna_dyscypline_pbn(kod, nazwa, rok_min=2018, rok_max=2022):
    kod = normalize_kod_dyscypliny_pbn(kod)

    from pbn_api.models import Discipline

    nieaktualna_parent_group_args = (
        Q(parent_group__validityDateFrom__year=rok_min),
        Q(parent_group__validityDateTo__year=rok_max),
    )
    try:
        return Discipline.objects.get(*nieaktualna_parent_group_args, code=kod)
    except Discipline.DoesNotExist:
        pass

    try:
        return Discipline.objects.get(*nieaktualna_parent_group_args, name=nazwa)
    except Discipline.DoesNotExist:
        pass


def matchuj_uczelnie(nazwa):
    from pbn_api.models import Institution

    try:
        return Institution.objects.get(name=nazwa)
    except Institution.DoesNotExist:
        pass

    res = (
        Institution.objects.annotate(similarity=TrigramSimilarity("name", nazwa))
        .filter(similarity__gte=0.8)
        .order_by("-similarity")
    )

    if res.count() == 1:
        return res.first()
