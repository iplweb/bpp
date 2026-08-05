"""Sześć czasowników OAI-PMH 2.0 dla profilu OpenAIRE CRIS 1.2.

Warstwa zna protokół (czasowniki, sety, tokeny, błędy) i **nie zna semantyki
CERIF** — ładunek metadanych składają moduły ``cerif_export.cerif.*``, dane
dostarczają ``cerif_export.providers.*``. Wejście HTTP (``views.py``) buduje
:class:`Zadanie` i serializuje wynik :func:`odpowiedz`.

Wszystkie datestampy wychodzą w UTC w formacie ``const.FORMAT_DATESTAMP``,
zgodnie z ``granularity`` deklarowaną w ``Identify``.
"""

import datetime
import importlib
import logging

import rollbar
from django.conf import settings
from lxml import etree

from cerif_export import const, identyfikatory
from cerif_export.kontekst import KontekstSerializacji, Kursor
from cerif_export.oai import bledy, tokeny
from cerif_export.oai.bledy import (
    NS_PMH,
    NS_XSI,
    SCHEMA_LOCATION_PMH,
    BlednyArgument,
    BlednyCzasownik,
    BlednyResumptionToken,
    BrakPasujacychRekordow,
    NieobslugiwanyFormat,
    NieznanyIdentyfikator,
)
from cerif_export.providers.base import ADNOTACJA_TS, na_datestamp

logger = logging.getLogger(__name__)

#: Lokalizacja XSD profilu, deklarowana w ``ListMetadataFormats``. Świadomie
#: nie w ``const.py`` — to adres schematu OAI-PMH-owego elementu ``<schema>``,
#: a nie stała samego profilu CERIF.
SCHEMA_CERIF = "https://www.openaire.eu/schema/cris/1.2/openaire-cerif-profile.xsd"

#: Namespace bloku ``oai-identifier`` z odpowiedzi ``Identify``. To element
#: standardu OAI-PMH 2.0, nie profilu CERIF — stąd osobna stała.
NS_OAI_IDENTIFIER = "http://www.openarchives.org/OAI/2.0/oai-identifier"

CZASOWNIKI = (
    "Identify",
    "ListMetadataFormats",
    "ListSets",
    "ListIdentifiers",
    "ListRecords",
    "GetRecord",
)

#: Argumenty dopuszczalne dla czasownika (poza samym ``verb``).
ARGUMENTY = {
    "Identify": frozenset(),
    "ListMetadataFormats": frozenset({"identifier"}),
    "ListSets": frozenset({"resumptionToken"}),
    "ListIdentifiers": frozenset(
        {"metadataPrefix", "from", "until", "set", "resumptionToken"}
    ),
    "ListRecords": frozenset(
        {"metadataPrefix", "from", "until", "set", "resumptionToken"}
    ),
    "GetRecord": frozenset({"identifier", "metadataPrefix"}),
}

#: Slug encji -> moduł w ``cerif_export.cerif`` z funkcją ``serializuj``.
MODULY_SERIALIZERA = {
    "wc": "publication",
    "wz": "publication",
    "pd": "publication",
    "ph": "publication",
    "zr": "publication",
    "au": "person",
    "je": "orgunit",
    "uc": "orgunit",
    # Instytucja finansująca wychodzi jako OrgUnit — profil nie ma osobnej
    # encji grantodawcy. Bez tego wpisu ``ListRecords`` dla setu OrgUnits
    # wywalałby się na pierwszym grantodawcy zwróconym przez provider.
    "if": "orgunit",
    "pt": "patent",
    "kf": "event",
}

_WZORCE_DATY = (
    (const.FORMAT_DATESTAMP, False),
    ("%Y-%m-%d", True),
)


class Zadanie:
    """Żądanie OAI-PMH oderwane od HTTP.

    ``argumenty`` może być zwykłym słownikiem albo ``QueryDict`` — w tym
    drugim przypadku powtórzone klucze są wykrywane i dają ``badArgument``
    (protokół zabrania powtarzania argumentów).
    """

    def __init__(self, uczelnia, base_url, argumenty=None):
        self.uczelnia = uczelnia
        self.base_url = base_url
        self.argumenty = argumenty if argumenty is not None else {}

    @property
    def namespace(self) -> str:
        return self.uczelnia.oai_repository_identifier()


