"""Łączenie źródeł danych w imporcie publikacji (FD#512).

Import zaczyna się od jednego źródła (dostawcy), ale żadne nie ma kompletu
danych: CrossRef nie zna identyfikatorów PBN ani oświadczeń, PBN często nie
ma streszczenia, licencji czy numerów ORCID. Dlatego zaraz po pobraniu
danych importer sam sprawdza pozostałe źródła:

* import zaczęty POZA PBN (CrossRef, DSpace, strona WWW, BibTeX) — szuka
  pracy w PBN po DOI, a dla książek także po ISBN,
* import zaczęty POZA CrossRef (PBN, DSpace, strona WWW, BibTeX) — pobiera
  dane z CrossRef po DOI.

Z drugiego źródła bierzemy WYŁĄCZNIE to, czego brakuje w pierwszym — dane
źródła wybranego przez redaktora nigdy nie są nadpisywane. Co skąd przyszło,
zapisujemy w ``normalized_data[KLUCZ_ZRODEL]`` i pokazujemy w kreatorze.

Gdy praca jest w PBN, dochodzi trzecie źródło: profil instytucji w PBN,
z którego pochodzą dyscypliny z oświadczeń autorów.

Błąd drugiego źródła nigdy nie przerywa importu — wpis dostaje stan
„nie sprawdzono” z powodem, a import idzie dalej na danych pierwszego.
"""

import itertools
import logging

import requests

from bpp import const
from bpp.util.isbn import warianty_isbn
from bpp.zglaszanie_bledow import capture_exception
from import_common.normalization import (
    normalize_doi,
    normalize_nazwisko_do_porownania,
)

from .models import ImportedAuthor, ImportSession
from .providers import TYPY_Z_WLASNYMI_REDAKTORAMI

logger = logging.getLogger(__name__)

#: Klucz w ``ImportSession.normalized_data`` z listą sprawdzonych źródeł.
KLUCZ_ZRODEL = "zrodla_dodatkowe"

ZRODLO_PBN = "PBN"
ZRODLO_CROSSREF = "CrossRef"
ZRODLO_PROFIL = "profil instytucji w PBN"

STAN_ZNALEZIONO = "znaleziono"
STAN_BRAK = "brak"
STAN_NIEJEDNOZNACZNE = "niejednoznaczne"
STAN_NIE_SPRAWDZONO = "nie_sprawdzono"

#: Pola ``FetchedPublication`` uzupełniane z drugiego źródła → nazwa
#: pokazywana redaktorowi. Tytułu nie ma tu celowo: to po nim (i po DOI)
#: redaktor rozpoznaje pracę, więc zawsze pochodzi ze źródła, które wybrał.
POLA_DO_UZUPELNIENIA = (
    ("doi", "DOI"),
    ("year", "rok"),
    ("publication_type", "typ publikacji"),
    ("source_title", "tytuł źródła"),
    ("source_abbreviation", "skrót źródła"),
    ("issn", "ISSN"),
    ("e_issn", "e-ISSN"),
    ("isbn", "ISBN"),
    ("e_isbn", "e-ISBN"),
    ("publisher", "wydawca"),
    ("language", "język"),
    ("abstract", "streszczenie"),
    ("volume", "tom"),
    ("issue", "numer"),
    ("pages", "strony"),
    ("url", "adres WWW"),
    ("license_url", "licencja"),
    ("keywords", "słowa kluczowe"),
)

#: To samo dla kluczy słownika ``FetchedPublication.extra``.
POLA_EXTRA_DO_UZUPELNIENIA = (
    ("article_number", "numer artykułu"),
    ("original_title", "tytuł oryginalny"),
)

#: Ile wyników jednego zapytania o ISBN czytamy — do rozstrzygnięcia „jedna
#: praca czy kilka” wystarczy garść, a wynik PBN potrafi mieć wiele stron.
_MAKS_WYNIKOW_ISBN = 5


def _wpis(zrodlo, stan, **reszta):
    return {"zrodlo": zrodlo, "stan": stan, **reszta}


