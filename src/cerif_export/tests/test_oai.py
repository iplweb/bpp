"""Testy warstwy OAI-PMH eksportu CERIF.

Testy celowo **nie dotykają bazy**: providery i serializery CERIF są
podmieniane atrapami, a obiekty domenowe to niezapisane instancje modeli
Django (wystarczają, bo warstwa OAI czyta z nich tylko ``pk``, ``_meta``
i adnotację ``_cerif_ts``). Dzięki temu suita mierzy dokładnie to, co ma
mierzyć — protokół — a nie ORM.
"""

import datetime

import pytest
from django.core import signing
from lxml import etree

from bpp.models import (
    Autor,
    Jednostka,
    Konferencja,
    Patent,
    Uczelnia,
    Wydawnictwo_Ciagle,
)

from cerif_export import const, identyfikatory
from cerif_export.kontekst import Kursor, ZbioryWidocznosci
from cerif_export.oai import bledy, czasowniki, tokeny
from cerif_export.oai.bledy import NS_PMH
from cerif_export.providers.base import ADNOTACJA_TS, ProviderPusty, na_datestamp

BASE_URL = "https://bpp.example.org/cerif/"
NAMESPACE = "cerif.example.org"


# -- atrapy --------------------------------------------------------------


def _z_datestampem(obiekt, dzien):
    setattr(
        obiekt,
        ADNOTACJA_TS,
        datetime.datetime(2026, 1, dzien, 12, 0, 0, tzinfo=datetime.UTC),
    )
    return obiekt


class FikcyjnyProvider:
    """Provider trzymający obiekty w pamięci, z tą samą semantyką keyset."""

    def __init__(self, set_spec, modele, obiekty=()):
        self.set_spec = set_spec
        self.modele = list(modele)
        self._slugi = [identyfikatory.slug_dla(model) for model in self.modele]
        self.obiekty = sorted(obiekty, key=self._klucz)

    def _klucz(self, obiekt):
        slug = identyfikatory.slug_dla(obiekt)
        return (self._slugi.index(slug), getattr(obiekt, ADNOTACJA_TS), obiekt.pk)

    def _klucz_kursora(self, kursor):
        moment = datetime.datetime.strptime(kursor.ts, const.FORMAT_DATESTAMP).replace(
            tzinfo=datetime.UTC
        )
        return (self._slugi.index(kursor.slug), moment, kursor.pk)

    def strona(self, uczelnia, od=None, do=None, kursor=None, rozmiar=None):
        rozmiar = rozmiar or const.ROZMIAR_STRONY
        pozostale = list(self.obiekty)

        if od is not None:
            pozostale = [o for o in pozostale if getattr(o, ADNOTACJA_TS) >= od]
        if do is not None:
            pozostale = [o for o in pozostale if getattr(o, ADNOTACJA_TS) <= do]
        if kursor is not None:
            granica = self._klucz_kursora(kursor)
            pozostale = [o for o in pozostale if self._klucz(o) > granica]

        partia = pozostale[:rozmiar]
        if len(pozostale) > rozmiar:
            ostatni = partia[-1]
            return partia, Kursor(
                slug=identyfikatory.slug_dla(ostatni),
                ts=na_datestamp(getattr(ostatni, ADNOTACJA_TS)),
                pk=ostatni.pk,
            )
        return partia, None

    def pojedynczy(self, uczelnia, model, pk):
        for obiekt in self.obiekty:
            if type(obiekt) is model and obiekt.pk == pk:
                return obiekt
        return None

    def zbiory_widocznosci(self, uczelnia, obiekty):
        return ZbioryWidocznosci()

    def najstarszy_datestamp(self, uczelnia):
        if not self.obiekty:
            return None
        return min(getattr(o, ADNOTACJA_TS) for o in self.obiekty)


def _fikcyjny_serializer(obiekt, ctx):
    element = etree.Element(f"{{{const.NS_CERIF}}}Encja")
    element.set("id", identyfikatory.zbuduj(ctx.namespace, obiekt))
    return element