# -- rejestr providerów --------------------------------------------------


def rejestr_providerow() -> dict:
    """Mapa ``setSpec`` -> instancja providera.

    Zwraca **ten sam** rejestr, którego używa ``providers.provider_dla_setu``.
    Wcześniej warstwa OAI budowała własny słownik: testy widoczności chodziły
    wtedy przez jeden rejestr, a HTTP przez drugi, więc sprawdzały inny
    obiekt, niż serwowała produkcja. Dodanie providera wymagało też edycji
    dwóch miejsc.

    Import leniwy, bo import modeli Django na poziomie modułu ``oai``
    wiązałby warstwę protokołu z gotowością rejestru aplikacji.
    """
    from cerif_export.providers import PROVIDERY_WG_SETU

    return dict(PROVIDERY_WG_SETU)


def serializer_dla(slug: str):
    """Zwróć funkcję ``serializuj(obj, ctx)`` dla sluga encji."""
    nazwa = MODULY_SERIALIZERA.get(slug)
    if nazwa is None:
        raise identyfikatory.BlednyIdentyfikator(
            f"Brak serializera CERIF dla sluga {slug!r}"
        )
    return importlib.import_module(f"cerif_export.cerif.{nazwa}").serializuj


def serializer_service():
    """Zwróć funkcję ``serializuj(uczelnia, ctx)`` rekordu ``Service``."""
    return importlib.import_module("cerif_export.cerif.service").serializuj


# -- wejście -------------------------------------------------------------


def odpowiedz(zadanie: Zadanie) -> etree._Element:
    """Zbuduj kompletny dokument ``<OAI-PMH>`` dla żądania.

    Błędy protokołu **nie** propagują się wyżej — wracają jako ``<error>``
    w poprawnej odpowiedzi, którą warstwa HTTP odda ze statusem 200.
    """
    korzen = _koperta()
    argumenty = {}

    try:
        argumenty = _splaszcz(zadanie.argumenty)
        czasownik = _wyluskaj_czasownik(argumenty)
        pozostale = {k: v for k, v in argumenty.items() if k != "verb"}
        _sprawdz_nazwy_argumentow(czasownik, pozostale)
        tresc = _WYKONAWCY[czasownik](zadanie, pozostale)
    except bledy.BladProtokolu as wyjatek:
        echo = {} if wyjatek.kod in bledy.KODY_BEZ_ECHA_ARGUMENTOW else argumenty
        _dopisz_request(korzen, zadanie.base_url, echo)
        korzen.append(bledy.element_dla_wyjatku(wyjatek))
        return korzen

    _dopisz_request(korzen, zadanie.base_url, argumenty)
    korzen.append(tresc)
    return korzen


def na_xml(korzen: etree._Element) -> bytes:
    """Zserializuj dokument odpowiedzi do bajtów (z deklaracją XML)."""
    return etree.tostring(
        korzen, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )


# -- czasowniki ----------------------------------------------------------


def _identify(zadanie, argumenty):
    uczelnia = zadanie.uczelnia
    rejestr = rejestr_providerow()

    identify = etree.Element(f"{{{NS_PMH}}}Identify")
    _pod(identify, "repositoryName", uczelnia.nazwa)
    _pod(identify, "baseURL", zadanie.base_url)
    _pod(identify, "protocolVersion", "2.0")
    _pod(identify, "adminEmail", _adres_administratora())
    _pod(identify, "earliestDatestamp", _najstarszy_datestamp(uczelnia, rejestr))
    _pod(identify, "deletedRecord", const.DELETED_RECORD)
    _pod(identify, "granularity", const.GRANULARITY)

    # Pierwszy <description>: oai-identifier. Wymagany przez OAI-PMH 2.0
    # (walidator: "the Identify descriptions list (1b) does not contain an
    # 'oai-identifier' element"), niezależnie od profilu CERIF.
    _pod(identify, "description").append(_oai_identifier(zadanie))

    # Drugi <description>: rekord Service — to z kolei wymóg profilu
    # OpenAIRE CRIS.
    serializuj = serializer_service()
    kontekst = _kontekst(zadanie, _puste_zbiory())
    # `base_url` i adres serwisu zna tylko warstwa HTTP. Bez ich przekazania
    # `OAIPMHBaseURL` i `WebsiteURL` w ogóle nie powstawały — a to po nich
    # OpenAIRE i DRIS rozpoznają, gdzie ten CRIS właściwie stoi.
    element = _bezpiecznie(
        lambda: serializuj(
            uczelnia,
            kontekst,
            base_url=zadanie.base_url,
            www_url=_adres_serwisu(uczelnia),
        ),
        "Service",
    )
    if element is not None:
        _pod(identify, "description").append(element)

    return identify


