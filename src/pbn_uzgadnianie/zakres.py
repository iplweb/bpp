"""Etap 1: odświeżenie kopii danych PBN i ustalenie zakresu uzgadniania.

Zakres to prace z PROFILU INSTYTUCJI w PBN — odczytanego w tym przebiegu,
nie z całej lokalnej tabeli publikacji PBN (w niej są też prace obce:
książki nadrzędne, prace pobrane przy innych okazjach, wpisy po pracach
zdjętych z profilu — FD#552).
"""

import logging
import sys
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from bpp.zglaszanie_bledow import capture_exception
from pbn_api.exceptions import HttpException, PublicationNotFound
from pbn_api.models import Publication
from pbn_integrator.utils import zapisz_mongodb
from pbn_integrator.utils.mongodb_ops import zapisz_publikacje_instytucji
from pbn_integrator.utils.publications import zapisz_publikacje_instytucji_v2

from .dyscypliny import pobierz_oswiadczenia
from .odpowiedniki import identyfikatory, rekordy_bpp_uczelni

logger = logging.getLogger(__name__)


class Anulowano(Exception):
    """Użytkownik anulował przebieg."""


def _dopisz(profil, pbn_uid, wersja=None, rok=None):
    wpis = profil.setdefault(pbn_uid, {"wersje": [], "rok": None})
    if wersja and str(wersja) not in wpis["wersje"]:
        wpis["wersje"].append(str(wersja))
    if rok and not wpis["rok"]:
        wpis["rok"] = int(rok)


def _blad(bledy, etap, opis, pbn_uid=None):
    """Loguje bieżący wyjątek z tracebackiem i dopisuje go do raportu."""
    logger.exception("Uzgodnienie z PBN, %s: %s (%s)", etap, opis, pbn_uid)
    capture_exception(sys.exc_info(), extra={"etap": etap, "pbn_uid": pbn_uid})
    bledy.append({"etap": etap, "pbn_uid": pbn_uid, "opis": opis})


def _z_licznikiem(zasob):
    """``(numer, łączna liczba albo None, element)`` dla stronicowanej
    odpowiedzi PBN. Łączną liczbę PBN podaje w pierwszej stronie."""
    ile = getattr(zasob, "total_elements", None)
    if ile is None and hasattr(zasob, "__len__"):
        ile = len(zasob)
    for nr, elem in enumerate(zasob, 1):
        yield nr, ile, elem


def _postep_profilu(nadzorca, co, nr, ile, procent_od, procent_do):
    """Licznik pobierania profilu — co 25 wpisów (profil bywa duży i bez
    licznika wyglądało to na zawieszenie)."""
    if nr != 1 and nr % 25:
        return
    if ile:
        opis = f"{nr} z {ile}"
        procent = procent_od + (procent_do - procent_od) * nr // ile
    else:
        opis, procent = f"{nr}", procent_od
    nadzorca.etap(f"Pobieranie profilu instytucji z PBN — {co}: {opis}", procent)


def pobierz_profil_instytucji(client, uczelnia, nadzorca, bledy):
    """Czyta profil instytucji z PBN (API v1 i v2) i zapisuje go w kopii.

    Zwraca ``{pbn_uid: {"wersje": [...], "rok": int | None}}`` — WSZYSTKIE
    prace profilu (bez filtra lat; filtr nakłada ``wyznacz_zakres``).
    """
    profil = {}

    for nr, ile, elem in _z_licznikiem(
        client.get_institution_publications(page_size=100)
    ):
        nadzorca.sprawdz_anulowanie()
        _postep_profilu(nadzorca, "lista prac i osób", nr, ile, 2, 5)
        if elem.get("institutionId") != uczelnia.pbn_uid_id:
            continue
        pbn_uid = elem.get("publicationId")
        if not pbn_uid:
            continue
        _dopisz(
            profil,
            pbn_uid,
            wersja=elem.get("publicationVersion"),
            rok=elem.get("publicationYear"),
        )
        try:
            zapisz_publikacje_instytucji(dict(elem), None, client=client)
        except HttpException as e:
            _blad(bledy, "profil instytucji", f"PBN zwrócił błąd: {e}", pbn_uid)

    for nr, ile, elem in _z_licznikiem(client.get_institution_publications_v2()):
        nadzorca.sprawdz_anulowanie()
        _postep_profilu(nadzorca, "lista prac (API v2)", nr, ile, 6, 9)
        pbn_uid = elem.get("objectId")
        if not pbn_uid:
            continue
        _dopisz(profil, pbn_uid)
        try:
            zapisz_publikacje_instytucji_v2(client, dict(elem))
        except (HttpException, IntegrityError) as e:
            # IntegrityError: PBN nie oddał samej publikacji (błąd 500 po ich
            # stronie), więc wiersza profilu nie ma do czego podpiąć.
            _blad(bledy, "profil instytucji (v2)", f"Nie zapisano: {e}", pbn_uid)

    return profil


