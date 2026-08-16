"""Instytucje finansujące jako CERIF ``OrgUnit`` + fundament eksportu.

``Funding/Funder`` i ``Project/Funded/By`` wskazują na OrgUnit-a, więc
grantodawca **musi** wyjść w secie ``openaire_cris_orgunits`` — inaczej
referencja jest wisząca i walidator odrzuca cały harvest (kontrola 5a).

Zakres modułu to fundament z Taska 4 planu: stałe typów, rejestr
identyfikatorów, słownik typów finansowania i sam eksport grantodawcy.
"""

import pytest
from django.contrib.sites.models import Site
from lxml import etree
from model_bakery import baker

from bpp.models import (
    Finansowanie,
    Instytucja_Finansujaca,
    Jednostka,
    Projekt,
    Uczelnia,
)
from cerif_export import const, identyfikatory
from cerif_export.cerif import orgunit, wspolne
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.oai import czasowniki
from cerif_export.providers import provider_dla_modelu, provider_dla_setu
from cerif_export.providers.jednostki import ProviderJednostek
from cerif_export.slowniki import typy_finansowania
from cerif_export.tests.pomocnicze import strona_zywych

NAMESPACE = "cerif.example.org"


def q(nazwa):
    """Nazwa elementu z przestrzeni nazw profilu."""
    return f"{{{const.NS_CERIF}}}{nazwa}"


def kontekst(uczelnia, obiekty):
    provider = provider_dla_setu(const.SET_ORGUNITS)
    return KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )


def zbuduj_finansowanie(jednostka, instytucja, **kwargs):
    projekt = baker.make(Projekt, jednostka=jednostka)
    return baker.make(Finansowanie, projekt=projekt, instytucja=instytucja, **kwargs)


# -- stałe i rejestr identyfikatorów -------------------------------------


def test_stale_typow_projektu_i_finansowania():
    # Człon typu w identyfikatorze OAI to nazwa elementu XSD w liczbie
    # mnogiej — patrz reguła walidatora opisana w ``cerif/wspolne.py``.
    assert const.TYP_PROJECT == "Projects"
    assert const.TYP_FUNDING == "Fundings"


def test_schematy_klasyfikacji_wlasnych_sa_uri():
    for schemat in (const.SCHEMAT_STATUSU_PROJEKTU, const.SCHEMAT_DYSCYPLIN):
        assert schemat.startswith("https://")


def test_rejestr_zna_nowe_modele():
    assert identyfikatory.slug_dla(Projekt) == "pj"
    assert identyfikatory.slug_dla(Finansowanie) == "fn"
    assert identyfikatory.slug_dla(Instytucja_Finansujaca) == "if"

    # Grantodawca jest OrgUnit-em, nie osobnym typem encji.
    assert identyfikatory.typ_dla(Instytucja_Finansujaca) == const.TYP_ORGUNIT
    assert identyfikatory.typ_dla(Projekt) == const.TYP_PROJECT
    assert identyfikatory.typ_dla(Finansowanie) == const.TYP_FUNDING


def test_identyfikator_grantodawcy_daje_sie_rozebrac():
    oai_id = identyfikatory.zbuduj_z_czesci(NAMESPACE, "if", 7)
    assert oai_id == f"oai:{NAMESPACE}:OrgUnits/if-7"
    assert identyfikatory.rozbierz(oai_id) == (
        NAMESPACE,
        Instytucja_Finansujaca,
        7,
    )


def test_slug_grantodawcy_ma_serializer():
    # Bez wpisu w ``MODULY_SERIALIZERA`` ``ListRecords`` dla setu OrgUnits
    # wywaliłby się na pierwszym grantodawcy.
    assert czasowniki.serializer_dla("if") is orgunit.serializuj


# -- słownik typów finansowania ------------------------------------------


def test_slownik_typow_ma_komplet_wartosci():
    # Osiem wartości z ``vocabularies/openaire_funding_types.xsd``.
    assert len(typy_finansowania.TYPY) == 8


def test_uri_typu_dla_kazdej_wartosci_modelu():
    for wartosc, _etykieta in Finansowanie.TYPY:
        uri = typy_finansowania.uri_typu(wartosc)
        assert uri is not None, wartosc
        assert uri == f"{typy_finansowania.SCHEMAT}#{wartosc}"


@pytest.mark.parametrize("wejscie", [None, "", "Nieznany", "grant"])
def test_uri_typu_odrzuca_nieznane(wejscie):
    assert typy_finansowania.uri_typu(wejscie) is None


# -- provider ------------------------------------------------------------