def _adres_serwisu(uczelnia):
    """Publiczny adres serwisu uczelni (``WebsiteURL`` w ``Service``)."""
    site = getattr(uczelnia, "site", None)
    domena = getattr(site, "domain", None)
    return f"https://{domena}/" if domena else None


def _oai_identifier(zadanie):
    """Blok ``oai-identifier`` opisujący schemat identyfikatorów repozytorium."""
    el = etree.Element(
        f"{{{NS_OAI_IDENTIFIER}}}oai-identifier",
        nsmap={None: NS_OAI_IDENTIFIER, "xsi": NS_XSI},
    )
    el.set(
        f"{{{NS_XSI}}}schemaLocation",
        f"{NS_OAI_IDENTIFIER} {NS_OAI_IDENTIFIER}.xsd",
    )
    for nazwa, wartosc in (
        ("scheme", "oai"),
        ("repositoryIdentifier", zadanie.namespace),
        ("delimiter", ":"),
        (
            "sampleIdentifier",
            identyfikatory.zbuduj_z_czesci(zadanie.namespace, "wc", 1),
        ),
    ):
        etree.SubElement(el, f"{{{NS_OAI_IDENTIFIER}}}{nazwa}").text = wartosc
    return el


def _list_metadata_formats(zadanie, argumenty):
    identyfikator = argumenty.get("identifier")
    if identyfikator is not None:
        # Protokół: dla nieznanego identyfikatora -> idDoesNotExist.
        _znajdz_rekord(zadanie, identyfikator)

    lista = etree.Element(f"{{{NS_PMH}}}ListMetadataFormats")
    format_ = _pod(lista, "metadataFormat")
    _pod(format_, "metadataPrefix", const.METADATA_PREFIX)
    _pod(format_, "schema", SCHEMA_CERIF)
    _pod(format_, "metadataNamespace", const.NS_CERIF)
    return lista


def _list_sets(zadanie, argumenty):
    if "resumptionToken" in argumenty:
        # Wszystkie dziewięć setów mieści się w jednej odpowiedzi, więc
        # żaden token ListSets nigdy nie został przez nas wydany.
        raise BlednyResumptionToken("ListSets nie wydaje resumption tokenów")

    lista = etree.Element(f"{{{NS_PMH}}}ListSets")
    for set_spec in const.WSZYSTKIE_SETY:
        element = _pod(lista, "set")
        _pod(element, "setSpec", set_spec)
        _pod(element, "setName", const.nazwa_setu(set_spec))
    return lista


def _list_identifiers(zadanie, argumenty):
    return _lista(zadanie, argumenty, "ListIdentifiers", z_metadanymi=False)


def _list_records(zadanie, argumenty):
    return _lista(zadanie, argumenty, "ListRecords", z_metadanymi=True)