def _fikcyjny_service(uczelnia, ctx):
    element = etree.Element(f"{{{const.NS_CERIF}}}Service")
    element.set("id", identyfikatory.zbuduj(ctx.namespace, uczelnia))
    return element


# -- fixture'y -----------------------------------------------------------


@pytest.fixture
def uczelnia():
    return Uczelnia(
        pk=1,
        nazwa="Uniwersytet Testowy",
        skrot="UT",
        oai_identyfikator_repozytorium=NAMESPACE,
    )


@pytest.fixture
def publikacje():
    return [
        _z_datestampem(
            Wydawnictwo_Ciagle(pk=numer, tytul_oryginalny=f"Praca {numer}"), numer
        )
        for numer in (1, 2, 3)
    ]


@pytest.fixture
def rejestr(monkeypatch, uczelnia, publikacje):
    mapa = {
        const.SET_PUBLICATIONS: FikcyjnyProvider(
            const.SET_PUBLICATIONS, [Wydawnictwo_Ciagle], publikacje
        ),
        const.SET_PRODUCTS: ProviderPusty(),
        const.SET_PATENTS: FikcyjnyProvider(
            const.SET_PATENTS,
            [Patent],
            [_z_datestampem(Patent(pk=30, tytul_oryginalny="Patent"), 4)],
        ),
        const.SET_PERSONS: FikcyjnyProvider(
            const.SET_PERSONS,
            [Autor],
            [_z_datestampem(Autor(pk=10, nazwisko="Kowalski", imiona="Jan"), 5)],
        ),
        const.SET_ORGUNITS: FikcyjnyProvider(
            const.SET_ORGUNITS,
            [Jednostka, Uczelnia],
            [_z_datestampem(Jednostka(pk=20, nazwa="Katedra", skrot="KAT"), 6)],
        ),
        const.SET_PROJECTS: ProviderPusty(),
        const.SET_FUNDING: ProviderPusty(),
        const.SET_EVENTS: FikcyjnyProvider(
            const.SET_EVENTS,
            [Konferencja],
            [_z_datestampem(Konferencja(pk=40, nazwa="Zjazd"), 7)],
        ),
        const.SET_EQUIPMENTS: ProviderPusty(),
    }
    monkeypatch.setattr(czasowniki, "rejestr_providerow", lambda: mapa)
    return mapa


@pytest.fixture(autouse=True)
def serializery(monkeypatch):
    monkeypatch.setattr(czasowniki, "serializer_dla", lambda slug: _fikcyjny_serializer)
    monkeypatch.setattr(czasowniki, "serializer_service", lambda: _fikcyjny_service)


# -- pomocnicze ----------------------------------------------------------


def wykonaj(uczelnia, **argumenty):
    return czasowniki.odpowiedz(czasowniki.Zadanie(uczelnia, BASE_URL, argumenty))


def kod_bledu(korzen):
    element = korzen.find(f"{{{NS_PMH}}}error")
    return None if element is None else element.get("code")


def znajdz(korzen, *nazwy):
    sciezka = "/".join(f"{{{NS_PMH}}}{nazwa}" for nazwa in nazwy)
    return korzen.findall(sciezka)


def tekst(korzen, *nazwy):
    znalezione = znajdz(korzen, *nazwy)
    assert znalezione, f"Brak elementu {nazwy}"
    return znalezione[0].text


# -- koperta -------------------------------------------------------------


