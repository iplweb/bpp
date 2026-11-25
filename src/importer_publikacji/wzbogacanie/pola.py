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
    wartosc_alternatywy=None,
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
    pole_alt = _pole(rekord, alternatywa) if alternatywa else None
    if not z:
        # Wartość z BPP źródło podaje w polu bliźniaczym (np. e-ISSN z BPP
        # to w źródle ISSN) — to nie jest brak.
        if pole_alt is not None and normalizuj(wartosc_alternatywy) == b:
            wiersz.uwaga = f"W źródle ta wartość jest w polu „{_etykieta(pole_alt)}”."
            return wiersz
        wiersz.status = BRAK_W_ZRODLE
        return wiersz
    if z == b:
        return wiersz
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


#: Limit długości jednego słowa kluczowego (``taggit.Tag.name``).
MAKSYMALNA_DLUGOSC_SLOWA = 100


def _slowa(lista):
    return {reguly.odstepy(s).casefold() for s in lista if reguly.odstepy(s)}


def _wiersz_slow_kluczowych(rekord, slowa):
    if not hasattr(rekord, "slowa_kluczowe"):
        return None
    slowa = [reguly.odstepy(s) for s in slowa or [] if reguly.odstepy(s)]
    # ``.all()``, nie ``.names()`` — korzysta z ``prefetch_related`` (komparator
    # porównuje tysiące prac). Słowa angielskie rekord trzyma w osobnym polu;
    # źródła podają wszystkie języki razem.
    obecne = sorted(
        {
            *(tag.name for tag in rekord.slowa_kluczowe.all()),
            *(getattr(rekord, "slowa_kluczowe_eng", None) or ()),
        },
        key=str.casefold,
    )
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

    za_dlugie = [x for x in slowa if len(x) > MAKSYMALNA_DLUGOSC_SLOWA]
    if za_dlugie:
        wiersz.uwaga = (
            "Tych słów kluczowych nie da się zapisać w BPP — najdłuższe ma "
            f"ponad {MAKSYMALNA_DLUGOSC_SLOWA} znaków."
        )
        return wiersz

    def zastosuj(r, slowa=slowa):
        r.slowa_kluczowe.set(slowa)

    wiersz.zastosuj = zastosuj
    return wiersz


def _wiersze_streszczen(rekord, publikacja, znajdz_jezyk):
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
                jezyk = znajdz_jezyk(kod_jezyka or _detect_language(tekst))
                r.streszczenia.create(streszczenie=tekst, jezyk_streszczenia=jezyk)

            wiersz.zastosuj = zastosuj
        yield wiersz


def _prosty(nazwa, wartosc, blizniacze=None, **opcje):
    """``blizniacze`` — wartość ze źródła dla pola ``alternatywa``."""

    def wiersz(rekord, p, _jezyk):
        return _wiersz_prosty(
            rekord,
            nazwa,
            wartosc(p),
            wartosc_alternatywy=blizniacze(p) if blizniacze else None,
            **opcje,
        )

    return wiersz


#: Pola porównania w kolejności wyświetlania: nazwa → funkcja
#: ``(rekord, publikacja, znajdz_jezyk)`` zwracająca wiersz, listę wierszy
#: albo ``None`` (pole nie dotyczy rekordu / puste po obu stronach).
POLA = {
    "tytul_oryginalny": _prosty("tytul_oryginalny", lambda p: p.title),
    "tytul": _prosty(
        "tytul",
        lambda p: p.extra.get("original_title"),
        pomin_gdy_brak_w_zrodle=True,
    ),
    "rok": _prosty("rok", lambda p: p.year, normalizuj=reguly.rok, do_zapisu=int),
    "doi": _prosty("doi", lambda p: p.doi, normalizuj=reguly.doi, do_zapisu=reguly.doi),
    "tom": _prosty("tom", lambda p: p.volume),
    "nr_zeszytu": _prosty("nr_zeszytu", lambda p: p.issue),
    "strony": _prosty("strony", lambda p: p.pages, normalizuj=reguly.strony),
    "issn": _prosty(
        "issn",
        lambda p: p.issn,
        blizniacze=lambda p: p.e_issn,
        normalizuj=reguly.numer,
        alternatywa="e_issn",
    ),
    "e_issn": _prosty(
        "e_issn",
        lambda p: p.e_issn,
        blizniacze=lambda p: p.issn,
        normalizuj=reguly.numer,
        alternatywa="issn",
    ),
    "isbn": _prosty(
        "isbn",
        lambda p: p.isbn,
        blizniacze=lambda p: p.e_isbn,
        normalizuj=reguly.numer,
        alternatywa="e_isbn",
    ),
    "e_isbn": _prosty(
        "e_isbn",
        lambda p: p.e_isbn,
        blizniacze=lambda p: p.isbn,
        normalizuj=reguly.numer,
        alternatywa="isbn",
    ),
    "www": _prosty(
        "www",
        lambda p: p.url,
        normalizuj=reguly.adres,
        alternatywa="public_www",
        walidatory=(nie_zawiera_adresu_doi_org,),
    ),
    "jezyk": lambda rekord, p, jezyk: _wiersz_slownikowy(
        rekord,
        "jezyk",
        p.language,
        jezyk,
        "Tego języka nie ma w słowniku języków BPP (Dane systemowe → Języki).",
    ),
    "openaccess_licencja": lambda rekord, p, _jezyk: _wiersz_slownikowy(
        rekord,
        "openaccess_licencja",
        p.license_url,
        _znajdz_licencje,
        "Tej licencji nie ma w słowniku licencji otwartego dostępu BPP.",
    ),
    "slowa_kluczowe": lambda rekord, p, _jezyk: _wiersz_slow_kluczowych(
        rekord, p.keywords
    ),
    "streszczenie": lambda rekord, p, jezyk: list(
        _wiersze_streszczen(rekord, p, jezyk)
    ),
}


def porownaj(rekord, publikacja, pola=None, znajdz_jezyk=None) -> list[Wiersz]:
    """Wiersze porównania rekordu BPP z danymi ze źródła (``publikacja``).

    ``pola`` — nazwy z ``POLA`` (domyślnie wszystkie); liczone są tylko one.
    ``znajdz_jezyk`` — funkcja „kod języka → język BPP”; wołający, który
    porównuje wiele rekordów naraz, podaje wersję z pamięcią podręczną."""
    znajdz_jezyk = znajdz_jezyk or _znajdz_jezyk
    wiersze = []
    for nazwa in pola if pola is not None else POLA:
        wynik = POLA[nazwa](rekord, publikacja, znajdz_jezyk)
        if isinstance(wynik, list):
            wiersze.extend(wynik)
        elif wynik is not None:
            wiersze.append(wynik)
    return wiersze


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