def _get_record(zadanie, argumenty):
    identyfikator = argumenty.get("identifier")
    if identyfikator is None:
        raise BlednyArgument("GetRecord wymaga argumentu identifier")

    prefix = argumenty.get("metadataPrefix")
    if prefix is None:
        raise BlednyArgument("GetRecord wymaga argumentu metadataPrefix")
    _sprawdz_prefix(prefix)

    set_spec, provider, obiekt = _znajdz_rekord(zadanie, identyfikator)

    widoczne = provider.zbiory_widocznosci(zadanie.uczelnia, [obiekt])
    kontekst = _kontekst(zadanie, widoczne)

    korzen = etree.Element(f"{{{NS_PMH}}}GetRecord")
    rekord = _pod(korzen, "record")
    _naglowek(rekord, set_spec, obiekt, zadanie.namespace)

    # GetRecord dotyczy jednego rekordu — pominięcie go dałoby odpowiedź
    # niezgodną ze schematem, więc tutaj błąd serializacji propaguje się
    # (po zgłoszeniu do Rollbara), inaczej niż przy harveście listowym.
    serializuj = serializer_dla(identyfikatory.slug_dla(obiekt))
    element = _bezpiecznie(
        lambda: serializuj(obiekt, kontekst),
        identyfikator,
        pomijaj=False,
    )
    _pod(rekord, "metadata").append(element)
    return korzen


_WYKONAWCY = {
    "Identify": _identify,
    "ListMetadataFormats": _list_metadata_formats,
    "ListSets": _list_sets,
    "ListIdentifiers": _list_identifiers,
    "ListRecords": _list_records,
    "GetRecord": _get_record,
}


# -- stronicowanie list --------------------------------------------------


def _lista(zadanie, argumenty, nazwa, z_metadanymi):
    set_spec, prefix, od, do, kursor = _parametry_listy(argumenty)
    rejestr = rejestr_providerow()

    if set_spec is not None and set_spec not in rejestr:
        raise BrakPasujacychRekordow(f"Nieznany set: {set_spec}")

    pary, kolejny = _zbierz_strone(zadanie.uczelnia, rejestr, set_spec, od, do, kursor)
    if not pary:
        raise BrakPasujacychRekordow()

    korzen = etree.Element(f"{{{NS_PMH}}}{nazwa}")
    namespace = zadanie.namespace

    if z_metadanymi:
        _dopisz_rekordy(korzen, zadanie, rejestr, pary, namespace)
    else:
        for biezacy_set, obiekt in pary:
            _naglowek(korzen, biezacy_set, obiekt, namespace)

    _dopisz_token(korzen, argumenty, kolejny, set_spec, prefix, od, do)
    return korzen


def _parametry_listy(argumenty):
    """Zwróć ``(set_spec, prefix, od, do, kursor)`` dla ListIdentifiers/Records."""
    if "resumptionToken" in argumenty:
        if len(argumenty) > 1:
            pozostale = sorted(set(argumenty) - {"resumptionToken"})
            raise BlednyArgument(
                "resumptionToken wyklucza pozostałe argumenty: " + ", ".join(pozostale)
            )
        dane = tokeny.odkoduj(argumenty["resumptionToken"])
        _sprawdz_prefix(dane["prefix"], z_tokenu=True)
        try:
            od = _parsuj_date(dane["od"], "from")[0]
            do = _parsuj_date(dane["do"], "until")[0]
        except BlednyArgument as wyjatek:
            raise BlednyResumptionToken(
                "Resumption token niesie niepoprawny zakres dat"
            ) from wyjatek
        return dane["set"], dane["prefix"], od, do, tokeny.kursor_z(dane)

    prefix = argumenty.get("metadataPrefix")
    if prefix is None:
        raise BlednyArgument(
            "Argument metadataPrefix jest wymagany, gdy nie podano resumptionToken"
        )
    _sprawdz_prefix(prefix)

    od, od_dzienna = _parsuj_date(argumenty.get("from"), "from")
    do, do_dzienna = _parsuj_date(argumenty.get("until"), "until", koniec_dnia=True)

    if od is not None and do is not None:
        if od_dzienna != do_dzienna:
            raise BlednyArgument(
                "Argumenty from i until muszą mieć tę samą granularność"
            )
        if od > do:
            raise BlednyArgument("Argument from jest późniejszy niż until")

    return argumenty.get("set"), prefix, od, do, None


