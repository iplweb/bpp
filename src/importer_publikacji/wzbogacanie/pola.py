"""Porównanie pól rekordu BPP z danymi ze źródła i przenoszenie wybranych.

Dane ze źródła przychodzą jako ``FetchedPublication`` — w tej samej postaci,
z której importer publikacji tworzy nowe rekordy. Tu jest tylko to, czego
importer nie potrzebuje: porównanie z ISTNIEJĄCYM rekordem i zapis pojedynczych
pól. Słowniki (język, licencja) dopasowują te same funkcje co przy imporcie.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.utils.html import format_html

from bpp.admin.helpers.porownanie_wersji import diff_slow
from bpp.models import nie_zawiera_adresu_doi_org
from import_common import porownanie_pol as reguly

ZGODNE = "zgodne"
ROZNE = "rozne"
BRAK_W_BPP = "brak_w_bpp"
BRAK_W_ZRODLE = "brak_w_zrodle"
NIEROZPOZNANE = "nierozpoznane"

ETYKIETY_STATUSU = {
    ZGODNE: "zgodne",
    ROZNE: "różne",
    BRAK_W_BPP: "brak w BPP",
    BRAK_W_ZRODLE: "brak w źródle",
    NIEROZPOZNANE: "nie rozpoznano",
}

PUSTE = "—"


@dataclass
class Wiersz:
    """Jedno pole w porównaniu „źródło ↔ BPP”."""

    klucz: str
    etykieta: str
    status: str
    zrodlo: str = PUSTE
    bpp: str = PUSTE
    zmiana: str = ""
    uwaga: str = ""
    #: Zapisuje wartość ze źródła w rekordzie; ``None`` — pola nie da się
    #: przenieść (zgodne, puste w źródle albo wartość nie do zapisania).
    zastosuj: Callable | None = None
    #: Dla pól zapisywanych w powiązanych tabelach (streszczenia, słowa
    #: kluczowe): wykonywane PO zapisie rekordu.
    po_zapisie: bool = False

    @property
    def status_tekst(self):
        return ETYKIETY_STATUSU[self.status]

    @property
    def rozni_sie(self):
        return self.status in (ROZNE, BRAK_W_BPP)

    @property
    def mozna_przeniesc(self):
        return self.rozni_sie and self.zastosuj is not None

    @property
    def token(self):
        """Skrót wartości ze źródła — zatwierdzenie przenosi dokładnie to, co
        redaktor widział na podglądzie (dane źródła mogły się zmienić)."""
        return hashlib.sha1(
            self.zrodlo.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:12]

    @property
    def wartosc_wyboru(self):
        return f"{self.klucz}:{self.token}"


def _etykieta(pole):
    nazwa = str(pole.verbose_name)
    if nazwa[1:2] == "-":  # „e-ISSN” zostaje, jak jest
        return nazwa
    return nazwa[:1].upper() + nazwa[1:]


def _pole(rekord, nazwa):
    try:
        return rekord._meta.get_field(nazwa)
    except FieldDoesNotExist:
        return None


def _zmiana(status, bpp, zrodlo):
    if status == ROZNE:
        return diff_slow(bpp, zrodlo)
    if status == BRAK_W_BPP:
        return format_html("<ins>{}</ins>", zrodlo)
    return ""


def _blad_walidacji(pole, wartosc, rekord, walidatory):
    """Powód, dla którego ``wartosc`` nie nadaje się do pola (albo ``""``)."""
    try:
        pole.clean(wartosc, rekord)
        for walidator in walidatory:
            walidator(wartosc)
    except ValidationError as e:
        return " ".join(e.messages)
    return ""


def _wiersz_prosty(
    rekord,
    nazwa,
    wartosc,
    *,
    normalizuj=reguly.tekst,
    do_zapisu=reguly.odstepy,
    alternatywa=None,
    walidatory=(),
    pomin_gdy_brak_w_zrodle=False,
):
    """Wiersz dla zwykłego pola rekordu (tekst, liczba, identyfikator).

    ``alternatywa`` — drugie pole BPP, w którym ta sama wartość też jest „na
    miejscu” (np. ISSN zapisany w BPP jako e-ISSN, adres w polu wolnego
    dostępu) — wtedy pole uznajemy za zgodne, z wyjaśnieniem."""
    pole = _pole(rekord, nazwa)
    if pole is None:
        return None
    obecna = getattr(rekord, nazwa)
    z, b = normalizuj(wartosc), normalizuj(obecna)
    if not z and (not b or pomin_gdy_brak_w_zrodle):
        return None
    wiersz = Wiersz(
        klucz=nazwa,
        etykieta=_etykieta(pole),
        status=ZGODNE,
        zrodlo=reguly.odstepy(wartosc) or PUSTE,
        bpp=reguly.odstepy(obecna) or PUSTE,
    )
    if not z:
        wiersz.status = BRAK_W_ZRODLE
        return wiersz
    if z == b:
        return wiersz
    pole_alt = _pole(rekord, alternatywa) if alternatywa else None
    if pole_alt is not None and normalizuj(getattr(rekord, alternatywa)) == z:
        wiersz.uwaga = f"W BPP ta wartość jest w polu „{_etykieta(pole_alt)}”."
        return wiersz

    wiersz.status = ROZNE if b else BRAK_W_BPP
    wiersz.zmiana = _zmiana(wiersz.status, wiersz.bpp, wiersz.zrodlo)
    nowa = do_zapisu(wartosc)
    blad = _blad_walidacji(pole, nowa, rekord, walidatory)
    if blad:
        wiersz.uwaga = f"Tej wartości nie da się zapisać w BPP: {blad}"
        return wiersz

    def zastosuj(r, nazwa=nazwa, nowa=nowa):
        setattr(r, nazwa, nowa)

    wiersz.zastosuj = zastosuj
    return wiersz


def _wiersz_slownikowy(rekord, nazwa, kod, znajdz, opis_brakujacego):
    """Wiersz dla pola wskazującego pozycję słownika BPP (język, licencja).

    ``znajdz(kod)`` zwraca pozycję słownika albo ``None``; nieznanej wartości
    nie przenosimy — redaktor dostaje informację, czego brakuje w słowniku."""
    pole = _pole(rekord, nazwa)
    if pole is None:
        return None
    obecna = getattr(rekord, nazwa)
    if not kod and obecna is None:
        return None
    wiersz = Wiersz(
        klucz=nazwa,
        etykieta=_etykieta(pole),
        status=ZGODNE,
        bpp=str(obecna) if obecna is not None else PUSTE,
    )
    if not kod:
        wiersz.status = BRAK_W_ZRODLE
        return wiersz
    nowa = znajdz(kod)
    if nowa is None:
        wiersz.status = NIEROZPOZNANE
        wiersz.zrodlo = str(kod)
        wiersz.uwaga = opis_brakujacego
        return wiersz
    wiersz.zrodlo = str(nowa)
    if obecna is not None and obecna.pk == nowa.pk:
        return wiersz
    wiersz.status = ROZNE if obecna is not None else BRAK_W_BPP
    wiersz.zmiana = _zmiana(wiersz.status, wiersz.bpp, wiersz.zrodlo)

    def zastosuj(r, nazwa=nazwa, nowa=nowa):
        setattr(r, nazwa, nowa)

    wiersz.zastosuj = zastosuj
    return wiersz


def _znajdz_jezyk(kod):
    """Język BPP dla kodu ze źródła — tak samo jak przy imporcie: kod
    CrossRef / ISO (importer publikacji), potem kod PBN (import z PBN)."""
    from pbn_integrator.importer.helpers import _znajdz_jezyk as jezyk_z_pbn

    from ..views.publikacja import _resolve_jezyk

    return _resolve_jezyk(kod) or jezyk_z_pbn(kod)


def _znajdz_licencje(adres):
    """Licencja otwartego dostępu dla adresu licencji — tym samym
    dopasowaniem, co „Pobierz z CrossRef” przy dodawaniu rekordu."""
    from crossref_bpp.core import Komparator

    return Komparator.porownaj_license({"URL": adres}).rekord_po_stronie_bpp


def _slowa(lista):
    return {reguly.odstepy(s).casefold() for s in lista if reguly.odstepy(s)}


def _wiersz_slow_kluczowych(rekord, slowa):
    if not hasattr(rekord, "slowa_kluczowe"):
        return None
    slowa = [reguly.odstepy(s) for s in slowa or [] if reguly.odstepy(s)]
    obecne = sorted(rekord.slowa_kluczowe.names(), key=str.casefold)
    if not slowa and not obecne:
        return None
    wiersz = Wiersz(
        klucz="slowa_kluczowe",
        etykieta="Słowa kluczowe",
        status=ZGODNE,
        zrodlo=", ".join(slowa) or PUSTE,
        bpp=", ".join(obecne) or PUSTE,
        po_zapisie=True,
    )
    if not slowa:
        wiersz.status = BRAK_W_ZRODLE
        return wiersz
    if _slowa(slowa) == _slowa(obecne):
        return wiersz
    wiersz.status = ROZNE if obecne else BRAK_W_BPP
    wiersz.zmiana = _zmiana(wiersz.status, wiersz.bpp, wiersz.zrodlo)
    if wiersz.status == ROZNE:
        wiersz.uwaga = "Przeniesienie zastąpi słowa kluczowe rekordu tymi ze źródła."

    def zastosuj(r, slowa=slowa):
        r.slowa_kluczowe.set(slowa)

    wiersz.zastosuj = zastosuj
    return wiersz


def _wiersze_streszczen(rekord, publikacja):
    """Po wierszu na każde streszczenie ze źródła, którego rekord nie ma.
    Przeniesienie DODAJE streszczenie — istniejących nie rusza."""
    from ..views.helpers import _detect_language
    from ..views.publikacja import _build_abstracts_list

    if not hasattr(rekord, "streszczenia"):
        return
    obecne = [s.streszczenie for s in rekord.streszczenia.all()]
    obecne_norm = {reguly.tekst(s) for s in obecne if reguly.tekst(s)}
    ze_zrodla = [
        (reguly.odstepy(a.get("text")), a.get("language"))
        for a in _build_abstracts_list(publikacja)
        if reguly.tekst(a.get("text"))
    ]
    if not ze_zrodla:
        if obecne_norm:
            yield Wiersz(
                klucz="streszczenie",
                etykieta="Streszczenie",
                status=BRAK_W_ZRODLE,
                bpp=reguly.odstepy(obecne[0]),
            )
        return
    for nr, (tekst, kod_jezyka) in enumerate(ze_zrodla):
        wiersz = Wiersz(
            klucz=f"streszczenie-{nr}",
            etykieta="Streszczenie",
            status=ZGODNE,
            zrodlo=tekst,
            bpp=tekst,
            po_zapisie=True,
        )
        if reguly.tekst(tekst) not in obecne_norm:
            wiersz.status = ROZNE if obecne_norm else BRAK_W_BPP
            wiersz.bpp = reguly.odstepy(obecne[0]) if obecne else PUSTE
            wiersz.zmiana = _zmiana(wiersz.status, wiersz.bpp, tekst)
            if obecne_norm:
                wiersz.uwaga = (
                    "Przeniesienie doda kolejne streszczenie — istniejące zostaną."
                )

            def zastosuj(r, tekst=tekst, kod_jezyka=kod_jezyka):
                jezyk = _znajdz_jezyk(kod_jezyka or _detect_language(tekst))
                r.streszczenia.create(streszczenie=tekst, jezyk_streszczenia=jezyk)

            wiersz.zastosuj = zastosuj
        yield wiersz


def porownaj(rekord, publikacja) -> list[Wiersz]:
    """Wiersze porównania rekordu BPP z danymi ze źródła (``publikacja``)."""
    p = publikacja
    kandydaci = [
        _wiersz_prosty(rekord, "tytul_oryginalny", p.title),
        _wiersz_prosty(
            rekord,
            "tytul",
            p.extra.get("original_title"),
            pomin_gdy_brak_w_zrodle=True,
        ),
        _wiersz_prosty(rekord, "rok", p.year, normalizuj=reguly.rok, do_zapisu=int),
        _wiersz_prosty(
            rekord, "doi", p.doi, normalizuj=reguly.doi, do_zapisu=reguly.doi
        ),
        _wiersz_prosty(rekord, "tom", p.volume),
        _wiersz_prosty(rekord, "nr_zeszytu", p.issue),
        _wiersz_prosty(rekord, "strony", p.pages, normalizuj=reguly.strony),
        _wiersz_prosty(
            rekord, "issn", p.issn, normalizuj=reguly.numer, alternatywa="e_issn"
        ),
        _wiersz_prosty(
            rekord, "e_issn", p.e_issn, normalizuj=reguly.numer, alternatywa="issn"
        ),
        _wiersz_prosty(
            rekord, "isbn", p.isbn, normalizuj=reguly.numer, alternatywa="e_isbn"
        ),
        _wiersz_prosty(
            rekord, "e_isbn", p.e_isbn, normalizuj=reguly.numer, alternatywa="isbn"
        ),
        _wiersz_prosty(
            rekord,
            "www",
            p.url,
            normalizuj=reguly.adres,
            alternatywa="public_www",
            walidatory=(nie_zawiera_adresu_doi_org,),
        ),
        _wiersz_slownikowy(
            rekord,
            "jezyk",
            p.language,
            _znajdz_jezyk,
            "Tego języka nie ma w słowniku języków BPP (Dane systemowe → Języki).",
        ),
        _wiersz_slownikowy(
            rekord,
            "openaccess_licencja",
            p.license_url,
            _znajdz_licencje,
            "Tej licencji nie ma w słowniku licencji otwartego dostępu BPP.",
        ),
        _wiersz_slow_kluczowych(rekord, p.keywords),
        *_wiersze_streszczen(rekord, p),
    ]
    return [w for w in kandydaci if w is not None]


def zastosuj(rekord, wiersze, wybrane):
    """Przenieś do ``rekord`` pola wskazane w ``wybrane`` (wartości pól
    wyboru z formularza: ``klucz:token``).

    Zwraca ``(przeniesione, pominiete)`` — listy wierszy. Pominięte to pola,
    których w międzyczasie nie da się już przenieść albo których wartość
    w źródle zmieniła się od podglądu. Zapisuje rekord, gdy coś przeniesiono.
    """
    po_kluczu = {w.klucz: w for w in wiersze}
    przeniesione, pominiete = [], []
    for wybor in wybrane:
        klucz, _, token = str(wybor).partition(":")
        wiersz = po_kluczu.get(klucz)
        if wiersz is None:
            continue
        if not wiersz.mozna_przeniesc or wiersz.token != token:
            pominiete.append(wiersz)
            continue
        przeniesione.append(wiersz)
    if not przeniesione:
        return przeniesione, pominiete
    for wiersz in przeniesione:
        if not wiersz.po_zapisie:
            wiersz.zastosuj(rekord)
    rekord.save()
    for wiersz in przeniesione:
        if wiersz.po_zapisie:
            wiersz.zastosuj(rekord)
    return przeniesione, pominiete
