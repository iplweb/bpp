from typing import Union

from django.db.models import Q, Value
from django.db.models.functions import Lower, Replace, Trim

from .normalization import (
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

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import TrigramSimilarity

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
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
    Wymiar_Etatu,
    Zrodlo,
)
from bpp.util import fail_if_seq_scan


def matchuj_wydzial(nazwa):
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


def matchuj_jednostke(nazwa, wydzial=None):
    nazwa = normalize_nazwa_jednostki(nazwa)

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


def matchuj_autora(
    imiona: str,
    nazwisko: str,
    jednostka: Union[Jednostka, None] = None,
    bpp_id: Union[int, None] = None,
    pbn_uid_id: Union[str, None] = None,
    system_kadrowy_id: Union[int, None] = None,
    pbn_id: Union[int, None] = None,
    orcid: Union[str, None] = None,
    tytul_str: Union[Tytul, None] = None,
):
    if bpp_id is not None:
        try:
            return Autor.objects.get(pk=bpp_id)
        except Autor.DoesNotExist:
            pass

    if orcid:
        try:
            return Autor.objects.get(orcid__iexact=orcid.strip())
        except Autor.DoesNotExist:
            pass

    if pbn_uid_id is not None and pbn_uid_id.strip() != "":
        # Może być > 1 autor z takim pbn_uid_id
        _qset = Autor.objects.filter(pbn_uid_id=pbn_uid_id)
        if _qset.exists():
            return _qset.first()

    if system_kadrowy_id is not None:
        try:
            int(system_kadrowy_id)
        except (TypeError, ValueError):
            system_kadrowy_id = None

        if system_kadrowy_id is not None:
            try:
                return Autor.objects.get(system_kadrowy_id=system_kadrowy_id)
            except Autor.DoesNotExist:
                pass

    if pbn_id is not None:
        if isinstance(pbn_id, str):
            pbn_id = pbn_id.strip()

        try:
            pbn_id = int(pbn_id)
        except (TypeError, ValueError):
            pbn_id = None

        if pbn_id is not None:
            try:
                return Autor.objects.get(pbn_id=pbn_id)
            except Autor.DoesNotExist:
                pass

    queries = [
        Q(
            Q(nazwisko__iexact=nazwisko.strip())
            | Q(poprzednie_nazwiska__icontains=nazwisko.strip()),
            imiona__iexact=imiona.strip(),
        )
    ]

    if tytul_str:
        queries.append(queries[0] & Q(tytul__skrot=tytul_str))

    for qry in queries:
        try:
            return Autor.objects.get(qry)
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        try:
            return Autor.objects.get(qry & Q(aktualna_jednostka=jednostka))
        except (Autor.MultipleObjectsReturned, Autor.DoesNotExist):
            pass

    # Jesteśmy tutaj. Najwyraźniej poszukiwanie po aktualnej jednostce, imieniu, nazwisku,
    # tytule itp nie bardzo się powiodło. Spróbujmy innej strategii -- jednostka jest
    # określona, poszukajmy w jej autorach. Wszak nie musi być ta jednostka jednostką
    # aktualną...

    if jednostka:

        queries = [
            Q(
                Q(autor__nazwisko__iexact=nazwisko.strip())
                | Q(autor__poprzednie_nazwiska__icontains=nazwisko.strip()),
                autor__imiona__iexact=imiona.strip(),
            )
        ]
        if tytul_str:
            queries.append(queries[0] & Q(autor__tytul__skrot=tytul_str))

        for qry in queries:
            try:
                return jednostka.autor_jednostka_set.get(qry).autor
            except (
                Autor_Jednostka.MultipleObjectsReturned,
                Autor_Jednostka.DoesNotExist,
            ):
                pass

    return None


def matchuj_zrodlo(
    s: Union[str, None],
    issn: Union[str, None] = None,
    e_issn: Union[str, None] = None,
    alt_nazwa=None,
) -> Union[None, Zrodlo]:
    if s is None or str(s) == "":
        return

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

    for elem in s, alt_nazwa:
        if elem is None:
            continue

        elem = normalize_tytul_zrodla(elem)
        try:
            return Zrodlo.objects.get(Q(nazwa__iexact=elem) | Q(skrot__iexact=elem))
        except Zrodlo.MultipleObjectsReturned:
            pass
        except Zrodlo.DoesNotExist:
            if elem.endswith("."):
                try:
                    return Zrodlo.objects.get(
                        Q(nazwa__istartswith=elem[:-1])
                        | Q(skrot__istartswith=elem[:-1])
                    )
                except Zrodlo.DoesNotExist:
                    pass
                except Zrodlo.MultipleObjectsReturned:
                    pass


def matchuj_dyscypline(kod, nazwa):
    nazwa = normalize_nazwa_dyscypliny(nazwa)
    try:
        return Dyscyplina_Naukowa.objects.get(nazwa=nazwa)
    except Dyscyplina_Naukowa.DoesNotExist:
        pass
    except Dyscyplina_Naukowa.MultipleObjectsReturned:
        pass

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


# Znormalizowany skrot zrodla do wyszukiwania -- wyrzucone wszystko procz kropek
normalized_db_zrodlo_nazwa = Trim(
    Replace(Lower("nazwa"), Value(" "), Value("")),
)


