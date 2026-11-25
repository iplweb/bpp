"""Jeden przycisk „Pobierz z PBN” przy polu „Odpowiednik w PBN” (FD#515).

Redaktor nie wybiera już, WEDŁUG CZEGO szukać odpowiednika (osobne „Pobierz
po DOI” i „Pobierz po ISBN”) — klika jeden przycisk, a system sam próbuje
kolejno wszystkich identyfikatorów rekordu.

Moduł zawiera:

* ``znajdz_odpowiednik_publikacji`` — wspólną logikę dla przycisku
  w formularzu i dla akcji grupowej (FD#516),
* widoki JSON dla przycisku w edycji: publikacji, autora (FD#519), źródła
  i wydawcy.

Widoki NICZEGO nie zapisują — zwracają propozycję, którą przeglądarka wpisuje
w pole formularza; zapis następuje dopiero, gdy redaktor zapisze rekord.
"""

import logging
import re
import sys
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import requests
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.views.generic.base import View
from pbn_client.const import DELETED

from bpp.models import Autor, Uczelnia
from bpp.views.api.pbn_get_by_parameter import (
    MAX_KANDYDATOW,
    SzukaczDOI,
    SzukaczISBN,
    bez_usunietych,
)
from bpp.zglaszanie_bledow import capture_exception
from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
    WillNotExportError,
)
from pbn_api.models import Journal, Publication, Publisher

logger = logging.getLogger(__name__)

#: Odpowiednik wskazany jednoznacznie — można go wpisać bez pytania.
PEWNY = "pewny"
#: Są kandydaci, ale wybrać musi człowiek.
DO_WYBORU = "do_wyboru"
#: Sprawdzono identyfikatory, nic nie znaleziono.
BRAK = "brak"
#: Rekord nie ma żadnego identyfikatora, po którym da się szukać.
PUSTE = "puste"

KOMUNIKAT_PUSTE_PUBLIKACJA = (
    "Uzupełnij DOI, adres WWW lub ISBN, żeby wyszukać odpowiednik w PBN."
)
KOMUNIKAT_PRACE_SERWISOWE = "W PBN trwają teraz prace serwisowe — spróbuj później."
KOMUNIKAT_AUTORYZACJA = (
    "Sprawdzono tylko lokalną kopię danych z PBN. Żeby przeszukać także "
    "serwer PBN, zaloguj się do PBN (menu PBN → autoryzuj) i spróbuj ponownie."
)

PODPOWIEDZ_WYBIERZ_CHARAKTER = (
    "Wybierz „Charakter formalny”, żeby BPP mogło samo wstawić pasujący "
    "rekord — bez niego nie wiadomo, czy praca jest książką, czy rozdziałem."
)
PODPOWIEDZ_INNY_CHARAKTER = (
    "BPP nie wstawia rekordu samo, bo charakter formalny tej pracy nie mówi, "
    "czy to książka, czy rozdział, więc nie da się potwierdzić rodzaju "
    "rekordu w PBN. Wybierz rekord ręcznie."
)

#: Wyjątki oznaczające „nie da się odpytać serwera PBN w imieniu użytkownika”.
BRAK_AUTORYZACJI = (WillNotExportError, NeedsPBNAuthorisationException)

#: Błędy połączenia z serwerem PBN (serwer leży, przekroczony czas, 5xx…).
BLEDY_POLACZENIA = (
    HttpException,
    PraceSerwisoweException,
    AccessDeniedException,
    requests.RequestException,
)

KOMUNIKAT_NIEDOSTEPNY = (
    "Serwer PBN nie odpowiada — sprawdzono tylko lokalną kopię danych z PBN. "
    "Spróbuj ponownie za chwilę."
)

#: Czas oczekiwania (połączenie, odpowiedź) na serwer PBN, w sekundach. Dużo
#: krótszy niż domyślny klienta PBN — redaktor czeka przy formularzu.
TIMEOUT_PBN = (5, 20)