def _puste(wartosc) -> bool:
    return wartosc is None or wartosc == "" or wartosc == []


def _jezyk_rozpoznawalny(kod) -> bool:
    """Czy kod języka z drugiego źródła trafi w słownik języków BPP.

    Nierozpoznawalnego kodu nie przenosimy: zablokowałby wykrywanie języka
    z tytułu, które bez niego by zadziałało.
    """
    from .views.publikacja import _resolve_jezyk

    return _resolve_jezyk(kod) is not None


def uzupelnij_brakujace_pola(glowne, dodatkowe) -> list[str]:
    """Przenieś z ``dodatkowe`` pola, których ``glowne`` nie ma.

    Zwraca nazwy uzupełnionych pól (do pokazania redaktorowi). Niczego nie
    nadpisuje.
    """
    uzupelnione = []
    for pole, etykieta in POLA_DO_UZUPELNIENIA:
        if not _puste(getattr(glowne, pole, None)):
            continue
        wartosc = getattr(dodatkowe, pole, None)
        if _puste(wartosc):
            continue
        if pole == "language" and not _jezyk_rozpoznawalny(wartosc):
            continue
        setattr(glowne, pole, wartosc)
        uzupelnione.append(etykieta)

    for klucz, etykieta in POLA_EXTRA_DO_UZUPELNIENIA:
        wartosc = dodatkowe.extra.get(klucz)
        if _puste(glowne.extra.get(klucz)) and not _puste(wartosc):
            glowne.extra[klucz] = wartosc
            uzupelnione.append(etykieta)
    return uzupelnione


def _klucz_osoby(osoba, cale_imie=True):
    nazwisko = normalize_nazwisko_do_porownania(osoba.get("family") or "")
    imie = normalize_nazwisko_do_porownania(osoba.get("given") or "")
    return nazwisko, (imie if cale_imie else imie[:1])


def _indeks(osoby, klucz):
    wynik = {}
    for osoba in osoby:
        k = klucz(osoba)
        if k and k[0]:
            wynik.setdefault(k, []).append(osoba)
    return wynik


def _jedyna_osoba(kandydaci):
    """Zwróć kandydata, jeśli wszyscy na liście to jedna i ta sama osoba.

    Ta sama osoba bywa na liście dwa razy — jako redaktor i jako autor
    (FD#619); wtedy oba wpisy mają te same identyfikatory i imię.
    """
    if not kandydaci:
        return None
    rozne = {
        (o.get("pbn_uid") or "", o.get("orcid") or "", _klucz_osoby(o))
        for o in kandydaci
    }
    return kandydaci[0] if len(rozne) == 1 else None


def _ta_sama_osoba(osoba, po_orcid, po_imieniu, po_inicjale, ilu_z_inicjalem):
    """Znajdź w drugim źródle osobę odpowiadającą ``osoba`` albo ``None``.

    Kolejność: ORCID, nazwisko z pełnym imieniem, nazwisko z inicjałem.
    Po nazwisku łączymy tylko jednoznacznie — przy dwóch „Kowalskich J.”
    po którejkolwiek stronie wolimy nie uzupełnić nic, niż przypisać
    identyfikator PBN nie tej osobie.
    """
    orcid = (osoba.get("orcid") or "").strip().upper()
    if orcid and orcid in po_orcid:
        return po_orcid[orcid]

    kandydaci = po_imieniu.get(_klucz_osoby(osoba), [])
    if kandydaci:
        return _jedyna_osoba(kandydaci)

    inicjal = _klucz_osoby(osoba, cale_imie=False)
    if ilu_z_inicjalem.get(inicjal) != 1:
        return None
    return _jedyna_osoba(po_inicjale.get(inicjal, []))