def _zbierz_strone(uczelnia, rejestr, set_spec, od, do, kursor, rozmiar=None):
    """Zbierz stronę ``[(setSpec, obiekt), ...]`` i kolejny kursor.

    Bez argumentu ``set`` harvest idzie przez wszystkie sety po kolei; pozycję
    niesie ``Kursor.slug``, bo każdy slug należy do dokładnie jednego setu.
    """
    rozmiar = rozmiar or const.ROZMIAR_STRONY
    kolejnosc = [set_spec] if set_spec else list(const.WSZYSTKIE_SETY)

    indeks = 0
    if kursor is not None:
        indeks = _indeks_setu(kolejnosc, rejestr, kursor)

    zebrane = []
    for pozycja in range(indeks, len(kolejnosc)):
        brakuje = rozmiar - len(zebrane)

        if brakuje == 0:
            # Strona zapełniła się dokładnie na granicy setu. Token wydajemy
            # TYLKO wtedy, gdy w kolejnych setach coś jeszcze jest — inaczej
            # harvester dostawał token, po którym następne żądanie kończyło
            # się błędem `noRecordsMatch` zamiast pustą ostatnią stroną.
            # (Bez warunku `brakuje == 0` sonda niżej dostawała z kolei
            # rozmiar=1, przycinała wynik do zera i wywalała się na
            # `obiekty[-1]`.)
            if _cos_zostalo(uczelnia, rejestr, kolejnosc, pozycja, od, do):
                return zebrane, _kursor_dla(zebrane[-1][1])
            return zebrane, None

        biezacy_set = kolejnosc[pozycja]
        provider = rejestr[biezacy_set]
        wewnetrzny = kursor if (pozycja == indeks and kursor is not None) else None

        # Nadmiarowy element to sonda: jego obecność mówi, że w tym secie
        # jest jeszcze co najmniej jeden rekord, więc trzeba wydać token.
        obiekty, _ = provider.strona(
            uczelnia, od=od, do=do, kursor=wewnetrzny, rozmiar=brakuje + 1
        )
        obiekty = list(obiekty)

        if len(obiekty) > brakuje:
            obiekty = obiekty[:brakuje]
            zebrane.extend((biezacy_set, obiekt) for obiekt in obiekty)
            return zebrane, _kursor_dla(obiekty[-1])

        zebrane.extend((biezacy_set, obiekt) for obiekt in obiekty)

    return zebrane, None


def _cos_zostalo(uczelnia, rejestr, kolejnosc, pozycja, od, do):
    """Czy w setach od ``pozycja`` w górę został jakikolwiek rekord?

    Sety przed ``pozycja`` są w tym miejscu z definicji wyczerpane: każdy
    z nich był pobierany z zapasem jednego rekordu i oddał mniej, niż ten
    zapas — inaczej pętla wyszłaby wcześniej z tokenem.
    """
    for set_spec in kolejnosc[pozycja:]:
        obiekty, _ = rejestr[set_spec].strona(uczelnia, od=od, do=do, rozmiar=1)
        if list(obiekty):
            return True
    return False


def _indeks_setu(kolejnosc, rejestr, kursor):
    """Który set z ``kolejnosc`` zawiera model o slugu z kursora."""
    for pozycja, set_spec in enumerate(kolejnosc):
        provider = rejestr.get(set_spec)
        if provider is None:
            continue
        for model in provider.modele:
            if identyfikatory.slug_dla(model) == kursor.slug:
                return pozycja
    raise BlednyResumptionToken(
        f"Resumption token wskazuje slug {kursor.slug!r} spoza tego harvestu"
    )


def _kursor_dla(obiekt) -> Kursor:
    return Kursor(
        slug=identyfikatory.slug_dla(obiekt),
        ts=na_datestamp(getattr(obiekt, ADNOTACJA_TS, None)),
        pk=obiekt.pk,
    )


def _dopisz_token(korzen, argumenty, kolejny, set_spec, prefix, od, do):
    if kolejny is not None:
        _pod(
            korzen,
            "resumptionToken",
            tokeny.zakoduj(
                kolejny,
                set_spec,
                prefix,
                od=_na_datestamp_lub_none(od),
                do=_na_datestamp_lub_none(do),
            ),
        )
    elif "resumptionToken" in argumenty:
        # Lista niekompletna musi się domknąć pustym tokenem (sekcja 3.5).
        _pod(korzen, "resumptionToken")