#: Łączny limit czasu jednego wyszukiwania na serwerze PBN (zapytanie
#: i dociąganie szczegółów znalezionych rekordów), w sekundach.
LIMIT_LACZNY_PBN = 45

#: Rodzaj rekordu BPP → dopuszczalne rodzaje rekordu w PBN.
ZGODNE_RODZAJE = {
    "ARTICLE": {"ARTICLE"},
    "BOOK": {"BOOK", "EDITED_BOOK"},
    "CHAPTER": {"CHAPTER"},
}

_NIE_ALNUM = re.compile(r"[\W_]+")


def _norm_tytul(tytul):
    return _NIE_ALNUM.sub("", str(tytul or "")).casefold()


def normalizuj_www(url) -> str:
    """Adres WWW bez protokołu i końcowego ``/`` — do porównania z adresem
    publikacji zapisanym w PBN."""
    adres = str(url or "").strip()
    for prefiks in ("https://", "http://"):
        if adres.lower().startswith(prefiks):
            adres = adres[len(prefiks) :]
            break
    return adres.rstrip("/")


class SzukaczWWW:
    """Szukanie po adresie WWW — wyłącznie w lokalnej kopii danych z PBN
    (API PBN nie pozwala szukać publikacji po adresie)."""

    nazwa_identyfikatora = "adres WWW"

    def formy(self, value):
        adres = normalizuj_www(value)
        # Sam adres domeny („wydawnictwo.pl”) to strona wydawcy, nie pracy.
        if "/" not in adres and "?" not in adres:
            return []
        return [adres]

    def szukaj_lokalnie(self, value):
        formy = self.formy(value)
        if not formy:
            return []
        adres = formy[0].lower()
        warianty = [
            prefiks + adres + koncowka
            for prefiks in ("https://", "http://", "")
            for koncowka in ("", "/")
        ]
        return list(
            Publication.objects.annotate(_adres=Lower("publicUri"))
            .filter(_adres__in=warianty)
            .exclude(status=DELETED)
            .values_list("pk", flat=True)[: MAX_KANDYDATOW * 2]
        )

    def szukaj_w_pbn(self, client, value):
        return []

    def zapewnij_lokalnie(self, client, uidy):
        return


SZUKACZ_DOI = SzukaczDOI()
SZUKACZ_ISBN = SzukaczISBN()
SZUKACZ_WWW = SzukaczWWW()


@dataclass
class Odpowiednik:
    """Wynik szukania odpowiednika publikacji w PBN."""

    status: str = PUSTE
    #: Jedyny UID (``PEWNY``) albo kandydaci do wyboru (``DO_WYBORU``).
    uidy: list = field(default_factory=list)
    #: Po czym znaleziono — np. „DOI 10.1/x”.
    po_czym: str = ""
    #: Wszystkie sprawdzone identyfikatory, w kolejności prób.
    sprawdzono: list = field(default_factory=list)
    #: Powód, dla którego nie odpytano serwera PBN (sprawdzono tylko lokalnie).
    bez_serwera: str = ""
    #: Jedyną przeszkodą dla automatu był NIEUSTALONY rodzaj rekordu BPP —
    #: gdyby był znany (i zgodny z PBN), rekord zostałby wskazany na pewno.
    tylko_brak_rodzaju: bool = False

    @property
    def uid(self):
        return self.uidy[0] if self.status == PEWNY and self.uidy else None

    @property
    def komunikat(self):
        if self.status == PUSTE:
            return KOMUNIKAT_PUSTE_PUBLIKACJA
        sprawdzono = ", ".join(self.sprawdzono)
        if self.status == BRAK:
            return (
                f"Nie udało się znaleźć odpowiednika w PBN (sprawdzono: {sprawdzono})."
            )
        if self.status == PEWNY:
            return f"Znaleziono po: {self.po_czym}."
        return (
            f"Po: {self.po_czym} znaleziono w PBN rekordy, których nie da się "
            "przypisać automatycznie — wybierz właściwy."
        )


