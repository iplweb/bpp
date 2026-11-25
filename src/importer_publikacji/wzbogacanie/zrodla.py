"""Pobieranie danych do wzbogacania rekordu: CrossRef i PBN (z wersjami)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    PraceSerwisoweException,
)

from ..providers import FetchedPublication
from ..providers.crossref import publikacja_z_danych_crossref
from ..providers.pbn import publikacja_z_obiektu_wersji

logger = logging.getLogger(__name__)

CROSSREF = "crossref"
PBN = "pbn"

NAZWY_ZRODEL = {CROSSREF: "CrossRef", PBN: "PBN"}


@dataclass
class WersjaPBN:
    """Jedna wersja publikacji z historii w PBN."""

    identyfikator: str
    data: datetime | None
    biezaca: bool = False
    przypieta: bool = False
    obiekt: dict = field(default_factory=dict, repr=False)

    @property
    def data_tekst(self):
        if self.data is None:
            return "bez daty"
        return timezone.localtime(self.data).strftime("%d.%m.%Y, %H:%M")

    @property
    def oznaczenia(self):
        wynik = []
        if self.biezaca:
            wynik.append("najnowsza w PBN")
        if self.przypieta:
            wynik.append("przypięta na profilu instytucji")
        return wynik

    @property
    def opis(self):
        """„z 12.03.2024, 10:15 (najnowsza w PBN)” — do list i historii."""
        opis = f"z {self.data_tekst}"
        if self.oznaczenia:
            opis += f" ({', '.join(self.oznaczenia)})"
        return opis


@dataclass
class DaneZrodla:
    """Wynik pobrania danych ze źródła dla jednego rekordu."""

    zrodlo: str
    publikacja: FetchedPublication | None = None
    #: Powód, dla którego nie ma czego porównywać (tekst dla redaktora).
    blad: str = ""
    ostrzezenia: list[str] = field(default_factory=list)
    #: Skąd i z kiedy są pokazywane dane („pobrane z CrossRef 12.03.2024…”).
    stan_danych: str = ""
    #: Tylko PBN: wszystkie wersje (od najnowszej) i ta, którą pokazujemy.
    wersje: list[WersjaPBN] = field(default_factory=list)
    wersja: WersjaPBN | None = None

    @property
    def nazwa(self):
        return NAZWY_ZRODEL[self.zrodlo]

    @property
    def wczesniejsza_wersja(self):
        """Czy pokazujemy wersję PBN inną niż najnowsza (FD#518)."""
        return self.wersja is not None and not self.wersja.biezaca


#: Limit czasu (łączenie, odpowiedź) zapytań wysyłanych w trakcie obsługi
#: strony: jedno zapytanie, bez ponowień — żeby niedostępne źródło nie
#: zawiesiło widoku.
LIMIT_CZASU_PBN = (5, 20)
LIMIT_CZASU_CROSSREF = 15


def _kiedy(data):
    return f"{timezone.localtime(data):%d.%m.%Y, %H:%M}"


def odswiez_z_crossref(rekord) -> str:
    """Pobierz dane DOI rekordu z CrossRef (jedno zapytanie z krótkim limitem
    czasu) i zapisz w pamięci podręcznej. Zwraca komunikat błędu albo ``""``.
    Przy błędzie poprzednio pobrane dane zostają."""
    from crossref_bpp.models import CrossrefAPICache
    from crossref_bpp.monkey_patches import PatchedWorks
    from import_common.normalization import normalize_doi

    doi = normalize_doi(rekord.doi or "")
    if not doi:
        return "Rekord nie ma numeru DOI."
    works = PatchedWorks()
    works.timeout = LIMIT_CZASU_CROSSREF
    try:
        data = works.doi(doi)
    except (requests.RequestException, ValueError) as e:
        logger.warning("CrossRef: błąd pobierania DOI %s: %s", doi, e)
        return "Nie udało się pobrać danych z CrossRef — spróbuj za chwilę."
    if data is None:
        return f"CrossRef nie ma danych dla DOI {doi}."
    CrossrefAPICache.objects.update_or_create(doi=doi, defaults={"data": data})
    return ""


def identyfikator(rekord, zrodlo, wersja="") -> str:
    """Co dokładnie porównujemy: publikacja w źródle wskazywana TERAZ przez
    rekord (DOI albo odpowiednik w PBN) i — dla PBN — wersja.

    Podgląd zapisuje tę wartość w formularzu; zatwierdzenie liczy ją ponownie
    (przed pobraniem danych źródła i jeszcze raz na rekordzie odczytanym pod
    blokadą). Różnica oznacza, że rekord wskazuje już inną publikację niż
    ta, której dane widział redaktor."""
    from import_common.normalization import normalize_doi

    if zrodlo == CROSSREF:
        return f"doi:{normalize_doi(rekord.doi or '') or ''}"
    return f"pbn:{rekord.pbn_uid_id or ''}:{wersja or ''}"


def pobierz_z_crossref(rekord) -> DaneZrodla:
    """Dane CrossRef dla DOI rekordu — z pamięci podręcznej BPP; pierwszy
    raz (brak danych) pobierane jednym zapytaniem z krótkim limitem czasu."""
    from crossref_bpp.models import CrossrefAPICache
    from import_common.normalization import normalize_doi

    dane = DaneZrodla(CROSSREF)
    doi = normalize_doi(rekord.doi or "")
    if not doi:
        dane.blad = (
            "Rekord nie ma numeru DOI — CrossRef wyszukuje publikacje po DOI. "
            "Uzupełnij pole „DOI” i spróbuj ponownie."
        )
        return dane
    wpis = CrossrefAPICache.objects.filter(doi=doi).first()
    if wpis is None:
        dane.blad = odswiez_z_crossref(rekord)
        if dane.blad:
            return dane
        wpis = CrossrefAPICache.objects.get(doi=doi)
    dane.stan_danych = f"Dane pobrane z CrossRef {_kiedy(wpis.ostatnio_zmodyfikowany)}."
    dane.publikacja = publikacja_z_danych_crossref(wpis.data)
    return dane


def _data_wersji(wersja):
    wartosc = wersja.get("createdTime")
    if not wartosc:
        return None
    data = parse_datetime(str(wartosc))
    if data is not None and timezone.is_naive(data):
        data = timezone.make_aware(data, timezone.get_default_timezone())
    return data


def _przypiete_na_profilu(pbn_publication, uczelnia):
    """Identyfikatory wersji przypiętych na profilu instytucji w PBN (z
    lokalnej kopii profilu; zwykle jeden, powtórzony dla każdej osoby)."""
    from pbn_api.models import PublikacjaInstytucji

    if uczelnia is None or not uczelnia.pbn_uid_id:
        return set()
    return {
        str(wersja).lower()
        for wersja in PublikacjaInstytucji.objects.filter(
            publicationId_id=pbn_publication.pk,
            institutionId_id=uczelnia.pbn_uid_id,
        ).values_list("publicationVersion", flat=True)
        if wersja
    }


def wersje_pbn(pbn_publication, uczelnia) -> list[WersjaPBN]:
    """Wszystkie wersje publikacji z lokalnej kopii PBN, od najnowszej."""
    przypiete = _przypiete_na_profilu(pbn_publication, uczelnia)
    wersje = []
    for wersja in pbn_publication.versions or []:
        if not isinstance(wersja, dict) or not wersja.get("object"):
            continue
        identyfikator = str(wersja.get("versionHash") or "")
        wersje.append(
            WersjaPBN(
                identyfikator=identyfikator,
                data=_data_wersji(wersja),
                biezaca=bool(wersja.get("current")),
                przypieta=bool(identyfikator) and identyfikator.lower() in przypiete,
                obiekt=wersja["object"],
            )
        )
    poczatek = datetime.min.replace(tzinfo=timezone.get_default_timezone())
    wersje.sort(key=lambda w: (w.biezaca, w.data or poczatek), reverse=True)
    return wersje


def _klient_pbn_bez_ponowien(uczelnia):
    """Klient PBN (tylko odczyt, credentiale aplikacji uczelni) na czas
    obsługi strony: krótki limit czasu i JEDNO zapytanie. Zwykły transport
    ponawia błędy połączenia kilkanaście razy z przerwami — w zadaniach w tle
    to zaleta, ale widok wisiałby przez minuty."""
    from pbn_client.transport import RequestsTransport

    from pbn_api.client import PBNClient
    from pbn_api.reporting import bpp_reporter

    if not uczelnia or not all([uczelnia.pbn_app_name, uczelnia.pbn_app_token]):
        raise ValueError("Brak konfiguracji PBN")

    class TransportBezPonowien(RequestsTransport):
        def _make_get_request_with_retry(self, url, headers, max_retries=1):
            return requests.get(
                self.base_url + url, headers=headers, timeout=self.timeout
            )

    return PBNClient(
        TransportBezPonowien(
            uczelnia.pbn_app_name,
            uczelnia.pbn_app_token,
            uczelnia.pbn_api_root,
            timeout=LIMIT_CZASU_PBN,
            reporter=bpp_reporter,
        )
    )


def odswiez_z_pbn(rekord, uczelnia) -> str:
    """Pobierz odpowiednik rekordu z PBN (sam odczyt, jedno zapytanie
    z krótkim limitem czasu) i zapisz w lokalnej kopii. Zwraca komunikat
    błędu albo ``""``. Przy błędzie lokalna kopia zostaje bez zmian."""
    from pbn_api.models import Publication
    from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

    if not rekord.pbn_uid_id:
        return "Rekord nie ma odpowiednika w PBN."
    try:
        client = _klient_pbn_bez_ponowien(uczelnia)
    except ValueError:
        return "Uczelnia nie ma skonfigurowanego dostępu do PBN."
    try:
        odpowiedz = client.get_publication_by_id(rekord.pbn_uid_id)
    except (
        HttpException,
        PraceSerwisoweException,
        AccessDeniedException,
        requests.RequestException,
    ) as e:
        logger.warning("PBN: nie pobrano publikacji %s: %s", rekord.pbn_uid_id, e)
        return "Nie udało się pobrać aktualnych danych z PBN — spróbuj za chwilę."
    if not odpowiedz:
        return "PBN nie zwrócił danych tej publikacji."
    zapisz_mongodb(odpowiedz, Publication)
    return ""


def _wybierz_wersje(wersje, identyfikator):
    """Wersja o podanym identyfikatorze; bez niego — przypięta na profilu
    instytucji (jeśli jest dokładnie jedna), w ostateczności najnowsza."""
    if identyfikator:
        szukany = identyfikator.lower()
        return next((w for w in wersje if w.identyfikator.lower() == szukany), None)
    przypiete = [w for w in wersje if w.przypieta]
    if len(przypiete) == 1:
        return przypiete[0]
    return next((w for w in wersje if w.biezaca), wersje[0])


def _ostrzezenia_o_wersjach(wersje):
    przypiete = [w for w in wersje if w.przypieta]
    biezaca = next((w for w in wersje if w.biezaca), None)
    if len(przypiete) > 1:
        return [
            "Profil instytucji w PBN wskazuje kilka różnych wersji tej "
            "publikacji — domyślnie pokazuję najnowszą."
        ]
    if len(przypiete) == 1 and biezaca is not None and przypiete[0] is not biezaca:
        return [
            "Na profilu instytucji przypięta jest wersja "
            f"z {przypiete[0].data_tekst}, a najnowsza w repozytorium PBN jest "
            f"z {biezaca.data_tekst} — to dwie różne wersje. Domyślnie "
            "pokazuję przypiętą; drugą wybierzesz z listy wersji."
        ]
    return []


def pobierz_z_pbn(rekord, uczelnia, wersja=None) -> DaneZrodla:
    """Dane odpowiednika rekordu w PBN z LOKALNEJ kopii, w wersji ``wersja``
    (identyfikator wersji) albo domyślnej. Nie łączy się z PBN — lokalną
    kopię odświeża ``odswiez_z_pbn`` (przycisk „Odśwież z PBN”)."""
    from pbn_api.models import Publication

    dane = DaneZrodla(PBN)
    if not rekord.pbn_uid_id:
        dane.blad = (
            "Rekord nie ma odpowiednika w PBN. Wskaż go w polu „Odpowiednik "
            "w PBN” i zapisz rekord, a potem spróbuj ponownie."
        )
        return dane
    # Świeży odczyt: kopia mogła być przed chwilą odświeżona.
    pbn_publication = Publication.objects.get(pk=rekord.pbn_uid_id)
    dane.stan_danych = (
        f"Dane z lokalnej kopii PBN z {_kiedy(pbn_publication.last_updated_on)}."
    )

    dane.wersje = wersje_pbn(pbn_publication, uczelnia)
    if not dane.wersje:
        dane.blad = "Lokalna kopia tej publikacji z PBN nie zawiera żadnej wersji."
        return dane
    dane.wersja = _wybierz_wersje(dane.wersje, wersja)
    if dane.wersja is None:
        dane.blad = (
            "Nie ma już takiej wersji tej publikacji w PBN — wybierz inną z listy."
        )
        return dane
    dane.ostrzezenia.extend(_ostrzezenia_o_wersjach(dane.wersje))
    dane.publikacja = publikacja_z_obiektu_wersji(
        {"versions": pbn_publication.versions},
        dane.wersja.obiekt,
        pbn_publication.pk,
    )
    return dane