def normalize_zrodlo_nazwa_for_db_lookup(s):
    return s.lower().replace(" ", "").strip()


normalized_db_isbn = Trim(Replace(Lower("isbn"), Value("-"), Value("")))


def matchuj_publikacje(
    klass: [Wydawnictwo_Zwarte, Wydawnictwo_Ciagle, Rekord],
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

    if doi is not None:
        doi = normalize_doi(doi)
        if doi:
            zapytanie = klass.objects.filter(doi__istartswith=doi, rok=year)

            if doi_matchuj_tylko_nadrzedne:
                if hasattr(klass, "wydawnictwo_nadrzedne_id"):
                    zapytanie = zapytanie.filter(wydawnictwo_nadrzedne_id=None)

            res = zapytanie.annotate(
                podobienstwo=TrigramSimilarity(normalized_db_title, title.lower())
            ).order_by("-podobienstwo")[:2]
            fail_if_seq_scan(res, DEBUG_MATCHOWANIE)
            if res.exists():
                if res.first().podobienstwo >= MATCH_SIMILARITY_THRESHOLD_VERY_LOW:
                    return res.first()

    title = normalize_tytul_publikacji(title)

    title_has_spaces = False

    if title is not None:
        title_has_spaces = title.find(" ") > 0

    if title is not None and (
        (not title_has_spaces and len(title) >= TITLE_LIMIT_SINGLE_WORD)
        or (title_has_spaces and len(title) >= TITLE_LIMIT_MANY_WORDS)
    ):
        if zrodlo is not None and hasattr(klass, "zrodlo"):
            try:
                return klass.objects.get(
                    tytul_oryginalny__istartswith=title, rok=year, zrodlo=zrodlo
                )
            except klass.DoesNotExist:
                pass
            except klass.MultipleObjectsReturned:
                print(
                    f"PPP ZZZ MultipleObjectsReturned dla title={title} rok={year} zrodlo={zrodlo}"
                )

    if (
        isbn is not None
        and isbn != ""
        and hasattr(klass, "isbn")
        and hasattr(klass, "e_isbn")
    ):
        ni = normalize_isbn(isbn)

        zapytanie = klass.objects.exclude(isbn=None, e_isbn=None).exclude(
            isbn="", e_isbn=""
        )

        if isbn_matchuj_tylko_nadrzedne:
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

        #
        # Uwaga uwaga uwaga.
        #
        # Gdy matchujemy ISBN, to w BPP dochodzi do takiej nieciekawej sytuacji: wpisywany jest
        # ISBN zarówno dla rozdziałów jak i dla wydawnictw nadrzędnych.
        #
        # Zatem, na ten moment, aby usprawnić matchowanie ISBN, jeżeli ustawiona jest flaga
        # isbn_matchuj_tylko_nadrzedne, to system bedzie szukał tylko i wyłącznie wśród
        # rekordów będących wydawnictwami nadrzędnymi (czyli nie mającymi rekordów podrzędnych)
        #

        res = (
            zapytanie.filter(Q(isbn=ni) | Q(e_isbn=ni))
            .annotate(
                podobienstwo=TrigramSimilarity(
                    normalized_db_title,
                    title.lower(),
                )
            )
            .order_by("-podobienstwo")[:2]
        )
        fail_if_seq_scan(res, DEBUG_MATCHOWANIE)
        if res.exists():
            if res.first().podobienstwo >= MATCH_SIMILARITY_THRESHOLD_VERY_LOW:
                return res.first()

    public_uri = normalize_public_uri(public_uri)
    if public_uri:
        res = (
            klass.objects.filter(Q(www=public_uri) | Q(public_www=public_uri))
            .annotate(
                podobienstwo=TrigramSimilarity(normalized_db_title, title.lower())
            )
            .order_by("-podobienstwo")[:2]
        )
        fail_if_seq_scan(res, DEBUG_MATCHOWANIE)
        if res.exists():

            if res.first().podobienstwo >= MATCH_SIMILARITY_THRESHOLD:
                return res.first()

    if title is not None and (
        (not title_has_spaces and len(title) >= TITLE_LIMIT_SINGLE_WORD)
        or (title_has_spaces and len(title) >= TITLE_LIMIT_MANY_WORDS)
    ):
        res = (
            klass.objects.filter(tytul_oryginalny__istartswith=title, rok=year)
            .annotate(
                podobienstwo=TrigramSimilarity(normalized_db_title, title.lower())
            )
            .order_by("-podobienstwo")[:2]
        )

        fail_if_seq_scan(res, DEBUG_MATCHOWANIE)
        if res.exists():
            if res.first().podobienstwo >= MATCH_SIMILARITY_THRESHOLD:
                return res.first()

        # Ostatnia szansa, po podobieństwie, niski próg

        res = (
            klass.objects.filter(rok=year)
            .annotate(
                podobienstwo=TrigramSimilarity(normalized_db_title, title.lower())
            )
            .order_by("-podobienstwo")[:2]
        )

        fail_if_seq_scan(res, DEBUG_MATCHOWANIE)
        if res.exists():
            if res.first().podobienstwo >= MATCH_SIMILARITY_THRESHOLD_LOW:
                return res.first()