def rodzaj_rekordu(charakter_ogolny="", ma_nadrzedne=False, model=None):
    """Rodzaj rekordu BPP w kategoriach PBN (``ARTICLE`` / ``BOOK`` /
    ``CHAPTER``) albo ``""``, gdy nie da się go ustalić."""
    from bpp import const

    if ma_nadrzedne or charakter_ogolny == const.CHARAKTER_OGOLNY_ROZDZIAL:
        return "CHAPTER"
    if charakter_ogolny == const.CHARAKTER_OGOLNY_KSIAZKA:
        return "BOOK"
    if charakter_ogolny == const.CHARAKTER_OGOLNY_ARTYKUL or model == "ciagle":
        return "ARTICLE"
    return ""


def _zgodnosc_rodzaju(rodzaj, publikacja):
    """``True``/``False``, gdy rodzaje da się porównać; ``None``, gdy
    któregoś nie znamy."""
    typ = publikacja.type()
    if not rodzaj or not typ or rodzaj not in ZGODNE_RODZAJE:
        return None
    return typ in ZGODNE_RODZAJE[rodzaj]


def _pewne_i_reszta(szukacz, uidy, tytul, rodzaj):
    """Podziel ``uidy`` na rekordy, które wolno przypisać bez pytania,
    i pozostałe (kandydatów do wyboru).

    Pewny jest wyłącznie rekord, którego rodzaj w PBN POTWIERDZA rodzaj
    rekordu BPP (książka / rozdział / artykuł) i który dodatkowo ma zgodny
    tytuł — albo został znaleziony po DOI jako jedyny (tytuły w PBN bywają
    zapisane inaczej). Rodzaj sprzeczny albo nieustalony po którejkolwiek
    stronie = do ręcznego wyboru: rozdział dziedziczy ISBN książki, bywa
    zatytułowany jak tom i zdarza mu się mieć wpisany DOI książki.
    """
    publikacje = Publication.objects.in_bulk(uidy)
    uidy = [uid for uid in uidy if uid in publikacje]
    wzorzec = _norm_tytul(tytul)
    pewne = []
    zgodne_tytulem = []
    for uid in uidy:
        zgodny_tytul = bool(wzorzec) and _norm_tytul(publikacje[uid].title) == wzorzec
        if zgodny_tytul:
            zgodne_tytulem.append(uid)
        if _zgodnosc_rodzaju(rodzaj, publikacje[uid]) is not True:
            # Rodzaj sprzeczny ALBO nieustalony — bez potwierdzonej
            # zgodności nie ma automatu.
            continue
        if zgodny_tytul or (szukacz is SZUKACZ_DOI and len(uidy) == 1):
            pewne.append(uid)
    # Na liście do wyboru najpierw rekordy o zgodnym tytule.
    reszta = [u for u in zgodne_tytulem if u not in pewne]
    reszta += [u for u in uidy if u not in pewne and u not in reszta]
    return pewne, reszta


def _inne_zapisy(szukacz, wartosc):
    """Dopisek z pozostałymi zapisami identyfikatora, o które pytamy PBN
    (ISBN-10/13, z myślnikami i bez; DOI małymi literami)."""
    if szukacz is SZUKACZ_WWW:
        return ""
    inne = [forma for forma in szukacz.formy(wartosc) if forma != wartosc]
    return f" (także: {', '.join(inne)})" if inne else ""