def uzupelnij_autorow(glowne, dodatkowe) -> dict:
    """Uzupełnij autorom identyfikatory osób w PBN i numery ORCID.

    Lista osób zostaje taka, jak w źródle głównym (kolejność, role, zapis
    nazwisk) — drugie źródło dokłada tylko identyfikatory. Wyjątek: gdy
    źródło główne nie podało ŻADNEJ osoby, bierzemy całą listę z drugiego.

    Zwraca ``{"pbn_uid": n, "orcid": n, "dodani": n}``.
    """
    wynik = {"pbn_uid": 0, "orcid": 0, "dodani": 0}
    obcy = [dict(o) for o in (dodatkowe.authors or [])]
    if not obcy:
        return wynik

    if not glowne.authors:
        glowne.authors = obcy
        wynik["dodani"] = len(obcy)
        return wynik

    po_orcid = {
        (o.get("orcid") or "").strip().upper(): o for o in obcy if o.get("orcid")
    }
    po_imieniu = _indeks(obcy, _klucz_osoby)
    po_inicjale = _indeks(obcy, lambda o: _klucz_osoby(o, cale_imie=False))
    # Ta sama osoba bywa i redaktorem, i autorem (FD#619) — liczymy osoby,
    # nie wiersze.
    ilu_z_inicjalem = {
        inicjal: len({_klucz_osoby(o) for o in osoby})
        for inicjal, osoby in _indeks(
            glowne.authors, lambda o: _klucz_osoby(o, cale_imie=False)
        ).items()
    }

    for osoba in glowne.authors:
        druga = _ta_sama_osoba(
            osoba, po_orcid, po_imieniu, po_inicjale, ilu_z_inicjalem
        )
        if druga is None:
            continue
        for klucz in ("pbn_uid", "orcid"):
            if not osoba.get(klucz) and druga.get(klucz):
                osoba[klucz] = druga[klucz]
                wynik[klucz] += 1
    return wynik


def _polacz(glowne, dodatkowe, wpis) -> dict:
    wpis["pola"] = uzupelnij_brakujace_pola(glowne, dodatkowe)
    wpis["autorzy"] = uzupelnij_autorow(glowne, dodatkowe)
    return wpis


# --- PBN jako drugie źródło ---------------------------------------------------


def _uproszczony_tytul(tytul) -> str:
    return "".join(
        z for z in normalize_nazwisko_do_porownania(tytul or "") if z.isalnum()
    )


def _ten_sam_tytul(a, b) -> bool:
    a, b = _uproszczony_tytul(a), _uproszczony_tytul(b)
    if not a or not b:
        return False
    # Podtytuł bywa tylko po jednej stronie („Tytuł” ↔ „Tytuł. Podtytuł”).
    return a == b or a.startswith(b) or b.startswith(a)


def _identyfikatory_po_isbn(client, isbny) -> list[str]:
    """Identyfikatory prac w PBN o podanych numerach ISBN (bez powtórzeń).

    ISBN idzie w formie kanonicznej i w obu wariantach (ISBN-10/ISBN-13):
    PBN nie normalizuje zapytania ani nie przelicza wariantów.
    """
    znalezione = []
    warianty = []
    for isbn in isbny:
        for wariant in warianty_isbn(isbn):
            if wariant not in warianty:
                warianty.append(wariant)
    for wariant in warianty:
        wyniki = client.search_publications(isbn=wariant)
        for elem in itertools.islice(wyniki, _MAKS_WYNIKOW_ISBN):
            mongo_id = elem.get("mongoId") if isinstance(elem, dict) else None
            if mongo_id and mongo_id not in znalezione:
                znalezione.append(mongo_id)
    return znalezione