def _dopisz_rekordy(korzen, zadanie, rejestr, pary, namespace):
    pominiete = 0
    for biezacy_set, obiekty in _wg_setu(pary):
        provider = rejestr[biezacy_set]
        widoczne = provider.zbiory_widocznosci(zadanie.uczelnia, obiekty)
        kontekst = _kontekst(zadanie, widoczne)

        for obiekt in obiekty:
            identyfikator = identyfikatory.zbuduj(namespace, obiekt)
            serializuj = serializer_dla(identyfikatory.slug_dla(obiekt))
            element = _bezpiecznie(
                lambda: serializuj(obiekt, kontekst),  # noqa: B023
                identyfikator,
            )
            if element is None:
                pominiete += 1
                continue

            rekord = _pod(korzen, "record")
            _naglowek(rekord, biezacy_set, obiekt, namespace)
            _pod(rekord, "metadata").append(element)

    if pominiete:
        logger.warning(
            "Eksport CERIF: pominięto %d z %d rekordów strony "
            "z powodu błędów serializacji",
            pominiete,
            len(pary),
        )


def _wg_setu(pary):
    """Pogrupuj ``[(setSpec, obiekt)]`` zachowując kolejność setów."""
    grupy = []
    for set_spec, obiekt in pary:
        if grupy and grupy[-1][0] == set_spec:
            grupy[-1][1].append(obiekt)
        else:
            grupy.append((set_spec, [obiekt]))
    return grupy


# -- pojedynczy rekord ---------------------------------------------------


def _znajdz_rekord(zadanie, identyfikator):
    """Zwróć ``(setSpec, provider, obiekt)`` albo podnieś idDoesNotExist."""
    try:
        namespace, model, pk = identyfikatory.rozbierz(identyfikator)
    except identyfikatory.BlednyIdentyfikator as wyjatek:
        raise NieznanyIdentyfikator(str(wyjatek)) from wyjatek

    if namespace != zadanie.namespace:
        raise NieznanyIdentyfikator(
            f"Identyfikator spoza tego repozytorium: {identyfikator}"
        )

    rejestr = rejestr_providerow()
    for set_spec, provider in rejestr.items():
        if model not in provider.modele:
            continue
        obiekt = provider.pojedynczy(zadanie.uczelnia, model, pk)
        if obiekt is None:
            break
        return set_spec, provider, obiekt

    raise NieznanyIdentyfikator(f"Brak rekordu o identyfikatorze {identyfikator}")


def _bezpiecznie(wywolanie, opis, pomijaj=True):
    """Wywołaj serializer, raportując i (domyślnie) pomijając zepsuty rekord.

    Świadome odstępstwo od wzorca „report + raise" z ``CLAUDE.md``: harvest
    całego korpusu nie może umierać na jednym zepsutym wierszu, bo agregator
    dostanie 500 zamiast dziesiątek tysięcy poprawnych rekordów. Wyjątek nie
    jest połykany — idzie do Rollbara i do logu. W testach ustawienie
    ``CERIF_EXPORT_PRZERYWAJ_NA_BLEDZIE`` przywraca twarde podniesienie.
    """
    try:
        return wywolanie()
    except Exception:
        rollbar.report_exc_info()
        logger.exception("Eksport CERIF: błąd serializacji rekordu %s", opis)
        if not pomijaj or getattr(settings, "CERIF_EXPORT_PRZERYWAJ_NA_BLEDZIE", False):
            raise
        return None


# -- składanie XML -------------------------------------------------------


def _koperta():
    korzen = etree.Element(f"{{{NS_PMH}}}OAI-PMH", nsmap={None: NS_PMH, "xsi": NS_XSI})
    korzen.set(f"{{{NS_XSI}}}schemaLocation", SCHEMA_LOCATION_PMH)
    _pod(korzen, "responseDate", _teraz())
    return korzen


def _dopisz_request(korzen, base_url, atrybuty):
    element = _pod(korzen, "request", base_url)
    for nazwa, wartosc in atrybuty.items():
        element.set(nazwa, wartosc)
    return element


def _pod(rodzic, nazwa, tekst=None):
    element = etree.SubElement(rodzic, f"{{{NS_PMH}}}{nazwa}")
    if tekst is not None:
        element.text = str(tekst)
    return element