@pytest.mark.django_db
def test_funder_bez_finansowania_nie_wychodzi(uczelnia, jednostka):
    baker.make(Instytucja_Finansujaca, nazwa="Niepowiązana")

    provider = ProviderJednostek()
    assert not provider.queryset(uczelnia, Instytucja_Finansujaca).exists()


@pytest.mark.django_db
def test_funder_z_finansowaniem_wychodzi(uczelnia, jednostka):
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN", akronim="NCN")
    zbuduj_finansowanie(jednostka, instytucja)

    provider = ProviderJednostek()
    assert list(provider.queryset(uczelnia, Instytucja_Finansujaca)) == [instytucja]


@pytest.mark.django_db
def test_funder_wychodzi_raz_mimo_wielu_finansowan(uczelnia, jednostka):
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN")
    zbuduj_finansowanie(jednostka, instytucja)
    zbuduj_finansowanie(jednostka, instytucja)

    provider = ProviderJednostek()
    assert list(provider.queryset(uczelnia, Instytucja_Finansujaca)) == [instytucja]

    # Także po przepuszczeniu przez stronicowanie keyset — ``DISTINCT``
    # musi przeżyć adnotację ``_cerif_ts`` i ``ORDER BY`` po niej, inaczej
    # harvester dostałby ten sam rekord tyle razy, ile jest finansowań.
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=1000)
    assert [o for o in obiekty if isinstance(o, Instytucja_Finansujaca)] == [instytucja]


@pytest.mark.django_db
def test_funder_cudzej_uczelni_nie_wychodzi(uczelnia, jednostka):
    """Grantodawca innego tenanta nie może wyciec do naszego harvestu."""
    obca_uczelnia = Uczelnia.objects.create(
        nazwa="Obca uczelnia",
        skrot="OBC",
        site=Site.objects.create(domain="obca.example.org", name="obca"),
    )
    obca_jednostka = Jednostka.objects.create(
        nazwa="Obca jednostka", skrot="OJE", uczelnia=obca_uczelnia
    )
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="Obcy grantodawca")
    zbuduj_finansowanie(obca_jednostka, instytucja)

    provider = ProviderJednostek()
    assert not provider.queryset(uczelnia, Instytucja_Finansujaca).exists()


@pytest.mark.django_db
def test_funder_jest_w_secie_orgunits(uczelnia, jednostka):
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN")
    zbuduj_finansowanie(jednostka, instytucja)

    provider = provider_dla_setu(const.SET_ORGUNITS)
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=1000)
    assert instytucja in obiekty

    assert provider_dla_modelu(Instytucja_Finansujaca) is provider


@pytest.mark.django_db
def test_pojedynczy_grantodawca_po_identyfikatorze(uczelnia, jednostka):
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN")
    zbuduj_finansowanie(jednostka, instytucja)

    provider = provider_dla_setu(const.SET_ORGUNITS)
    assert (
        provider.pojedynczy(uczelnia, Instytucja_Finansujaca, instytucja.pk)
        == instytucja
    )


# -- serializacja --------------------------------------------------------


@pytest.mark.django_db
def test_orgunit_grantodawcy_ma_nazwy_i_akronim(uczelnia, jednostka):
    instytucja = baker.make(
        Instytucja_Finansujaca,
        nazwa="Narodowe Centrum Nauki",
        nazwa_en="National Science Centre",
        akronim="NCN",
        strona_www="https://ncn.gov.pl/",
    )
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))

    assert el.get("id") == f"OrgUnits/if-{instytucja.pk}"
    assert el.find(q("Acronym")).text == "NCN"
    nazwy = el.findall(q("Name"))
    assert [n.text for n in nazwy] == [
        "Narodowe Centrum Nauki",
        "National Science Centre",
    ]
    # Nazwa polska bez ``xml:lang`` — dokładnie tak, jak wychodzi
    # z ``wspolne.osadz_orgunit``, żeby encja osadzona pozostała podzbiorem
    # pełnego rekordu (kontrola 5b walidatora).
    assert nazwy[0].get(wspolne.XML_LANG) is None
    assert nazwy[1].get(wspolne.XML_LANG) == "en"
    assert el.find(q("ElectronicAddress")).text == "https://ncn.gov.pl/"


@pytest.mark.django_db
def test_orgunit_grantodawcy_nie_ma_kraju(uczelnia, jednostka):
    # Sekwencja OrgUnit w profilu nie ma elementu Country — pole ``kraj``
    # zostaje danymi wewnętrznymi.
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN", kraj="PL")
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))
    assert el.find(q("Country")) is None
    assert "PL" not in etree.tostring(el, encoding="unicode")