def _rok_z_kopii(pbn_uid):
    return Publication.objects.filter(pk=pbn_uid).values_list("year", flat=True).first()


def wyznacz_zakres(profil, rok_od, rok_do):
    """Prace profilu z lat ``rok_od``–``rok_do`` → posortowana lista ``pbn_uid``.

    Rok bierzemy z profilu instytucji, a gdy go tam nie ma — z kopii
    publikacji. Prace bez ustalonego roku trafiają na osobną listę
    (raport: „rok nieznany”), nie do zakresu.
    """
    w_zakresie, bez_roku = [], []
    for pbn_uid in sorted(profil):
        rok = profil[pbn_uid]["rok"] or _rok_z_kopii(pbn_uid)
        if rok is None:
            bez_roku.append(pbn_uid)
        elif rok_od <= rok <= rok_do:
            w_zakresie.append(pbn_uid)
    return w_zakresie, bez_roku


def odswiez_oswiadczenia(client, uczelnia, pbn_uids, nadzorca, bledy):
    """Oświadczenia instytucji (dyscypliny) dla prac z zakresu, prosto z PBN.

    Zwraca ``{pbn_uid: [oświadczenia]}``; pracy, dla której PBN zwrócił
    błąd, w słowniku NIE ma (znaczy: „nie wiadomo”, a nie „brak oświadczeń”).
    """
    wynik = {}
    ile = len(pbn_uids)
    for nr, pbn_uid in enumerate(pbn_uids, 1):
        nadzorca.sprawdz_anulowanie()
        nadzorca.etap(f"Pobieranie oświadczeń z PBN: {nr} z {ile}", 30 + 30 * nr // ile)
        try:
            oswiadczenia = pobierz_oswiadczenia(
                client,
                uczelnia,
                pbn_uid,
                lambda opis, pbn_uid=pbn_uid: _blad(
                    bledy, "oświadczenia", opis, pbn_uid
                ),
            )
        except IntegrityError as e:
            # Kopia nie przyjęła oświadczenia (np. PBN nie oddał osoby).
            _blad(bledy, "oświadczenia", f"Nie zapisano w kopii: {e}", pbn_uid)
            continue
        if oswiadczenia is not None:
            wynik[pbn_uid] = oswiadczenia
    return wynik


def odswiez_publikacje(client, pbn_uids, nadzorca, bledy):
    """Pobiera z PBN aktualne dane (wszystkie wersje) wskazanych publikacji.

    Samo „Pobieranie danych z PBN” dociąga tylko publikacje, których w kopii
    jeszcze nie ma — istniejących nie odświeża, więc po zmianie w PBN kopia
    byłaby nieaktualna. Zwraca listę ``pbn_uid``, których w PBN już nie ma.
    """
    nie_istnieja = []
    ile = len(pbn_uids)
    for nr, pbn_uid in enumerate(pbn_uids, 1):
        nadzorca.sprawdz_anulowanie()
        nadzorca.etap(f"Pobieranie publikacji z PBN: {nr} z {ile}", 10 + 20 * nr // ile)
        try:
            dane = client.get_publication_by_id(pbn_uid)
        except PublicationNotFound:
            # To nie awaria, tylko informacja: pracy nie ma już w PBN.
            logger.info("Uzgodnienie z PBN: pracy %s nie ma już w PBN", pbn_uid)
            nie_istnieja.append(pbn_uid)
            continue
        except HttpException as e:
            _blad(bledy, "odświeżanie publikacji", f"PBN zwrócił błąd: {e}", pbn_uid)
            continue
        zapisz_mongodb(dane, Publication)
    return nie_istnieja


def _swieze(wpis, teraz):
    """Czy wynik wyszukiwania jest jeszcze świeży (próg jak dla ostrzeżeń)."""
    granica = teraz - timedelta(hours=settings.PBN_UZGADNIANIE_DANE_AKTUALNE_GODZIN)
    return datetime.fromisoformat(wpis["kiedy"]) >= granica


def wyszukaj_w_pbn(client, uczelnia, rok_od, rok_do, nadzorca, bledy, poprzednie):
    """Pyta PBN o rekordy BPP bez powiązania: po DOI, a książki także po ISBN.

    Profil instytucji nie mówi nic o pracach spoza profilu — bez tego kroku
    nie da się odróżnić „pracy nie ma w PBN” od „jest, ale gdzie indziej”.

    Zwraca ``{klucz: {"uids": [...], "kiedy": ISO}}``; pusta lista = PBN nie
    ma pracy o tym identyfikatorze. Jedno zapytanie na unikalny identyfikator;
    wyniki z ``poprzednie`` (wcześniejsze pobranie), póki świeże, są brane
    bez pytania. Klucza, dla którego PBN zwrócił błąd, w słowniku nie ma.
    """
    teraz = timezone.now()
    klucze = []
    for rekord in rekordy_bpp_uczelni(uczelnia, rok_od, rok_do).filter(pbn_uid_id=None):
        for klucz in identyfikatory(rekord):
            if klucz not in klucze:
                klucze.append(klucz)

    wynik = {}
    ile = len(klucze)
    for nr, klucz in enumerate(klucze, 1):
        nadzorca.sprawdz_anulowanie()
        stary = (poprzednie or {}).get(klucz)
        if stary and _swieze(stary, teraz):
            wynik[klucz] = stary
            continue
        nadzorca.etap(
            f"Szukanie w PBN prac po DOI/ISBN: {nr} z {ile}", 60 + 35 * nr // ile
        )
        pole, _, wartosc = klucz.partition(":")
        try:
            uids = [e["mongoId"] for e in client.search_publications(**{pole: wartosc})]
            for pbn_uid in uids:
                zapisz_mongodb(client.get_publication_by_id(pbn_uid), Publication)
        except HttpException as e:
            _blad(bledy, "szukanie po DOI/ISBN", f"PBN zwrócił błąd: {e}", klucz)
            continue
        wynik[klucz] = {"uids": uids, "kiedy": timezone.now().isoformat()}
    return wynik


def zbuduj_zakres(client, uczelnia, rok_od, rok_do, nadzorca, poprzedni=None):
    """Pobranie danych z PBN. Zwraca słownik dla ``UzgodnienieZPBN.zakres``.

    ``poprzedni`` — zakres wcześniejszego pobrania tej uczelni:

    * ``{"profil": …}`` z kluczem ``uzyj_profilu`` — lista prac z profilu
      jest brana stamtąd (z JEJ datą), bez pobierania;
    * świeże wyniki wyszukiwania po DOI/ISBN są brane stamtąd zawsze.

    ``pobrano`` to chwile zakończenia pobierania każdego ze źródeł (ISO) —
    jedyne wiarygodne „z kiedy są dane”: daty modyfikacji wierszy kopii
    mówią, kiedy wiersz się ZMIENIŁ, a nie kiedy sprawdzono go w PBN.
    """
    poprzedni = poprzedni or {}
    bledy, pobrano = [], {}
    if poprzedni.get("uzyj_profilu"):
        profil = poprzedni["profil"]
        pobrano["profil"] = poprzedni["pobrano"]["profil"]
    else:
        profil = pobierz_profil_instytucji(client, uczelnia, nadzorca, bledy)
        pobrano["profil"] = timezone.now().isoformat()
    w_zakresie, bez_roku = wyznacz_zakres(profil, rok_od, rok_do)
    nie_istnieja = odswiez_publikacje(client, w_zakresie, nadzorca, bledy)
    pobrano["publikacje"] = timezone.now().isoformat()
    # Rok mógł się zmienić w PBN — po odświeżeniu sprawdzamy jeszcze raz
    # prace, dla których profil roku nie podał.
    w_zakresie, bez_roku = wyznacz_zakres(profil, rok_od, rok_do)
    oswiadczenia = odswiez_oswiadczenia(client, uczelnia, w_zakresie, nadzorca, bledy)
    pobrano["oswiadczenia"] = timezone.now().isoformat()
    szukane = wyszukaj_w_pbn(
        client, uczelnia, rok_od, rok_do, nadzorca, bledy, poprzedni.get("szukane")
    )
    # Data źródła = najstarszy z użytych wyników (część mogła być wzięta
    # z poprzedniego pobrania).
    pobrano["wyszukiwanie"] = min(
        (w["kiedy"] for w in szukane.values()), default=timezone.now().isoformat()
    )
    return {
        "pobrano": pobrano,
        "pobrano_lata": [rok_od, rok_do],
        "oswiadczenia": oswiadczenia,
        "szukane": szukane,
        "profil": profil,
        "w_zakresie": w_zakresie,
        "bez_roku": bez_roku,
        "nie_istnieja_w_pbn": nie_istnieja,
        "bledy_pobierania": bledy,
    }


def zawez_zakres(zakres, rok_od, rok_do):
    """Zakres pobrany dla szerszych lat, zawężony do ``rok_od``–``rok_do``."""
    w_zakresie, bez_roku = wyznacz_zakres(zakres["profil"], rok_od, rok_do)
    return {**zakres, "w_zakresie": w_zakresie, "bez_roku": bez_roku}