def test_koperta_ma_response_date_i_request(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Identify")

    assert korzen.tag == f"{{{NS_PMH}}}OAI-PMH"
    dzieci = [etree.QName(dziecko).localname for dziecko in korzen]
    assert dzieci[:2] == ["responseDate", "request"]
    datetime.datetime.strptime(tekst(korzen, "responseDate"), const.FORMAT_DATESTAMP)
    assert tekst(korzen, "request") == BASE_URL
    assert znajdz(korzen, "request")[0].get("verb") == "Identify"


# -- Identify ------------------------------------------------------------


def test_identify(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Identify")

    assert kod_bledu(korzen) is None
    assert tekst(korzen, "Identify", "repositoryName") == "Uniwersytet Testowy"
    assert tekst(korzen, "Identify", "baseURL") == BASE_URL
    assert tekst(korzen, "Identify", "protocolVersion") == "2.0"
    assert tekst(korzen, "Identify", "deletedRecord") == const.DELETED_RECORD
    assert tekst(korzen, "Identify", "granularity") == const.GRANULARITY
    assert tekst(korzen, "Identify", "adminEmail")

    # Kolejność elementów jest narzucona przez XSD OAI-PMH.
    identify = znajdz(korzen, "Identify")[0]
    assert [etree.QName(dziecko).localname for dziecko in identify] == [
        "repositoryName",
        "baseURL",
        "protocolVersion",
        "adminEmail",
        "earliestDatestamp",
        "deletedRecord",
        "granularity",
        "description",
    ]


def test_identify_earliest_datestamp_z_najstarszego_setu(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Identify")

    # Najstarszy rekord w atrapie to publikacja z 1 stycznia.
    assert tekst(korzen, "Identify", "earliestDatestamp") == "2026-01-01T12:00:00Z"


def test_identify_ma_rekord_service_w_description(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Identify")

    opis = znajdz(korzen, "Identify", "description")[0]
    assert len(opis) == 1
    assert opis[0].tag == f"{{{const.NS_CERIF}}}Service"


def test_identify_odrzuca_dodatkowe_argumenty(uczelnia, rejestr):
    assert kod_bledu(wykonaj(uczelnia, verb="Identify", set="x")) == "badArgument"


# -- ListMetadataFormats -------------------------------------------------


def test_list_metadata_formats(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListMetadataFormats")

    assert (
        tekst(korzen, "ListMetadataFormats", "metadataFormat", "metadataPrefix")
        == const.METADATA_PREFIX
    )
    assert (
        tekst(korzen, "ListMetadataFormats", "metadataFormat", "metadataNamespace")
        == const.NS_CERIF
    )
    assert tekst(korzen, "ListMetadataFormats", "metadataFormat", "schema")


def test_list_metadata_formats_dla_nieznanego_identyfikatora(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListMetadataFormats", identifier="oai:x:y/zz-1")
    assert kod_bledu(korzen) == "idDoesNotExist"


# -- ListSets ------------------------------------------------------------


def test_list_sets_wszystkie_dziewiec(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListSets")

    specyfikacje = [el.text for el in znajdz(korzen, "ListSets", "set", "setSpec")]
    nazwy = [el.text for el in znajdz(korzen, "ListSets", "set", "setName")]

    assert specyfikacje == list(const.WSZYSTKIE_SETY)
    assert nazwy == [const.OPISY_SETOW[s] for s in const.WSZYSTKIE_SETY]


def test_list_sets_odrzuca_resumption_token(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListSets", resumptionToken="cokolwiek")
    assert kod_bledu(korzen) == "badResumptionToken"


# -- ListIdentifiers / ListRecords ---------------------------------------


def test_list_identifiers(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListIdentifiers",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PUBLICATIONS,
    )

    identyfikatory_ = [
        el.text for el in znajdz(korzen, "ListIdentifiers", "header", "identifier")
    ]
    assert identyfikatory_ == [
        f"oai:{NAMESPACE}:Publications/wc-{numer}" for numer in (1, 2, 3)
    ]

    sety = [el.text for el in znajdz(korzen, "ListIdentifiers", "header", "setSpec")]
    assert set(sety) == {const.SET_PUBLICATIONS}

    datestampy = [
        el.text for el in znajdz(korzen, "ListIdentifiers", "header", "datestamp")
    ]
    assert datestampy[0] == "2026-01-01T12:00:00Z"


def test_list_records_zawiera_metadane(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PUBLICATIONS,
    )

    rekordy = znajdz(korzen, "ListRecords", "record")
    assert len(rekordy) == 3
    for rekord in rekordy:
        metadane = rekord.find(f"{{{NS_PMH}}}metadata")
        assert len(metadane) == 1
        assert metadane[0].tag == f"{{{const.NS_CERIF}}}Encja"


def test_list_identifiers_bez_setu_obejmuje_wszystkie_sety(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia, verb="ListIdentifiers", metadataPrefix=const.METADATA_PREFIX
    )

    sety = [el.text for el in znajdz(korzen, "ListIdentifiers", "header", "setSpec")]
    assert set(sety) == {
        const.SET_PUBLICATIONS,
        const.SET_PATENTS,
        const.SET_PERSONS,
        const.SET_ORGUNITS,
        const.SET_EVENTS,
    }
    # Sety wyczerpywane są sekwencyjnie, w kolejności z const.WSZYSTKIE_SETY.
    assert sety == sorted(sety, key=lambda s: const.WSZYSTKIE_SETY.index(s))


def test_list_identifiers_filtruje_zakresem_dat(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListIdentifiers",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PUBLICATIONS,
        **{"from": "2026-01-02T00:00:00Z", "until": "2026-01-02T23:59:59Z"},
    )

    identyfikatory_ = [
        el.text for el in znajdz(korzen, "ListIdentifiers", "header", "identifier")
    ]
    assert identyfikatory_ == [f"oai:{NAMESPACE}:Publications/wc-2"]


def test_stronicowanie_z_resumption_tokenem(monkeypatch, uczelnia, rejestr):
    monkeypatch.setattr(const, "ROZMIAR_STRONY", 2)

    pierwsza = wykonaj(
        uczelnia,
        verb="ListIdentifiers",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PUBLICATIONS,
    )
    pierwsze = [
        el.text for el in znajdz(pierwsza, "ListIdentifiers", "header", "identifier")
    ]
    token = tekst(pierwsza, "ListIdentifiers", "resumptionToken")

    assert len(pierwsze) == 2
    assert token

    druga = wykonaj(uczelnia, verb="ListIdentifiers", resumptionToken=token)
    drugie = [
        el.text for el in znajdz(druga, "ListIdentifiers", "header", "identifier")
    ]

    assert drugie == [f"oai:{NAMESPACE}:Publications/wc-3"]
    # Lista niekompletna domyka się pustym tokenem.
    assert znajdz(druga, "ListIdentifiers", "resumptionToken")[0].text is None
    assert set(pierwsze).isdisjoint(drugie)


def test_stronicowanie_przechodzi_miedzy_setami(monkeypatch, uczelnia, rejestr):
    monkeypatch.setattr(const, "ROZMIAR_STRONY", 3)

    pierwsza = wykonaj(
        uczelnia, verb="ListIdentifiers", metadataPrefix=const.METADATA_PREFIX
    )
    token = tekst(pierwsza, "ListIdentifiers", "resumptionToken")
    druga = wykonaj(uczelnia, verb="ListIdentifiers", resumptionToken=token)

    sety = [el.text for el in znajdz(druga, "ListIdentifiers", "header", "setSpec")]
    assert sety == [
        const.SET_PATENTS,
        const.SET_PERSONS,
        const.SET_ORGUNITS,
        const.SET_EVENTS,
    ]


def test_no_records_match_dla_pustego_setu(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PROJECTS,
    )
    assert kod_bledu(korzen) == "noRecordsMatch"


def test_no_records_match_dla_nieznanego_setu(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        set="nie_ma_takiego_setu",
    )
    assert kod_bledu(korzen) == "noRecordsMatch"


# -- GetRecord -----------------------------------------------------------


def test_get_record(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier=f"oai:{NAMESPACE}:Publications/wc-2",
        metadataPrefix=const.METADATA_PREFIX,
    )

    assert kod_bledu(korzen) is None
    assert (
        tekst(korzen, "GetRecord", "record", "header", "identifier")
        == f"oai:{NAMESPACE}:Publications/wc-2"
    )
    assert (
        tekst(korzen, "GetRecord", "record", "header", "setSpec")
        == const.SET_PUBLICATIONS
    )
    metadane = znajdz(korzen, "GetRecord", "record", "metadata")[0]
    assert metadane[0].tag == f"{{{const.NS_CERIF}}}Encja"


def test_get_record_smieciowy_identyfikator_to_blad_protokolu(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier="rm -rf /",
        metadataPrefix=const.METADATA_PREFIX,
    )
    assert kod_bledu(korzen) == "idDoesNotExist"


def test_get_record_nieistniejacy_pk(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier=f"oai:{NAMESPACE}:Publications/wc-999",
        metadataPrefix=const.METADATA_PREFIX,
    )
    assert kod_bledu(korzen) == "idDoesNotExist"


def test_get_record_obcy_namespace(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier="oai:inne.repozytorium.pl:Publications/wc-1",
        metadataPrefix=const.METADATA_PREFIX,
    )
    assert kod_bledu(korzen) == "idDoesNotExist"


def test_get_record_bez_metadata_prefix(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia, verb="GetRecord", identifier=f"oai:{NAMESPACE}:Publications/wc-1"
    )
    assert kod_bledu(korzen) == "badArgument"


# -- błędy protokołu -----------------------------------------------------


def test_bad_verb_brak_czasownika(uczelnia, rejestr):
    korzen = wykonaj(uczelnia)
    assert kod_bledu(korzen) == "badVerb"


def test_bad_verb_nieznany_czasownik(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Frobnicate")
    assert kod_bledu(korzen) == "badVerb"


def test_bad_verb_nie_echuje_argumentow(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="Frobnicate", set="cokolwiek")
    zadanie = znajdz(korzen, "request")[0]

    # Protokół zabrania echowania atrybutów przy badVerb i badArgument.
    assert zadanie.attrib == {}
    assert zadanie.text == BASE_URL


def test_bad_argument_echuje_baseurl_bez_atrybutow(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListRecords", nieznany="1")
    assert kod_bledu(korzen) == "badArgument"
    assert znajdz(korzen, "request")[0].attrib == {}


def test_bad_argument_brak_metadata_prefix(uczelnia, rejestr):
    assert kod_bledu(wykonaj(uczelnia, verb="ListRecords")) == "badArgument"


def test_bad_argument_resumption_token_nie_laczy_sie_z_innymi(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        resumptionToken="cokolwiek",
        set=const.SET_PUBLICATIONS,
    )
    assert kod_bledu(korzen) == "badArgument"


def test_bad_argument_zla_data(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        **{"from": "wczoraj"},
    )
    assert kod_bledu(korzen) == "badArgument"


def test_bad_argument_from_pozniejsze_niz_until(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        **{"from": "2026-02-01T00:00:00Z", "until": "2026-01-01T00:00:00Z"},
    )
    assert kod_bledu(korzen) == "badArgument"


def test_bad_argument_rozna_granularnosc_dat(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        **{"from": "2026-01-01", "until": "2026-02-01T00:00:00Z"},
    )
    assert kod_bledu(korzen) == "badArgument"


def test_bad_argument_powtorzony_argument(uczelnia, rejestr):
    from django.http import QueryDict

    argumenty = QueryDict("verb=ListRecords&metadataPrefix=a&metadataPrefix=b")
    korzen = czasowniki.odpowiedz(czasowniki.Zadanie(uczelnia, BASE_URL, argumenty))
    assert kod_bledu(korzen) == "badArgument"


@pytest.mark.parametrize("czasownik", ["ListRecords", "ListIdentifiers"])
def test_cannot_disseminate_format(uczelnia, rejestr, czasownik):
    korzen = wykonaj(uczelnia, verb=czasownik, metadataPrefix="oai_dc")
    assert kod_bledu(korzen) == "cannotDisseminateFormat"


def test_cannot_disseminate_format_get_record(uczelnia, rejestr):
    korzen = wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier=f"oai:{NAMESPACE}:Publications/wc-1",
        metadataPrefix="oai_dc",
    )
    assert kod_bledu(korzen) == "cannotDisseminateFormat"


def test_element_bledu_odrzuca_kod_spoza_specyfikacji():
    with pytest.raises(ValueError):
        bledy.element_bledu("zupelnieInnyKod")


def test_wszystkie_kody_protokolu_maja_wyjatek():
    assert set(bledy.WYJATKI_WG_KODU) == set(bledy.WSZYSTKIE_KODY)


# -- resumption tokeny ---------------------------------------------------


def test_token_round_trip():
    kursor = Kursor(slug="wc", ts="2026-01-02T12:00:00Z", pk=17)
    token = tokeny.zakoduj(
        kursor,
        const.SET_PUBLICATIONS,
        const.METADATA_PREFIX,
        od="2026-01-01T00:00:00Z",
        do=None,
    )

    dane = tokeny.odkoduj(token)

    assert dane == {
        "set": const.SET_PUBLICATIONS,
        "prefix": const.METADATA_PREFIX,
        "od": "2026-01-01T00:00:00Z",
        "do": None,
        "slug": "wc",
        "ts": "2026-01-02T12:00:00Z",
        "pk": 17,
    }
    assert tokeny.kursor_z(dane) == kursor


def test_token_bez_setu_oznacza_harvest_wszystkich_setow():
    token = tokeny.zakoduj(
        Kursor(slug="au", ts=const.EPOKA, pk=0), None, const.METADATA_PREFIX
    )
    assert tokeny.odkoduj(token)["set"] is None


def test_token_wymaga_sluga():
    with pytest.raises(ValueError):
        tokeny.zakoduj(
            Kursor(slug="", ts=const.EPOKA, pk=1),
            const.SET_PUBLICATIONS,
            const.METADATA_PREFIX,
        )


def test_token_wygasly(monkeypatch):
    token = tokeny.zakoduj(
        Kursor(slug="wc", ts=const.EPOKA, pk=1),
        const.SET_PUBLICATIONS,
        const.METADATA_PREFIX,
    )
    monkeypatch.setattr(const, "TOKEN_TTL", -1)

    with pytest.raises(bledy.BlednyResumptionToken):
        tokeny.odkoduj(token)


def test_token_zerwany_podpis():
    token = tokeny.zakoduj(
        Kursor(slug="wc", ts=const.EPOKA, pk=1),
        const.SET_PUBLICATIONS,
        const.METADATA_PREFIX,
    )
    zepsuty = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")

    with pytest.raises(bledy.BlednyResumptionToken):
        tokeny.odkoduj(zepsuty)


def test_token_z_inna_sola_odrzucony():
    # Bez podpisu token byłby wektorem wstrzykiwania parametrów zapytania.
    obcy = signing.dumps(
        {
            "set": const.SET_PUBLICATIONS,
            "prefix": const.METADATA_PREFIX,
            "od": None,
            "do": None,
            "slug": "wc",
            "ts": const.EPOKA,
            "pk": 1,
        },
        salt="zupelnie.inna.sol",
    )
    with pytest.raises(bledy.BlednyResumptionToken):
        tokeny.odkoduj(obcy)


def test_token_z_niepelnym_ladunkiem():
    okrojony = signing.dumps({"slug": "wc"}, salt=const.TOKEN_SALT)
    with pytest.raises(bledy.BlednyResumptionToken):
        tokeny.odkoduj(okrojony)


def test_token_pusty():
    with pytest.raises(bledy.BlednyResumptionToken):
        tokeny.odkoduj("")


def test_zly_token_w_czasowniku_daje_blad_protokolu(uczelnia, rejestr):
    korzen = wykonaj(uczelnia, verb="ListRecords", resumptionToken="nie-token")
    assert kod_bledu(korzen) == "badResumptionToken"


def test_token_ze_slugiem_spoza_setu(uczelnia, rejestr):
    token = tokeny.zakoduj(
        Kursor(slug="au", ts=const.EPOKA, pk=0),
        const.SET_PUBLICATIONS,
        const.METADATA_PREFIX,
    )
    korzen = wykonaj(uczelnia, verb="ListIdentifiers", resumptionToken=token)
    assert kod_bledu(korzen) == "badResumptionToken"


def test_token_z_obcym_prefiksem(uczelnia, rejestr):
    token = tokeny.zakoduj(
        Kursor(slug="wc", ts=const.EPOKA, pk=0), const.SET_PUBLICATIONS, "oai_dc"
    )
    korzen = wykonaj(uczelnia, verb="ListRecords", resumptionToken=token)
    assert kod_bledu(korzen) == "badResumptionToken"


# -- błąd serializacji pojedynczego rekordu ------------------------------


def _serializer_wybuchajacy_na(pk):
    def serializuj(obiekt, ctx):
        if obiekt.pk == pk:
            raise RuntimeError("zepsuty wiersz")
        return _fikcyjny_serializer(obiekt, ctx)

    return serializuj


def test_zepsuty_rekord_jest_pomijany_a_harvest_leci_dalej(
    monkeypatch, uczelnia, rejestr
):
    monkeypatch.setattr(
        czasowniki, "serializer_dla", lambda slug: _serializer_wybuchajacy_na(2)
    )
    zgloszenia = []
    monkeypatch.setattr(
        czasowniki.rollbar, "report_exc_info", lambda *a, **kw: zgloszenia.append(1)
    )

    korzen = wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_PUBLICATIONS,
    )

    identyfikatory_ = [
        el.text
        for el in znajdz(korzen, "ListRecords", "record", "header", "identifier")
    ]
    assert identyfikatory_ == [
        f"oai:{NAMESPACE}:Publications/wc-1",
        f"oai:{NAMESPACE}:Publications/wc-3",
    ]
    assert len(zgloszenia) == 1


def test_zepsuty_rekord_podnosi_wyjatek_gdy_wlaczone_przerywanie(
    monkeypatch, settings, uczelnia, rejestr
):
    settings.CERIF_EXPORT_PRZERYWAJ_NA_BLEDZIE = True
    monkeypatch.setattr(
        czasowniki, "serializer_dla", lambda slug: _serializer_wybuchajacy_na(2)
    )
    monkeypatch.setattr(czasowniki.rollbar, "report_exc_info", lambda *a, **kw: None)

    with pytest.raises(RuntimeError):
        wykonaj(
            uczelnia,
            verb="ListRecords",
            metadataPrefix=const.METADATA_PREFIX,
            set=const.SET_PUBLICATIONS,
        )


def test_zepsuty_rekord_w_get_record_nie_jest_pomijany(monkeypatch, uczelnia, rejestr):
    # Pominięcie jedynego rekordu dałoby odpowiedź niezgodną ze schematem.
    monkeypatch.setattr(
        czasowniki, "serializer_dla", lambda slug: _serializer_wybuchajacy_na(2)
    )
    monkeypatch.setattr(czasowniki.rollbar, "report_exc_info", lambda *a, **kw: None)

    with pytest.raises(RuntimeError):
        wykonaj(
            uczelnia,
            verb="GetRecord",
            identifier=f"oai:{NAMESPACE}:Publications/wc-2",
            metadataPrefix=const.METADATA_PREFIX,
        )


# -- serializacja do bajtów ----------------------------------------------


def test_na_xml_zwraca_dokument_z_deklaracja(uczelnia, rejestr):
    dokument = czasowniki.na_xml(wykonaj(uczelnia, verb="ListSets"))

    assert dokument.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert b"openaire_cris_publications" in dokument