def _bez_ponowien(klient, timeout):
    """Ustaw TEMU klientowi krótki czas oczekiwania i jedną próbę GET.

    Domyślny transport ponawia GET 15 razy z przerwami 1–5 s przy czasie
    oczekiwania (30, 120) — przy niedostępnym PBN to minuty. Zmiana dotyczy
    wyłącznie tego obiektu klienta (tworzonego na jedno żądanie/zlecenie),
    nie globalnego zachowania klienta PBN w innych modułach.
    """
    transport = getattr(klient, "transport", None)
    if transport is None or not hasattr(transport, "_make_get_request_with_retry"):
        return  # atrapa transportu w testach
    transport.timeout = timeout

    def jedna_proba(url, headers, max_retries=1):
        termin = getattr(transport, "termin_bpp", None)
        if termin is not None and time.monotonic() > termin:
            # Łączny limit jednego wyszukiwania (wyszukanie + dociąganie
            # szczegółów kilku rekordów) — nie zaczynamy kolejnego żądania.
            raise requests.Timeout("Przekroczono łączny limit czasu zapytań do PBN")
        return requests.get(
            transport.base_url + url, headers=headers, timeout=transport.timeout
        )

    transport._make_get_request_with_retry = jedna_proba


def _pewny_przy_znanym_rodzaju(szukacz, uidy, tytul):
    """Czy przy którymkolwiek rodzaju rekordu BPP dokładnie jeden z ``uidy``
    byłby pewny — tzn. czy automat zatrzymał się WYŁĄCZNIE na tym, że
    rodzaju pracy nie da się ustalić."""
    return any(
        len(_pewne_i_reszta(szukacz, uidy, tytul, rodzaj)[0]) == 1
        for rodzaj in ZGODNE_RODZAJE
    )


class SerwerPBN:
    """Leniwy dostęp do serwera PBN w imieniu użytkownika.

    Klient powstaje dopiero przy pierwszym zapytaniu (trafienie lokalne nie
    wymaga ani konfiguracji, ani tokena) i dostaje krótki czas oczekiwania
    bez pętli ponowień. Po odmowie autoryzacji obiekt milknie — kolejne
    zapytania nie idą już w sieć, a ``powod`` mówi dlaczego.

    ``lagodnie=True`` (przycisk w formularzu): błąd połączenia też wycisza
    serwer — wynik powstaje z lokalnej kopii, z uwagą dla redaktora.
    ``lagodnie=False`` (akcja grupowa): błąd połączenia jest propagowany,
    żeby trafił do raportu przy konkretnym rekordzie.
    """

    def __init__(
        self,
        fabryka=None,
        *,
        lagodnie=False,
        timeout=TIMEOUT_PBN,
        limit_laczny=LIMIT_LACZNY_PBN,
    ):
        self._fabryka = fabryka
        self._klient = None
        self._ustalony = False
        self._lagodnie = lagodnie
        self._timeout = timeout
        self._limit_laczny = limit_laczny
        self.powod = ""

    def klient(self):
        if not self._ustalony:
            self._ustalony = True
            if self._fabryka is not None:
                try:
                    self._klient = self._fabryka()
                except (*BRAK_AUTORYZACJI, ImproperlyConfigured):
                    # Brak tokena użytkownika albo nieskonfigurowana
                    # integracja — zostaje lokalna kopia danych.
                    self.powod = KOMUNIKAT_AUTORYZACJA
                else:
                    _bez_ponowien(self._klient, self._timeout)
        return self._klient

    def wylacz(self, powod=KOMUNIKAT_NIEDOSTEPNY):
        """Przestań odpytywać serwer PBN (zostaje lokalna kopia)."""
        self._ustalony = True
        self._klient = None
        self.powod = powod

    def wykonaj(self, funkcja, domyslnie=None):
        """Wywołaj ``funkcja(klient)``; bez klienta albo po odmowie
        autoryzacji zwróć ``domyslnie``."""
        klient = self.klient()
        if klient is None:
            return domyslnie
        transport = getattr(klient, "transport", None)
        if transport is not None:
            transport.termin_bpp = time.monotonic() + self._limit_laczny
        try:
            return funkcja(klient)
        except BRAK_AUTORYZACJI:
            # Token użytkownika wygasł — zostaje lokalna kopia danych.
            self.wylacz(KOMUNIKAT_AUTORYZACJA)
            return domyslnie
        except BLEDY_POLACZENIA as e:
            if not self._lagodnie:
                raise
            logger.warning("Serwer PBN niedostępny: %r", e)
            self.wylacz()
            return domyslnie