def _szukaj_w_pbn_po_isbn(client, uczelnia, result):
    """Zwróć ``(dane publikacji | None, wpis | None)`` dla szukania po ISBN."""
    from pbn_api.exceptions import (
        AccessDeniedException,
        HttpException,
        PraceSerwisoweException,
    )

    from .views.pbn_search import _pbn_url

    isbny = [i for i in (result.isbn, result.e_isbn) if isinstance(i, str) and i]
    try:
        znalezione = _identyfikatory_po_isbn(client, isbny)
        if len(znalezione) > 1:
            return None, _wpis(
                ZRODLO_PBN,
                STAN_NIEJEDNOZNACZNE,
                po="ISBN",
                komunikat=(
                    f"W PBN jest kilka prac o tym numerze ISBN ({len(znalezione)}). "
                    "Wskaż właściwą w kroku „Sprawdź w PBN”."
                ),
            )
        if not znalezione:
            return None, None
        dane = client.get_publication_by_id(znalezione[0])
    except (
        HttpException,
        AccessDeniedException,
        PraceSerwisoweException,
        requests.RequestException,
    ) as e:
        logger.warning("PBN: błąd szukania po ISBN %s: %s", isbny, e)
        return None, _wpis(
            ZRODLO_PBN,
            STAN_NIE_SPRAWDZONO,
            komunikat=f"Nie udało się wyszukać pracy w PBN po ISBN: {e}"[:300],
        )

    from .providers.pbn import _get_current_version_object

    tytul_pbn = (_get_current_version_object(dane) or {}).get("title", "")
    if not _ten_sam_tytul(result.title, tytul_pbn):
        return None, _wpis(
            ZRODLO_PBN,
            STAN_NIEJEDNOZNACZNE,
            po="ISBN",
            url=_pbn_url(uczelnia, znalezione[0]) or "",
            komunikat=(
                "W PBN jest praca o tym numerze ISBN, ale o innym tytule: "
                f"„{tytul_pbn[:200]}”. Jeśli to ta sama praca, wskaż ją "
                "w kroku „Sprawdź w PBN”."
            ),
        )
    return dane, None


def _szukaj_w_pbn(client, uczelnia, result):
    """Znajdź pracę w PBN: po DOI, a książkę także po ISBN.

    Zwraca ``(dane publikacji | None, po_czym, wpis | None)``; ``wpis`` jest
    ustawiony, gdy wynik jest inny niż „znaleziono” i inny niż zwykły brak.
    """
    from .views.pbn_check import _get_pbn_publication_by_doi

    doi = normalize_doi(result.doi) if isinstance(result.doi, str) else None
    if doi:
        dane, blad = _get_pbn_publication_by_doi(client, doi)
        if blad is not None and (blad["pbn_needs_auth"] or blad["pbn_error"]):
            return (
                None,
                None,
                _wpis(
                    ZRODLO_PBN,
                    STAN_NIE_SPRAWDZONO,
                    komunikat=(blad["pbn_error"] or "PBN odmówił dostępu.")[:300],
                ),
            )
        if isinstance(dane, dict) and dane.get("mongoId"):
            return dane, "DOI", None

    if result.publication_type in TYPY_Z_WLASNYMI_REDAKTORAMI:
        dane, wpis = _szukaj_w_pbn_po_isbn(client, uczelnia, result)
        if dane is not None or wpis is not None:
            return dane, "ISBN", wpis
    return None, None, None


def _dolacz_pbn(session, result) -> dict:
    from .providers.pbn import (
        _get_pbn_client,
        _save_to_pbn_publication,
        publikacja_z_danych_pbn,
    )
    from .views.pbn_search import _pbn_url

    try:
        client = _get_pbn_client(session.uczelnia)
    except ValueError:
        # ValueError = uczelnia nie ma skonfigurowanego dostępu do PBN.
        return _wpis(
            ZRODLO_PBN,
            STAN_NIE_SPRAWDZONO,
            komunikat="Dostęp do PBN nie jest skonfigurowany.",
        )

    dane, po_czym, wpis = _szukaj_w_pbn(client, session.uczelnia, result)
    if wpis is not None:
        return wpis
    if dane is None:
        return _wpis(ZRODLO_PBN, STAN_BRAK)

    mongo_id = dane["mongoId"]
    z_pbn = publikacja_z_danych_pbn(dane, mongo_id)
    if z_pbn is None:
        return _wpis(ZRODLO_PBN, STAN_BRAK)

    _save_to_pbn_publication(mongo_id, dane)
    session.matched_data["pbn_mongo_id"] = mongo_id
    return _polacz(
        result,
        z_pbn,
        _wpis(
            ZRODLO_PBN,
            STAN_ZNALEZIONO,
            po=po_czym,
            identyfikator=mongo_id,
            url=_pbn_url(session.uczelnia, mongo_id) or "",
        ),
    )


