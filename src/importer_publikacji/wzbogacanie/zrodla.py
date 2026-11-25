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
from ..providers.crossref import CrossRefProvider
from ..providers.pbn import _get_pbn_client, publikacja_z_obiektu_wersji

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


def pobierz_z_crossref(rekord) -> DaneZrodla:
    dane = DaneZrodla(CROSSREF)
    doi = (rekord.doi or "").strip()
    if not doi:
        dane.blad = (
            "Rekord nie ma numeru DOI — CrossRef wyszukuje publikacje po DOI. "
            "Uzupełnij pole „DOI” i spróbuj ponownie."
        )
        return dane
    try:
        dane.publikacja = CrossRefProvider().fetch(doi)
    except requests.RequestException as e:
        logger.warning("CrossRef: błąd pobierania DOI %s: %s", doi, e)
        dane.blad = f"Nie udało się połączyć z CrossRef ({e}). Spróbuj za chwilę."
        return dane
    if dane.publikacja is None:
        dane.blad = f"CrossRef nie ma danych dla DOI {doi}."
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


def _odswiez_kopie_pbn(pbn_publication, uczelnia, dane):
    """Pobierz publikację z PBN (tylko odczyt) i zapisz w lokalnej kopii.
    Gdy się nie uda — zostaje lokalna kopia i ostrzeżenie dla redaktora."""
    from pbn_api.models import Publication
    from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

    kopia = (
        "Pokazuję dane z lokalnej kopii PBN z "
        f"{timezone.localtime(pbn_publication.last_updated_on):%d.%m.%Y, %H:%M}."
    )
    try:
        client = _get_pbn_client(uczelnia)
    except ValueError:
        dane.ostrzezenia.append(
            f"Uczelnia nie ma skonfigurowanego dostępu do PBN. {kopia}"
        )
        return pbn_publication
    try:
        odpowiedz = client.get_publication_by_id(pbn_publication.pk)
    except (
        HttpException,
        PraceSerwisoweException,
        AccessDeniedException,
        requests.RequestException,
    ) as e:
        logger.warning("PBN: nie pobrano publikacji %s: %s", pbn_publication.pk, e)
        dane.ostrzezenia.append(
            f"Nie udało się pobrać aktualnych danych z PBN. {kopia}"
        )
        return pbn_publication
    if not odpowiedz:
        dane.ostrzezenia.append(f"PBN nie zwrócił danych tej publikacji. {kopia}")
        return pbn_publication
    zapisz_mongodb(odpowiedz, Publication)
    return Publication.objects.get(pk=pbn_publication.pk)


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


def pobierz_z_pbn(rekord, uczelnia, wersja=None, odswiez=True) -> DaneZrodla:
    """Dane odpowiednika rekordu w PBN, w wersji ``wersja`` (identyfikator
    wersji) albo domyślnej. ``odswiez=False`` — bez łączenia z PBN, z samej
    lokalnej kopii (przy zatwierdzaniu: stosujemy to, co było na podglądzie)."""
    dane = DaneZrodla(PBN)
    pbn_publication = getattr(rekord, "pbn_uid", None)
    if pbn_publication is None:
        dane.blad = (
            "Rekord nie ma odpowiednika w PBN. Wskaż go w polu „Odpowiednik "
            "w PBN” i zapisz rekord, a potem spróbuj ponownie."
        )
        return dane
    if odswiez:
        pbn_publication = _odswiez_kopie_pbn(pbn_publication, uczelnia, dane)

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
