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
    #: Kolumny rekordu zmieniane przez ``zastosuj`` — tylko one są zapisywane.
    pola_rekordu: tuple = ()

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
        """Skrót obu wartości z podglądu — zatwierdzenie przenosi dokładnie
        to, co redaktor widział: jeśli w międzyczasie zmieniły się dane
        w źródle ALBO rekord (inny redaktor), pole jest pomijane."""
        return hashlib.sha1(
            f"{self.zrodlo}\x00{self.bpp}".encode(), usedforsecurity=False
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
    brak_sprawdza_alternatywe=False,
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
    if not z and not b and brak_sprawdza_alternatywe:
        return _brak_w_zrodle_z_alternatywy(rekord, pole, alternatywa, normalizuj)
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
    wiersz.pola_rekordu = (nazwa,)
    return wiersz


def _brak_w_zrodle_z_alternatywy(rekord, pole, alternatywa, normalizuj):
    """Źródło nie ma wartości, a pole główne w BPP jest puste: jeśli BPP ma
    wartość w polu alternatywnym (adres wyłącznie w polu wolnego dostępu),
    to także „brak w źródle” — inaczej pola nie ma po żadnej stronie."""
    zastepcza = getattr(rekord, alternatywa, "")
    if not normalizuj(zastepcza):
        return None
    return Wiersz(
        klucz=pole.name,
        etykieta=_etykieta(pole),
        status=BRAK_W_ZRODLE,
        bpp=reguly.odstepy(zastepcza),
        uwaga=(
            f"W BPP ta wartość jest w polu „{_etykieta(_pole(rekord, alternatywa))}”."
        ),
    )


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
    wiersz.pola_rekordu = (nazwa,)
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
#: Limit długości słowa w polu „Słowa kluczowe -- język angielski”.
MAKSYMALNA_DLUGOSC_SLOWA_ENG = 255


def _slowa(lista):
    return {reguly.odstepy(s).casefold() for s in lista if reguly.odstepy(s)}


def _czyste(slowa):
    """Słowa bez pustych i powtórzeń (bez względu na wielkość liter)."""
    wynik, widziane = [], set()
    for slowo in slowa or []:
        slowo = reguly.odstepy(slowo)
        if slowo and slowo.casefold() not in widziane:
            widziane.add(slowo.casefold())
            wynik.append(slowo)
    return wynik


def _wiersz_slow(klucz, etykieta, ze_zrodla, obecne, limit, dopisz):
    """Wiersz porównania zbioru słów kluczowych.

    Zgodne = te same słowa (kolejność i wielkość liter bez znaczenia).
    Przeniesienie DOPISUJE brakujące słowa (``dopisz(rekord, brakujace)``)
    — słów wpisanych tylko w BPP nie usuwa."""
    ze_zrodla = _czyste(ze_zrodla)
    obecne = sorted(_czyste(obecne), key=str.casefold)
    if not ze_zrodla and not obecne:
        return None
    wiersz = Wiersz(
        klucz=klucz,
        etykieta=etykieta,
        status=ZGODNE,
        zrodlo=", ".join(ze_zrodla) or PUSTE,
        bpp=", ".join(obecne) or PUSTE,
    )
    if not ze_zrodla:
        wiersz.status = BRAK_W_ZRODLE
        return wiersz
    if _slowa(ze_zrodla) == _slowa(obecne):
        return wiersz
    wiersz.status = ROZNE if obecne else BRAK_W_BPP
    brakujace = [x for x in ze_zrodla if x.casefold() not in _slowa(obecne)]
    if not brakujace:
        wiersz.uwaga = (
            "Rekord ma wszystkie słowa ze źródła i dodatkowe własne — nie ma "
            "czego przenosić."
        )
        return wiersz
    wiersz.zmiana = format_html("<ins>{}</ins>", ", ".join(brakujace))
    za_dlugie = [x for x in brakujace if len(x) > limit]
    if za_dlugie:
        wiersz.uwaga = (
            f"Tych słów nie da się zapisać w BPP — słowo kluczowe może mieć "
            f"najwyżej {limit} znaków, a w źródle jest dłuższe (zwykle kilka "
            "słów sklejonych w jedno). Wpisz je ręcznie w formularzu rekordu."
        )
        return wiersz
    if obecne:
        wiersz.uwaga = (
            "Przeniesienie dopisze brakujące słowa; słowa wpisane w BPP zostaną."
        )

    def zastosuj(r, brakujace=brakujace):
        dopisz(r, brakujace)

    wiersz.zastosuj = zastosuj
    return wiersz


def _tagi(rekord):
    # ``.all()``, nie ``.names()`` — korzysta z ``prefetch_related``
    # (komparator porównuje tysiące prac).
    return [tag.name for tag in rekord.slowa_kluczowe.all()]


def _dopisz_tagi(rekord, slowa):
    rekord.slowa_kluczowe.add(*slowa)


def _dopisz_slowa_eng(rekord, slowa):
    rekord.slowa_kluczowe_eng = [*(rekord.slowa_kluczowe_eng or []), *slowa]


def _wiersze_slow_kluczowych(rekord, publikacja):
    """Słowa kluczowe. Rekord trzyma je w dwóch polach: „Słowa kluczowe”
    (język główny) i „Słowa kluczowe -- język angielski”.

    Źródło z podziałem na języki (PBN): angielskie porównujemy i zapisujemy
    w polu angielskim, pozostałe w głównym — tak samo jak import z PBN.
    Źródło bez podziału (CrossRef): jedna lista porównywana ze wszystkimi
    słowami rekordu; brakujące trafiają do pola głównego."""
    if not hasattr(rekord, "slowa_kluczowe"):
        return
    ma_eng = hasattr(rekord, "slowa_kluczowe_eng")
    eng = list(rekord.slowa_kluczowe_eng or []) if ma_eng else []
    wg_jezyka = publikacja.extra.get("slowa_kluczowe_wg_jezyka")
    if wg_jezyka is None or not ma_eng:
        wiersz = _wiersz_slow(
            "slowa_kluczowe",
            "Słowa kluczowe",
            publikacja.keywords,
            [*_tagi(rekord), *eng],
            MAKSYMALNA_DLUGOSC_SLOWA,
            _dopisz_tagi,
        )
        if wiersz is not None:
            wiersz.po_zapisie = True
            yield wiersz
        return
    angielskie = [
        s for kod, slowa in wg_jezyka.items() if _angielski(kod) for s in slowa
    ]
    pozostale = [
        s for kod, slowa in wg_jezyka.items() if not _angielski(kod) for s in slowa
    ]
    wiersz = _wiersz_slow(
        "slowa_kluczowe",
        "Słowa kluczowe",
        pozostale,
        _tagi(rekord),
        MAKSYMALNA_DLUGOSC_SLOWA,
        _dopisz_tagi,
    )
    if wiersz is not None:
        wiersz.po_zapisie = True
        yield wiersz
    wiersz = _wiersz_slow(
        "slowa_kluczowe_eng",
        "Słowa kluczowe (język angielski)",
        angielskie,
        eng,
        MAKSYMALNA_DLUGOSC_SLOWA_ENG,
        _dopisz_slowa_eng,
    )
    if wiersz is not None:
        wiersz.pola_rekordu = ("slowa_kluczowe_eng",)
        yield wiersz


def _angielski(kod_jezyka):
    return str(kod_jezyka or "").lower() in ("eng", "en")


def _streszczenia_zrodla(publikacja):
    """Streszczenia ze źródła jako lista ``(tekst, kod języka albo None)``.
    PBN podaje je w podziale na języki — bierzemy wszystkie, nie pierwsze."""
    from ..views.publikacja import _build_abstracts_list

    wg_jezyka = publikacja.extra.get("streszczenia_wg_jezyka")
    if wg_jezyka is not None:
        pary = [(tekst, kod) for kod, tekst in wg_jezyka.items()]
    else:
        pary = [
            (a.get("text"), a.get("language"))
            for a in _build_abstracts_list(publikacja)
        ]
    return [(reguly.odstepy(t), kod) for t, kod in pary if reguly.tekst(t)]


class _StreszczeniaRekordu:
    """Streszczenia rekordu (tekst, id języka); każde dopasowane raz."""

    def __init__(self, rekord):
        self.wszystkie = [
            (s.streszczenie, s.jezyk_streszczenia_id)
            for s in rekord.streszczenia.all()
            if reguly.tekst(s.streszczenie)
        ]
        self.wolne = list(range(len(self.wszystkie)))

    def _wez(self, warunek):
        for nr in self.wolne:
            if warunek(*self.wszystkie[nr]):
                self.wolne.remove(nr)
                return self.wszystkie[nr][0]
        return None

    def o_tekscie(self, tekst):
        norm = reguly.tekst(tekst)
        return self._wez(lambda t, _j: reguly.tekst(t) == norm)

    def w_jezyku(self, jezyk, kod):
        """Streszczenie rekordu w języku streszczenia ze źródła. Źródło bez
        języków i jedno streszczenie w rekordzie — porównujemy je ze sobą."""
        if jezyk is not None:
            return self._wez(lambda _t, j: j == jezyk.pk)
        if kod is None and len(self.wszystkie) == 1:
            return self._wez(lambda _t, _j: True)
        return None

    def niedopasowane(self):
        return [self.wszystkie[nr][0] for nr in self.wolne]


def _wiersze_streszczen(rekord, publikacja, znajdz_jezyk):
    """Streszczenia jako pary język–tekst.

    Streszczenie ze źródła jest zgodne, gdy rekord ma streszczenie o tym
    samym tekście. Gdy nie ma: jeśli rekord ma streszczenie W TYM SAMYM
    JĘZYKU — „różne” (porównanie z nim), inaczej „brak w BPP” (rekord może
    mieć streszczenia w innych językach — to nie zastępuje brakującego).
    Streszczenia rekordu bez odpowiednika w źródle to „brak w źródle”.
    Przeniesienie DODAJE streszczenie — istniejących nie rusza."""
    if not hasattr(rekord, "streszczenia"):
        return
    obecne = _StreszczeniaRekordu(rekord)
    for nr, (tekst, kod) in enumerate(_streszczenia_zrodla(publikacja)):
        jezyk = znajdz_jezyk(kod) if kod else None
        yield _wiersz_streszczenia(nr, tekst, kod, jezyk, obecne, znajdz_jezyk)
    for nr, tekst in enumerate(obecne.niedopasowane()):
        yield Wiersz(
            klucz=f"streszczenie-bpp-{nr}",
            etykieta="Streszczenie",
            status=BRAK_W_ZRODLE,
            bpp=reguly.odstepy(tekst),
        )


def _wiersz_streszczenia(nr, tekst, kod, jezyk, obecne, znajdz_jezyk):
    from ..views.helpers import _detect_language

    nazwa_jezyka = str(jezyk) if jezyk is not None else (kod or "")
    wiersz = Wiersz(
        klucz=f"streszczenie-{nr}",
        etykieta=f"Streszczenie ({nazwa_jezyka})" if nazwa_jezyka else "Streszczenie",
        status=ZGODNE,
        zrodlo=tekst,
        bpp=tekst,
        po_zapisie=True,
    )
    if obecne.o_tekscie(tekst) is not None:
        return wiersz
    w_tym_jezyku = obecne.w_jezyku(jezyk, kod)
    wiersz.status = ROZNE if w_tym_jezyku is not None else BRAK_W_BPP
    wiersz.bpp = reguly.odstepy(w_tym_jezyku) if w_tym_jezyku is not None else PUSTE
    wiersz.zmiana = _zmiana(wiersz.status, wiersz.bpp, tekst)
    if obecne.wszystkie:
        wiersz.uwaga = "Przeniesienie doda kolejne streszczenie — istniejące zostaną."

    def zastosuj(r):
        jezyk_zapisu = jezyk
        if jezyk_zapisu is None:
            jezyk_zapisu = znajdz_jezyk(kod or _detect_language(tekst))
        r.streszczenia.create(streszczenie=tekst, jezyk_streszczenia=jezyk_zapisu)

    wiersz.zastosuj = zastosuj
    return wiersz


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
        brak_sprawdza_alternatywe=True,
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
    "slowa_kluczowe": lambda rekord, p, _jezyk: list(
        _wiersze_slow_kluczowych(rekord, p)
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
    obsluzone = set()
    for wybor in wybrane:
        klucz, _, token = str(wybor).partition(":")
        wiersz = po_kluczu.get(klucz)
        # Każde pole najwyżej raz — powtórzona wartość w formularzu nie może
        # np. dodać tego samego streszczenia dwa razy.
        if wiersz is None or klucz in obsluzone:
            continue
        obsluzone.add(klucz)
        if not wiersz.mozna_przeniesc or wiersz.token != token:
            pominiete.append(wiersz)
            continue
        przeniesione.append(wiersz)
    if not przeniesione:
        return przeniesione, pominiete
    for wiersz in przeniesione:
        if not wiersz.po_zapisie:
            wiersz.zastosuj(rekord)
    # Zapisujemy WYŁĄCZNIE kolumny wybranych pól (plus datę ostatniej
    # zmiany): pełny ``save()`` zapisałby cały wiersz i uruchomił porządki
    # na polach, których redaktor nie zaznaczył (np. czyszczenie adresów WWW
    # o niedozwolonym schemacie). Przy samych relacjach (słowa kluczowe,
    # streszczenia) zapis dotyka tylko daty ostatniej zmiany. Opis
    # bibliograficzny i pozostałe pola wyliczane odświeżają się jak zwykle —
    # zależą od wyzwalaczy w bazie, nie od pełnego zapisu.
    kolumny = {nazwa for wiersz in przeniesione for nazwa in wiersz.pola_rekordu}
    if _pole(rekord, "ostatnio_zmieniony") is not None:
        kolumny.add("ostatnio_zmieniony")
    rekord.save(update_fields=sorted(kolumny))
    for wiersz in przeniesione:
        if wiersz.po_zapisie:
            wiersz.zastosuj(rekord)
    return przeniesione, pominiete