# --- CrossRef jako drugie źródło ----------------------------------------------


def _pobierz_z_crossref(doi):
    """Dane pracy z CrossRef albo ``None``, gdy CrossRef nie zna DOI.

    Osobna funkcja, żeby testy mogły podstawić odpowiedź bez sieci.
    """
    from .providers import get_provider

    return get_provider(ZRODLO_CROSSREF).fetch(doi)


def _dolacz_crossref(result) -> dict | None:
    """Uzupełnij ``result`` danymi z CrossRef. ``None`` = praca bez DOI
    (nie ma o co pytać)."""
    doi = normalize_doi(result.doi) if isinstance(result.doi, str) else None
    if not doi:
        return None

    try:
        z_crossref = _pobierz_z_crossref(doi)
    except requests.RequestException as e:
        logger.warning("CrossRef: błąd pobierania %s: %s", doi, e)
        return _wpis(
            ZRODLO_CROSSREF,
            STAN_NIE_SPRAWDZONO,
            komunikat=f"Nie udało się pobrać danych z CrossRef: {e}"[:300],
        )
    if z_crossref is None:
        return _wpis(ZRODLO_CROSSREF, STAN_BRAK)

    return _polacz(
        result,
        z_crossref,
        _wpis(
            ZRODLO_CROSSREF,
            STAN_ZNALEZIONO,
            po="DOI",
            identyfikator=doi,
            url=f"https://doi.org/{doi}",
        ),
    )


def _bezpiecznie(session, zrodlo, funkcja, *args):
    """Wywołaj dołączenie jednego źródła tak, by jego awaria nie zabrała
    redaktorowi danych, które już ma (ani nie zablokowała kolejnego
    źródła)."""
    try:
        return funkcja(*args)
    except Exception:
        logger.exception(
            "Sesja importu %s: błąd łączenia ze źródłem %s", session.pk, zrodlo
        )
        capture_exception()
        return _wpis(
            zrodlo,
            STAN_NIE_SPRAWDZONO,
            komunikat="Nieoczekiwany błąd podczas sprawdzania tego źródła.",
        )


def polacz_zrodla(session, result) -> list[dict]:
    """Sprawdź pozostałe źródła i uzupełnij ``result`` tym, czego mu brakuje.

    Import spoza PBN sprawdza PBN; każdy import poza zaczętym od CrossRef
    sprawdza CrossRef (gdy praca ma DOI).

    Wywoływane w zadaniu pobierania, zaraz po odpowiedzi dostawcy i PRZED
    dopasowaniem typu, języka i autorów — dzięki temu identyfikator osoby
    w PBN dociągnięty do autora z CrossRef od razu służy do dopasowania.

    Zmienia ``result`` w miejscu oraz ``session.matched_data`` (odpowiednik
    pracy w PBN). Zwraca listę wpisów dla ``normalized_data[KLUCZ_ZRODEL]``.
    """
    # Ponowienie pobierania zaczyna od zera — odpowiednik z poprzedniej
    # próby mógł dotyczyć innej odpowiedzi dostawcy.
    session.matched_data.pop("pbn_mongo_id", None)

    # Patent nie trafia do PBN i nie ma DOI w CrossRef.
    if result.publication_type == "patent":
        return []

    wpisy = []
    if session.provider_name == ZRODLO_PBN:
        # Praca pobrana z PBN ma w PBN odpowiednik z definicji.
        mongo_id = result.extra.get("pbn_uid")
        if mongo_id:
            session.matched_data["pbn_mongo_id"] = mongo_id
    else:
        # Najpierw PBN: książka znaleziona po ISBN może dopiero stamtąd
        # dostać numer DOI, o który zapytamy CrossRef.
        wpisy.append(_bezpiecznie(session, ZRODLO_PBN, _dolacz_pbn, session, result))

    if session.provider_name != ZRODLO_CROSSREF:
        wpisy.append(_bezpiecznie(session, ZRODLO_CROSSREF, _dolacz_crossref, result))
    return [w for w in wpisy if w is not None]