def _szukaj_na_serwerze(serwer, szukacz, wartosc):
    def funkcja(klient):
        uidy = szukacz.szukaj_w_pbn(klient, wartosc)
        szukacz.zapewnij_lokalnie(klient, uidy)
        # Rekord usunięty w PBN nie może zostać odpowiednikiem.
        return bez_usunietych(uidy)

    return serwer.wykonaj(funkcja, [])


def znajdz_odpowiednik_publikacji(
    *,
    doi="",
    www="",
    public_www="",
    isbn="",
    e_isbn="",
    tytul="",
    rodzaj="",
    klient=None,
) -> Odpowiednik:
    """Znajdź w PBN odpowiednik publikacji, próbując kolejno jej
    identyfikatorów: DOI → adres WWW → publiczny adres WWW → ISBN → e-ISBN.

    Każdy identyfikator jest szukany najpierw lokalnie (kopia danych z PBN
    i rekordy BPP, które mają już odpowiednik), a gdy lokalnie nic nie ma —
    na serwerze PBN (DOI i ISBN; po adresie WWW serwer PBN szukać nie
    pozwala). ``klient`` to bezargumentowa funkcja zwracająca klienta PBN
    albo gotowy ``SerwerPBN``; ``None`` = tylko lokalnie.

    Wynik jest ``PEWNY`` tylko wtedy, gdy dokładnie jeden znaleziony rekord
    ma rodzaj w PBN zgodny z ``rodzaj`` rekordu BPP (``ARTICLE`` / ``BOOK``
    / ``CHAPTER``) ORAZ:

    * ma ten sam tytuł, albo
    * został znaleziony po DOI jako jedyny.

    Bez potwierdzonej zgodności rodzaju (sprzeczny albo nieznany) wynik
    jest zawsze ``DO_WYBORU``. Rekordy usunięte w PBN są pomijane.

    W pozostałych przypadkach znalezione rekordy wracają jako ``DO_WYBORU``.
    Funkcja niczego nie wiąże.
    """
    proby = [
        (SZUKACZ_DOI, doi),
        (SZUKACZ_WWW, www),
        (SZUKACZ_WWW, public_www),
        (SZUKACZ_ISBN, isbn),
        (SZUKACZ_ISBN, e_isbn),
    ]
    serwer = klient if isinstance(klient, SerwerPBN) else SerwerPBN(klient)
    widziane = set()
    wynik = Odpowiednik()
    do_wyboru = None

    for szukacz, wartosc in proby:
        wartosc = str(wartosc or "").strip()[:1024]
        klucz = (szukacz.nazwa_identyfikatora, wartosc.lower())
        if not szukacz.formy(wartosc) or klucz in widziane:
            continue
        widziane.add(klucz)
        opis = f"{szukacz.nazwa_identyfikatora} {wartosc}"
        wynik.sprawdzono.append(opis + _inne_zapisy(szukacz, wartosc))

        # Lokalnie bierzemy PEŁNY wynik i dopiero na nim zawężamy po tytule.
        uidy = szukacz.szukaj_lokalnie(wartosc)
        pewne, reszta = _pewne_i_reszta(szukacz, uidy, tytul, rodzaj)
        if not pewne and (not uidy or _norm_tytul(tytul)):
            # Lokalnie nic albo nic o tym tytule (np. w kopii są tylko
            # rozdziały, a szukamy książki) — dopytaj serwer PBN.
            uidy = list(
                dict.fromkeys(uidy + _szukaj_na_serwerze(serwer, szukacz, wartosc))
            )
            pewne, reszta = _pewne_i_reszta(szukacz, uidy, tytul, rodzaj)
        wynik.bez_serwera = serwer.powod
        if len(pewne) == 1:
            wynik.status, wynik.uidy, wynik.po_czym = PEWNY, pewne, opis
            return wynik
        if (pewne or reszta) and do_wyboru is None:
            # Zgodne tytułem na początek; obcinamy dopiero listę do pokazania.
            do_wyboru = ((pewne + reszta)[:MAX_KANDYDATOW], opis)
            wynik.tylko_brak_rodzaju = not rodzaj and _pewny_przy_znanym_rodzaju(
                szukacz, uidy, tytul
            )

    if do_wyboru is not None:
        wynik.status = DO_WYBORU
        wynik.uidy, wynik.po_czym = do_wyboru
    elif wynik.sprawdzono:
        wynik.status = BRAK
    return wynik