@pytest.mark.django_db
def test_ror_i_fundref_ida_w_dedykowanych_elementach(uczelnia, jednostka):
    instytucja = baker.make(
        Instytucja_Finansujaca,
        nazwa="Narodowe Centrum Nauki",
        ror_id="https://ror.org/016f61126",
        fundref_id="501100004281",
    )
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))

    assert el.find(q("RORID")).text == "https://ror.org/016f61126"
    # ``FundRefID__Type`` wymaga pełnego DOI-a rejestru Crossrefa; w bazie
    # trzymamy sam numer.
    assert el.find(q("FundRefID")).text == "https://doi.org/10.13039/501100004281"

    # Kolejność wymuszona przez ``OrgUnitIdentifiers__Group``:
    # RORID przed FundRefID, oba przed generycznym Identifier.
    nazwy = [etree.QName(dziecko).localname for dziecko in el]
    assert nazwy.index("RORID") < nazwy.index("FundRefID")


@pytest.mark.django_db
def test_bledny_fundref_ladzie_w_generycznym_identifier(uczelnia, jednostka):
    instytucja = baker.make(
        Instytucja_Finansujaca, nazwa="Grantodawca", fundref_id="nie-numer"
    )
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))

    assert el.find(q("FundRefID")) is None
    identyfikator = el.find(q("Identifier"))
    assert identyfikator is not None
    assert identyfikator.text == "nie-numer"
    assert identyfikator.get("type") == orgunit.TYP_ID_FUNDREF


@pytest.mark.django_db
def test_pusty_grantodawca_serializuje_sie_bez_identyfikatorow(uczelnia, jednostka):
    instytucja = baker.make(
        Instytucja_Finansujaca,
        nazwa="Bez identyfikatorów",
        nazwa_en="",
        akronim="",
        ror_id="",
        fundref_id="",
        strona_www="",
    )
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))

    assert [etree.QName(dziecko).localname for dziecko in el] == ["Name"]


@pytest.mark.django_db
def test_orgunit_grantodawcy_zgodny_z_xsd(uczelnia, jednostka):
    from cerif_export.tests.test_serializery import sprawdz, zbuduj_schemat

    instytucja = baker.make(
        Instytucja_Finansujaca,
        nazwa="Narodowe Centrum Nauki",
        nazwa_en="National Science Centre",
        akronim="NCN",
        ror_id="https://ror.org/016f61126",
        fundref_id="501100004281",
        strona_www="https://ncn.gov.pl/",
    )
    zbuduj_finansowanie(jednostka, instytucja)

    el = orgunit.serializuj(instytucja, kontekst(uczelnia, [instytucja]))
    sprawdz(zbuduj_schemat(), el)


@pytest.mark.django_db
def test_grantodawca_wychodzi_z_harvestu_oai(uczelnia, jednostka):
    """Pełny ``ListRecords`` musi wydać rekord grantodawcy, nie wywalić się.

    Sam queryset providera to za mało: bez wpisu w ``MODULY_SERIALIZERA``
    warstwa OAI podnosi ``BlednyIdentyfikator`` dopiero przy serializacji,
    czyli w produkcji, a nie w teście providera.
    """
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN", akronim="NCN")
    zbuduj_finansowanie(jednostka, instytucja)

    korzen = czasowniki.odpowiedz(
        czasowniki.Zadanie(
            uczelnia,
            "https://cerif.example.org/cerif-oai/",
            {
                "verb": "ListRecords",
                "metadataPrefix": const.METADATA_PREFIX,
                "set": const.SET_ORGUNITS,
            },
        )
    )

    bledy = [el for el in korzen.iter() if el.tag.endswith("}error")]
    assert not bledy, [el.get("code") for el in bledy]

    identyfikatory_naglowkow = {
        el.text for el in korzen.iter() if el.tag.endswith("}identifier") and el.text
    }
    oczekiwany = identyfikatory.zbuduj(uczelnia.oai_repository_identifier(), instytucja)
    assert oczekiwany in identyfikatory_naglowkow


@pytest.mark.django_db
def test_jednostka_serializuje_sie_bez_zmian(uczelnia, jednostka):
    """Rozszerzenie setu nie może ruszyć tego, co wychodzi dla jednostek."""
    el = orgunit.serializuj(jednostka, kontekst(uczelnia, [jednostka]))

    nazwa = el.find(q("Name"))
    assert nazwa.text == "Jednostka CERIF"
    assert nazwa.get(wspolne.XML_LANG) is None
    assert el.find(q("Acronym")).text == "JCE"