# --- Profil instytucji w PBN: dyscypliny z oświadczeń -------------------------


def _odswiez_oswiadczenia(session, user, mongo_id) -> str:
    """Pobierz z PBN aktualne oświadczenia instytucji dla tej pracy.

    Profil instytucji wymaga osobistego tokenu PBN redaktora. Bez niego
    (albo gdy PBN odmówi) zostają oświadczenia z lokalnej kopii danych PBN.
    Zwraca opis, skąd są oświadczenia.
    """
    from pbn_api.exceptions import (
        AccessDeniedException,
        HttpException,
        PraceSerwisoweException,
        WillNotExportError,
    )
    from pbn_api.models import Publication

    from .views.pbn_search import _operator_pbn_logged_in

    lokalne = "z lokalnej kopii danych PBN"
    if session.uczelnia is None or not _operator_pbn_logged_in(user):
        return lokalne
    pub = Publication.objects.filter(pk=mongo_id).first()
    if pub is None:
        return lokalne
    try:
        session.uczelnia.pbn_client(user.pbn_token).download_statements_of_publication(
            pub
        )
    except (
        HttpException,
        AccessDeniedException,
        PraceSerwisoweException,
        WillNotExportError,
        requests.RequestException,
    ) as e:
        logger.warning("PBN: nie udało się pobrać oświadczeń pracy %s: %s", mongo_id, e)
        return lokalne
    return "pobrane z PBN"


def _dyscyplina_z_oswiadczenia(oswiadczenie):
    from bpp.models import Dyscyplina_Naukowa

    try:
        return oswiadczenie.get_bpp_discipline()
    except (Dyscyplina_Naukowa.DoesNotExist, KeyError, TypeError):
        # Dyscyplina spoza słownika BPP albo oświadczenie bez nazwy
        # dyscypliny — nie ma czego podpowiedzieć.
        return None


#: Rola osoby w importerze → typ oświadczenia w PBN.
_TYP_OSWIADCZENIA = {const.TO_AUTOR: "AUTHOR", const.TO_REDAKTOR: "EDITOR"}


def _oswiadczenia_po_osobie(session) -> dict:
    """Oświadczenia instytucji dla pracy tej sesji z lokalnej kopii danych
    PBN: ``{(identyfikator osoby, typ oświadczenia): oświadczenie}``."""
    from pbn_api.models import OswiadczenieInstytucji

    mongo_id = (session.matched_data or {}).get("pbn_mongo_id")
    if not mongo_id or session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT:
        return {}

    oswiadczenia = OswiadczenieInstytucji.objects.filter(publicationId_id=mongo_id)
    uczelnia = session.uczelnia
    if uczelnia is not None and uczelnia.pbn_uid_id:
        oswiadczenia = oswiadczenia.filter(institutionId_id=uczelnia.pbn_uid_id)
    return {(o.personId_id, o.type): o for o in oswiadczenia}


def _dyscyplina_z_pbn(po_osobie, imported):
    """Dyscyplina z oświadczenia autora w PBN albo ``None``."""
    if imported.matched_autor is None:
        return None
    osoba = imported.pbn_uid or imported.matched_autor.pbn_uid_id
    oswiadczenie = po_osobie.get((osoba, _TYP_OSWIADCZENIA.get(imported.typ_ogolny)))
    if oswiadczenie is None:
        return None
    return _dyscyplina_z_oswiadczenia(oswiadczenie)