def _naglowek(rodzic, set_spec, obiekt, namespace):
    naglowek = _pod(rodzic, "header")
    _pod(naglowek, "identifier", identyfikatory.zbuduj(namespace, obiekt))
    _pod(naglowek, "datestamp", na_datestamp(getattr(obiekt, ADNOTACJA_TS, None)))
    _pod(naglowek, "setSpec", set_spec)
    return naglowek


# -- walidacja argumentów ------------------------------------------------


def _splaszcz(argumenty):
    """Sprowadź argumenty do ``dict[str, str]``, wykrywając powtórzenia."""
    if argumenty is None:
        return {}

    if not hasattr(argumenty, "lists"):
        return dict(argumenty)

    wynik = {}
    for nazwa, wartosci in argumenty.lists():
        if len(wartosci) > 1:
            raise BlednyArgument(f"Argument {nazwa} został powtórzony")
        wynik[nazwa] = wartosci[0]
    return wynik


def _wyluskaj_czasownik(argumenty):
    czasownik = argumenty.get("verb")
    if czasownik is None:
        raise BlednyCzasownik("Brak argumentu verb")
    if czasownik not in CZASOWNIKI:
        raise BlednyCzasownik(f"Nieznany czasownik: {czasownik}")
    return czasownik


def _sprawdz_nazwy_argumentow(czasownik, argumenty):
    nieznane = sorted(set(argumenty) - ARGUMENTY[czasownik])
    if nieznane:
        raise BlednyArgument(
            f"Argumenty nieobsługiwane przez {czasownik}: " + ", ".join(nieznane)
        )


def _sprawdz_prefix(prefix, z_tokenu=False):
    if prefix != const.METADATA_PREFIX:
        if z_tokenu:
            raise BlednyResumptionToken(
                "Resumption token niesie nieobsługiwany metadataPrefix"
            )
        raise NieobslugiwanyFormat(
            f"Obsługiwany jest wyłącznie metadataPrefix={const.METADATA_PREFIX}"
        )


def _parsuj_date(wartosc, nazwa, koniec_dnia=False):
    """Zwróć ``(datetime | None, czy_granularnosc_dzienna)``."""
    if wartosc is None:
        return None, False

    for wzorzec, dzienna in _WZORCE_DATY:
        try:
            moment = datetime.datetime.strptime(wartosc, wzorzec)
        except ValueError:
            continue

        if dzienna and koniec_dnia:
            # Granularność dzienna w ``until`` jest inkluzywna dla całej doby.
            moment = moment.replace(hour=23, minute=59, second=59)
        return moment.replace(tzinfo=datetime.UTC), dzienna

    raise BlednyArgument(f"Argument {nazwa} ma niepoprawny format daty: {wartosc}")


# -- drobiazgi -----------------------------------------------------------


def _kontekst(zadanie, widoczne):
    return KontekstSerializacji(
        namespace=zadanie.namespace,
        uczelnia=zadanie.uczelnia,
        widoczne=widoczne,
    )


def _puste_zbiory():
    from cerif_export.kontekst import ZbioryWidocznosci

    return ZbioryWidocznosci()


def _teraz():
    return datetime.datetime.now(datetime.UTC).strftime(const.FORMAT_DATESTAMP)


def _na_datestamp_lub_none(moment):
    return None if moment is None else na_datestamp(moment)


def _najstarszy_datestamp(uczelnia, rejestr):
    najstarszy = None
    for provider in rejestr.values():
        wartosc = provider.najstarszy_datestamp(uczelnia)
        if wartosc is None:
            continue
        if najstarszy is None or wartosc < najstarszy:
            najstarszy = wartosc

    if najstarszy is None:
        return const.EPOKA
    if isinstance(najstarszy, str):
        return najstarszy
    return na_datestamp(najstarszy)


def _adres_administratora():
    jawny = getattr(settings, "CERIF_EXPORT_ADMIN_EMAIL", "")
    if jawny:
        return jawny
    admini = getattr(settings, "ADMINS", ())
    if admini:
        return admini[0][1]
    return settings.DEFAULT_FROM_EMAIL