# --- Widoki dla przycisku w formularzu --------------------------------------


class PobierzZPBNBase(LoginRequiredMixin, View):
    """Wspólna obsługa żądania przycisku „Pobierz z PBN”: uprawnienia,
    klient PBN i zamiana błędów PBN na czytelny komunikat."""

    #: Uprawnienia, z których co najmniej jedno musi mieć użytkownik —
    #: te same, których panel redagowania wymaga do zmiany rekordu.
    wymagane_uprawnienia = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (
            request.user.is_active
            and request.user.is_staff
            and any(request.user.has_perm(u) for u in self.wymagane_uprawnienia)
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def pole(self, nazwa):
        return self.request.POST.get(nazwa, "").strip()[:1024]

    def uczelnia(self):
        return Uczelnia.objects.get_for_request(self.request)

    def klient(self):
        """Dostęp do serwera PBN w imieniu zalogowanego użytkownika: leniwy
        (lokalne trafienie nie wymaga ani konfiguracji, ani tokena), z krótkim
        czasem oczekiwania; niedostępny PBN nie jest błędem — wynik powstaje
        z lokalnej kopii, z uwagą."""
        uczelnia = self.uczelnia()
        if uczelnia is None:
            return SerwerPBN(None)
        token = getattr(self.request.user, "pbn_token", "")
        return SerwerPBN(lambda: uczelnia.pbn_client(token), lagodnie=True)

    def szukaj(self) -> dict:
        raise NotImplementedError

    def post(self, request, *args, **kw):
        try:
            return JsonResponse(self.szukaj())
        except PermissionDenied:
            raise
        except PraceSerwisoweException:
            return JsonResponse({"error": KOMUNIKAT_PRACE_SERWISOWE})
        except NeedsPBNAuthorisationException:
            return JsonResponse(
                {
                    "error": "Zaloguj się do PBN (menu PBN → autoryzuj) "
                    "i spróbuj ponownie."
                }
            )
        except HttpException as e:
            capture_exception(sys.exc_info())
            return JsonResponse(
                {
                    "error": f"Serwer PBN odpowiedział błędem ({e.status_code}). "
                    "Spróbuj ponownie za chwilę."
                }
            )
        except Exception:
            # Nieznany błąd nie może zostawić redaktora z martwym
            # przyciskiem: zgłoszenie do monitoringu + ogólny komunikat.
            capture_exception(sys.exc_info())
            return JsonResponse(
                {
                    "error": "Nieznany błąd po stronie serwera przy "
                    "odpytywaniu PBN. Spróbuj ponownie za chwilę."
                }
            )


def _odpowiedz(status, komunikat, kandydaci, uwaga=""):
    odp = {
        "status": status,
        "komunikat": komunikat,
        "kandydaci": kandydaci,
        "uwaga": uwaga,
    }
    if status == PEWNY and kandydaci:
        odp["id"] = kandydaci[0]["id"]
    return odp


class PobierzOdpowiednikPublikacjiView(PobierzZPBNBase):
    """Odpowiednik wydawnictwa ciągłego / zwartego."""

    wymagane_uprawnienia = (
        "bpp.change_wydawnictwo_ciagle",
        "bpp.change_wydawnictwo_zwarte",
    )

    def rodzaj(self):
        """Rodzaj rekordu z formularza: po charakterze formalnym i po tym,
        czy wskazano wydawnictwo nadrzędne."""
        from bpp.models import Charakter_Formalny

        charakter = self.pole("charakter_formalny")
        ogolny = ""
        if charakter.isdigit():
            ogolny = (
                Charakter_Formalny.objects.filter(pk=int(charakter))
                .values_list("charakter_ogolny", flat=True)
                .first()
                or ""
            )
        return rodzaj_rekordu(
            ogolny,
            bool(self.pole("wydawnictwo_nadrzedne")),
            model=self.pole("model") or None,
        )

    def szukaj(self):
        wynik = znajdz_odpowiednik_publikacji(
            doi=self.pole("doi"),
            www=self.pole("www"),
            public_www=self.pole("public_www"),
            isbn=self.pole("isbn"),
            e_isbn=self.pole("e_isbn"),
            tytul=self.pole("tytul_oryginalny"),
            rodzaj=self.rodzaj(),
            klient=self.klient(),
        )
        publikacje = Publication.objects.in_bulk(wynik.uidy)
        uidy = [uid for uid in wynik.uidy if uid in publikacje]
        rok = self.pole("rok")
        if wynik.status == DO_WYBORU and rok.isdigit():
            # Rekordy z rokiem z formularza na początek; poza tym kolejność
            # wyszukiwania (``sorted`` jest stabilne). Rok niczego nie zawęża.
            uidy = sorted(uidy, key=lambda uid: publikacje[uid].year != int(rok))
        kandydaci = [
            {
                "id": uid,
                "etykieta": str(publikacje[uid]),
                "opis": " · ".join(
                    str(x)
                    for x in (
                        publikacje[uid].title,
                        publikacje[uid].year,
                        publikacje[uid].type(),
                    )
                    if x
                ),
                "typ": publikacje[uid].type(),
                "rok": publikacje[uid].year,
            }
            for uid in uidy
        ]
        uwaga = wynik.bez_serwera if wynik.status in (BRAK, DO_WYBORU) else ""
        odp = _odpowiedz(wynik.status, wynik.komunikat, kandydaci, uwaga)
        if wynik.tylko_brak_rodzaju:
            odp["podpowiedz"] = (
                PODPOWIEDZ_INNY_CHARAKTER
                if self.pole("charakter_formalny")
                else PODPOWIEDZ_WYBIERZ_CHARAKTER
            )
        return odp


class PobierzOdpowiednikAutoraView(PobierzZPBNBase):
    """Odpowiednik autora (FD#519): po ORCID, a gdy go brak — po imieniu
    i nazwisku oraz po autorach prac powiązanych z PBN."""

    wymagane_uprawnienia = ("bpp.change_autor",)

    def autor(self):
        """Autor z formularza — z TEGO SAMEGO zbioru, który panel
        redagowania pokazuje temu użytkownikowi (zakres uczelni w instalacji
        wielouczelnianej). Autor spoza zakresu = odmowa: widok ujawniałby
        kandydatów i liczbę jego prac."""
        from django.contrib import admin

        pk = self.pole("pk")
        if not pk.isdigit():
            return Autor()
        autor = (
            admin.site._registry[Autor]
            .get_queryset(self.request)
            .filter(pk=int(pk))
            .first()
        )
        if autor is None:
            raise PermissionDenied
        return autor

    def szukaj(self):
        from pbn_integrator.utils.odpowiednik_autora import szukaj_odpowiednika_autora

        autor = self.autor()
        # Wartości z formularza — redaktor mógł właśnie wpisać ORCID.
        autor.imiona = self.pole("imiona")
        autor.nazwisko = self.pole("nazwisko")
        autor.poprzednie_nazwiska = self.pole("poprzednie_nazwiska")
        autor.orcid = self.pole("orcid") or None

        if not (autor.orcid or (autor.imiona and autor.nazwisko)):
            return _odpowiedz(
                PUSTE,
                "Uzupełnij ORCID albo imię i nazwisko, żeby wyszukać "
                "odpowiednik autora w PBN.",
                [],
            )

        wynik = szukaj_odpowiednika_autora(
            autor, uczelnia=self.uczelnia(), klient=self.klient()
        )
        return _odpowiedz(wynik.status, wynik.komunikat, wynik.kandydaci, wynik.uwaga)


class _LokalnySlownikView(PobierzZPBNBase):
    """Źródła i wydawcy: szukamy wyłącznie w lokalnej kopii słowników PBN
    (pobieranych w całości przy integracji)."""

    komunikat_puste = ""

    def kandydaci(self) -> list | None:
        """Lista obiektów PBN albo ``None``, gdy nie ma po czym szukać."""
        raise NotImplementedError

    def szukaj(self):
        obiekty = self.kandydaci()
        if obiekty is None:
            return _odpowiedz(PUSTE, self.komunikat_puste, [])
        # Pozycje z wykazu ministerialnego na początek.
        obiekty = sorted(obiekty, key=lambda o: o.mniswId is None)
        kandydaci = [
            {
                "id": o.pk,
                "etykieta": str(o),
                "opis": str(o),
                "oficjalny": o.mniswId is not None,
            }
            for o in obiekty
        ]
        if not kandydaci:
            return _odpowiedz(
                BRAK,
                "Nie udało się znaleźć odpowiednika w lokalnej kopii danych z PBN.",
                [],
            )
        if len(kandydaci) == 1:
            return _odpowiedz(PEWNY, "Znaleziono odpowiednik w PBN.", kandydaci)
        return _odpowiedz(
            DO_WYBORU,
            "W PBN pasuje kilka pozycji — wybierz właściwą.",
            kandydaci,
        )


class PobierzOdpowiednikZrodlaView(_LokalnySlownikView):
    """Odpowiednik źródła: po ISSN, e-ISSN albo dokładnej nazwie."""

    wymagane_uprawnienia = ("bpp.change_zrodlo",)
    komunikat_puste = (
        "Uzupełnij ISSN, e-ISSN albo nazwę, żeby wyszukać odpowiednik źródła w PBN."
    )

    def kandydaci(self):
        from pbn_integrator.utils.journals import _zrodlo_query

        zrodlo = SimpleNamespace(
            issn=self.pole("issn"),
            e_issn=self.pole("e_issn"),
            nazwa=self.pole("nazwa"),
        )
        if not (zrodlo.issn or zrodlo.e_issn or zrodlo.nazwa):
            return None
        return list(
            Journal.objects.filter(_zrodlo_query(zrodlo)).exclude(status=DELETED)[
                :MAX_KANDYDATOW
            ]
        )


class PobierzOdpowiednikWydawcyView(_LokalnySlownikView):
    """Odpowiednik wydawcy: po dokładnej nazwie (bez wielkości liter)."""

    wymagane_uprawnienia = ("bpp.change_wydawca",)
    komunikat_puste = "Uzupełnij nazwę, żeby wyszukać odpowiednik wydawcy w PBN."

    def kandydaci(self):
        nazwa = self.pole("nazwa")
        if not nazwa:
            return None
        return list(
            Publisher.objects.filter(publisherName__iexact=nazwa).exclude(
                status=DELETED
            )[:MAX_KANDYDATOW]
        )


__all__ = [
    "BRAK",
    "DO_WYBORU",
    "PEWNY",
    "PUSTE",
    "Odpowiednik",
    "PobierzOdpowiednikAutoraView",
    "PobierzOdpowiednikPublikacjiView",
    "PobierzOdpowiednikWydawcyView",
    "PobierzOdpowiednikZrodlaView",
    "SerwerPBN",
    "rodzaj_rekordu",
    "znajdz_odpowiednik_publikacji",
]