def _wolno_ustawic_dyscypline(session, imported, dyscyplina, rok) -> bool:
    """Czy dyscyplinę z oświadczenia da się zapisać w rekordzie pracy.

    Te same reguły, co przy tworzeniu rekordu: autor z przypisaniem na rok
    pracy musi mieć w nim tę dyscyplinę (FD#623); autor bez przypisania
    dostanie je przy tworzeniu rekordu tylko jako autor uczelni (FD#620,
    FD#640). Oświadczenia, którego nie da się zapisać, nie podpowiadamy —
    zablokowałoby utworzenie pracy.
    """
    from django.db.models import Q

    from bpp.models import Autor_Dyscyplina

    from .dyscypliny import _uczelnia_autora, ma_przypisanie_na_rok

    autor = imported.matched_autor
    if not rok:
        return True
    if ma_przypisanie_na_rok(autor, rok):
        return (
            Autor_Dyscyplina.objects.filter(autor=autor, rok=rok)
            .filter(
                Q(dyscyplina_naukowa=dyscyplina) | Q(subdyscyplina_naukowa=dyscyplina)
            )
            .exists()
        )
    return autor.jest_autorem_uczelni(_uczelnia_autora(session, imported))


def zastosuj_dyscypliny_z_profilu(session, tylko=None) -> tuple[int, int]:
    """Ustaw dopasowanym autorom dyscypliny z oświadczeń w profilu instytucji.

    Bez sieci — czyta lokalną kopię oświadczeń. Oświadczenie z PBN jest
    mocniejsze niż domysł „autor ma jedną dyscyplinę”, ale nigdy nie
    nadpisuje wyboru redaktora ani dyscypliny ze zgłoszenia publikacji.
    Zwraca ``(ustawione, pominięte)``; pominięte to oświadczenia niezgodne
    z przypisaniem dyscyplin autora w BPP na rok pracy.

    ``tylko`` — identyfikatory wierszy autorów, do których ograniczyć
    działanie (np. właśnie utworzeni autorzy); ``None`` = wszyscy.
    """
    po_osobie = _oswiadczenia_po_osobie(session)
    if not po_osobie:
        return 0, 0

    rok = (session.normalized_data or {}).get("year")
    Zrodlo = ImportedAuthor.DyscyplinaSource
    ustawione = pominiete = 0
    wiersze = session.authors.filter(matched_autor__isnull=False)
    if tylko is not None:
        wiersze = wiersze.filter(pk__in=tylko)
    for imported in wiersze.select_related(
        "matched_autor", "matched_jednostka__uczelnia"
    ):
        if imported.dyscyplina_source in (Zrodlo.MANUAL, Zrodlo.ZGLOSZENIE):
            continue
        dyscyplina = _dyscyplina_z_pbn(po_osobie, imported)
        if dyscyplina is None:
            continue
        if not _wolno_ustawic_dyscypline(session, imported, dyscyplina, rok):
            pominiete += 1
            continue
        imported.matched_dyscyplina = dyscyplina
        imported.dyscyplina_source = Zrodlo.PBN_PROFIL
        imported.save(update_fields=["matched_dyscyplina", "dyscyplina_source"])
        ustawione += 1
    return ustawione, pominiete


def dolacz_profil_instytucji(session, user) -> dict | None:
    """Dociągnij dyscypliny z oświadczeń w profilu instytucji w PBN.

    ``None``, gdy praca nie ma odpowiednika w PBN (nie ma czego sprawdzać).
    """
    mongo_id = (session.matched_data or {}).get("pbn_mongo_id")
    if not mongo_id or session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT:
        return None

    try:
        skad = _odswiez_oswiadczenia(session, user, mongo_id)
        ustawione, pominiete = zastosuj_dyscypliny_z_profilu(session)
    except Exception:
        # Jak w ``polacz_zrodla``: dodatek nie może wywrócić importu.
        logger.exception(
            "Sesja importu %s: błąd pobierania oświadczeń z profilu instytucji",
            session.pk,
        )
        capture_exception()
        return _wpis(
            ZRODLO_PROFIL,
            STAN_NIE_SPRAWDZONO,
            komunikat="Nieoczekiwany błąd podczas odczytu oświadczeń.",
        )
    return _wpis(
        ZRODLO_PROFIL,
        STAN_ZNALEZIONO if ustawione else STAN_BRAK,
        dyscypliny=ustawione,
        pominiete=pominiete,
        oswiadczenia=skad,
    )


