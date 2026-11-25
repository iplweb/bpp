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
from dataclasses import dataclass, field
from types import SimpleNamespace

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
)
from bpp.zglaszanie_bledow import capture_exception
from pbn_api.exceptions import (
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

#: Wyjątki oznaczające „nie da się odpytać serwera PBN w imieniu użytkownika”.
BRAK_AUTORYZACJI = (WillNotExportError, NeedsPBNAuthorisationException)

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


def _zawez_po_tytule(uidy, tytul):
    """UID-y rekordów PBN o tytule zgodnym z ``tytul`` (bez wielkości liter
    i znaków przestankowych)."""
    wzorzec = _norm_tytul(tytul)
    if not wzorzec:
        return []
    tytuly = dict(Publication.objects.filter(pk__in=uidy).values_list("pk", "title"))
    return [uid for uid in uidy if _norm_tytul(tytuly.get(uid)) == wzorzec]


def _inne_zapisy(szukacz, wartosc):
    """Dopisek z pozostałymi zapisami identyfikatora, o które pytamy PBN
    (ISBN-10/13, z myślnikami i bez; DOI małymi literami)."""
    if szukacz is SZUKACZ_WWW:
        return ""
    inne = [forma for forma in szukacz.formy(wartosc) if forma != wartosc]
    return f" (także: {', '.join(inne)})" if inne else ""


class SerwerPBN:
    """Leniwy dostęp do serwera PBN w imieniu użytkownika.

    Klient powstaje dopiero przy pierwszym zapytaniu (trafienie lokalne nie
    wymaga ani konfiguracji, ani tokena). Po odmowie autoryzacji obiekt
    milknie — kolejne zapytania nie idą już w sieć, a ``powod`` mówi
    dlaczego. Akcja grupowa używa jednego obiektu dla wszystkich rekordów.
    """

    def __init__(self, fabryka=None):
        self._fabryka = fabryka
        self._klient = None
        self._ustalony = False
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
        return self._klient

    def wykonaj(self, funkcja, domyslnie=None):
        """Wywołaj ``funkcja(klient)``; bez klienta albo po odmowie
        autoryzacji zwróć ``domyslnie``."""
        klient = self.klient()
        if klient is None:
            return domyslnie
        try:
            return funkcja(klient)
        except BRAK_AUTORYZACJI:
            # Token użytkownika wygasł — zostaje lokalna kopia danych.
            self._klient = None
            self.powod = KOMUNIKAT_AUTORYZACJA
            return domyslnie


def _szukaj_na_serwerze(serwer, szukacz, wartosc):
    def funkcja(klient):
        uidy = szukacz.szukaj_w_pbn(klient, wartosc)
        szukacz.zapewnij_lokalnie(klient, uidy)
        return uidy

    return serwer.wykonaj(funkcja, [])


def znajdz_odpowiednik_publikacji(
    *, doi="", www="", public_www="", isbn="", e_isbn="", tytul="", klient=None
) -> Odpowiednik:
    """Znajdź w PBN odpowiednik publikacji, próbując kolejno jej
    identyfikatorów: DOI → adres WWW → publiczny adres WWW → ISBN → e-ISBN.

    Każdy identyfikator jest szukany najpierw lokalnie (kopia danych z PBN
    i rekordy BPP, które mają już odpowiednik), a gdy lokalnie nic nie ma —
    na serwerze PBN (DOI i ISBN; po adresie WWW serwer PBN szukać nie
    pozwala). ``klient`` to bezargumentowa funkcja zwracająca klienta PBN
    albo gotowy ``SerwerPBN``; ``None`` = tylko lokalnie.

    Wynik jest ``PEWNY`` tylko wtedy, gdy:

    * DOI wskazuje dokładnie jeden rekord, albo
    * adres WWW / ISBN wskazuje rekord o tym samym tytule (ISBN książki
      noszą też jej rozdziały, a adres WWW bywa wspólny dla kilku prac —
      sam identyfikator to za mało, żeby wiązać bez pytania).

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

        uidy = szukacz.szukaj_lokalnie(wartosc) or _szukaj_na_serwerze(
            serwer, szukacz, wartosc
        )
        wynik.bez_serwera = serwer.powod
        if not uidy:
            continue

        uidy = uidy[:MAX_KANDYDATOW]
        if szukacz is SZUKACZ_DOI and len(uidy) == 1:
            pewne = uidy
        else:
            pewne = _zawez_po_tytule(uidy, tytul)
        if len(pewne) == 1:
            wynik.status, wynik.uidy, wynik.po_czym = PEWNY, pewne, opis
            return wynik
        if do_wyboru is None:
            # Zgodne tytułem na początek listy.
            do_wyboru = (pewne + [u for u in uidy if u not in pewne], opis)

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

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def pole(self, nazwa):
        return self.request.POST.get(nazwa, "").strip()[:1024]

    def uczelnia(self):
        return Uczelnia.objects.get_for_request(self.request)

    def klient(self):
        """Fabryka klienta PBN zalogowanego użytkownika (leniwa — lokalne
        trafienie nie wymaga ani konfiguracji, ani tokena)."""
        uczelnia = self.uczelnia()
        if uczelnia is None:
            return None
        token = getattr(self.request.user, "pbn_token", "")
        return lambda: uczelnia.pbn_client(token)

    def szukaj(self) -> dict:
        raise NotImplementedError

    def post(self, request, *args, **kw):
        try:
            return JsonResponse(self.szukaj())
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

    def szukaj(self):
        wynik = znajdz_odpowiednik_publikacji(
            doi=self.pole("doi"),
            www=self.pole("www"),
            public_www=self.pole("public_www"),
            isbn=self.pole("isbn"),
            e_isbn=self.pole("e_isbn"),
            tytul=self.pole("tytul_oryginalny"),
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
        return _odpowiedz(wynik.status, wynik.komunikat, kandydaci, uwaga)


class PobierzOdpowiednikAutoraView(PobierzZPBNBase):
    """Odpowiednik autora (FD#519): po ORCID, a gdy go brak — po imieniu
    i nazwisku oraz po autorach prac powiązanych z PBN."""

    def szukaj(self):
        from pbn_integrator.utils.odpowiednik_autora import szukaj_odpowiednika_autora

        autor = None
        pk = self.pole("pk")
        if pk.isdigit():
            autor = Autor.objects.filter(pk=int(pk)).first()
        if autor is None:
            autor = Autor()
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
    "znajdz_odpowiednik_publikacji",
]