def _dyscypliny_ze_zgloszenia(session) -> dict:
    """``{pk autora BPP: dyscyplina}`` ze zgłoszenia publikacji tej sesji."""
    from .views.authors import _zgloszenie_dla_prefilla

    zgloszenie = _zgloszenie_dla_prefilla(session)
    if zgloszenie is None:
        return {}

    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    return {
        zpa.autor_id: zpa.dyscyplina_naukowa
        for zpa in Zgloszenie_Publikacji_Autor.objects.filter(
            rekord=zgloszenie, dyscyplina_naukowa__isnull=False
        ).select_related("dyscyplina_naukowa")
    }


def _dyscypliny_na_rok(autorzy, rok) -> dict:
    """``{pk autora BPP: [dyscypliny przypisane na rok]}``."""
    from bpp.models import Autor_Dyscyplina

    wynik = {}
    if not rok:
        return wynik
    for ad in Autor_Dyscyplina.objects.filter(
        rok=rok, autor_id__in=autorzy
    ).select_related("dyscyplina_naukowa", "subdyscyplina_naukowa"):
        wynik.setdefault(ad.autor_id, []).extend(
            d
            for d in (ad.dyscyplina_naukowa, ad.subdyscyplina_naukowa)
            if d is not None
        )
    return wynik


def uwagi_o_dyscyplinach(session) -> dict:
    """Rozbieżności między dyscypliną z oświadczenia w PBN a pozostałymi
    źródłami — do pokazania przy autorze w kroku „Dopasowanie autorów”.

    Zwraca ``{pk wiersza autora: uwaga}`` tylko dla autorów, u których coś
    się nie zgadza. ``uwaga`` to słownik:

    * ``pbn`` — dyscyplina z oświadczenia w profilu instytucji,
    * ``przyjeta`` — dyscyplina, z którą autor trafi do rekordu (lub ``None``),
    * ``zgloszenie`` — dyscyplina ze zgłoszenia publikacji, gdy jest inna
      niż w PBN,
    * ``na_rok`` — dyscypliny przypisane autorowi w BPP na rok pracy, gdy
      nie ma wśród nich tej z PBN (wtedy to ostrzeżenie: takiej dyscypliny
      nie da się zapisać w rekordzie, a PBN zapewne nie przyjmie
      oświadczenia z inną),
    * ``rok`` — rok pracy.

    Liczone przy wyświetlaniu, z bieżącego stanu bazy — niczego nie zmienia.
    """
    po_osobie = _oswiadczenia_po_osobie(session)
    if not po_osobie:
        return {}

    rok = (session.normalized_data or {}).get("year")
    wiersze = list(
        session.authors.filter(matched_autor__isnull=False).select_related(
            "matched_autor", "matched_dyscyplina"
        )
    )

    ze_zgloszenia = _dyscypliny_ze_zgloszenia(session)
    na_rok = _dyscypliny_na_rok([w.matched_autor_id for w in wiersze], rok)

    uwagi = {}
    for imported in wiersze:
        z_pbn = _dyscyplina_z_pbn(po_osobie, imported)
        if z_pbn is None:
            continue
        uwaga = {"pbn": z_pbn, "przyjeta": imported.matched_dyscyplina, "rok": rok}
        w_zgloszeniu = ze_zgloszenia.get(imported.matched_autor_id)
        if w_zgloszeniu is not None and w_zgloszeniu != z_pbn:
            uwaga["zgloszenie"] = w_zgloszeniu
        przypisane = na_rok.get(imported.matched_autor_id)
        if przypisane and z_pbn not in przypisane:
            uwaga["na_rok"] = przypisane
        if "zgloszenie" in uwaga or "na_rok" in uwaga:
            uwagi[imported.pk] = uwaga
    return uwagi
