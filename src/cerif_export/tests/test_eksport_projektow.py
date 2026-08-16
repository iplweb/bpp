"""Eksport setów ``openaire_cris_projects`` i ``openaire_cris_funding``.

Dwie encje profilu, które do tej pory były zadeklarowane, ale puste.
Najwięcej uwagi dostają tu trzy rzeczy, bo to one wychodzą dopiero pod
walidatorem OpenAIRE, a nie przy oglądaniu XML-a gołym okiem:

1. ``Project/Funded/By`` to **referencja** do OrgUnit-a grantodawcy, a
   ``Project/Funded/As`` to **osadzone pełne** ``<Funding>``;
2. każda referencja musi wskazywać na rekord obecny w harveście —
   stąd testy znikającego ``Team`` przy ``eksport_cerif_osoby=False``;
3. kolejność elementów wymuszona przez ``xs:sequence`` — sprawdzana
   wprost wobec XSD profilu.
"""

import decimal

import pytest
from django.contrib.sites.models import Site
from django.db import connection
from django.test.utils import CaptureQueriesContext
from lxml import etree
from model_bakery import baker

from bpp.models import (
    Dyscyplina_Naukowa,
    Finansowanie,
    Instytucja_Finansujaca,
    Jednostka,
    Projekt,
    Projekt_Autor,
    Uczelnia,
)
from cerif_export import const, identyfikatory
from cerif_export.cerif import funding as cerif_funding
from cerif_export.cerif import project as cerif_project
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.oai import czasowniki
from cerif_export.providers import provider_dla_modelu, provider_dla_setu
from cerif_export.slowniki import typy_finansowania
from cerif_export.tests.pomocnicze import strona_zywych

NAMESPACE = "cerif.example.org"
BASE_URL = "https://cerif.example.org/cerif-oai/"


def q(nazwa):
    """Nazwa elementu z przestrzeni nazw profilu CERIF."""
    return f"{{{const.NS_CERIF}}}{nazwa}"


def qt(nazwa):
    """Nazwa elementu ze słownika typów finansowania (własna przestrzeń)."""
    return f"{{{typy_finansowania.SCHEMAT}}}{nazwa}"


def nazwy_dzieci(el):
    """Lokalne nazwy dzieci elementu — w kolejności wystąpienia."""
    return [etree.QName(dziecko).localname for dziecko in el]


# -- budowanie danych ----------------------------------------------------


@pytest.fixture
def grantodawca(db):
    return baker.make(
        Instytucja_Finansujaca,
        nazwa="Narodowe Centrum Nauki",
        nazwa_en="National Science Centre",
        akronim="NCN",
        fundref_id="501100004281",
    )


@pytest.fixture
def projekt(jednostka):
    return baker.make(
        Projekt,
        tytul="Badanie czegoś ważnego",
        tytul_en="A study of something important",
        akronim="BCW",
        status=Projekt.STATUS_W_TRAKCIE,
        data_rozpoczecia="2024-01-01",
        data_zakonczenia="2026-12-31",
        abstrakt="Streszczenie projektu.",
        abstrakt_en="Project abstract.",
        jednostka=jednostka,
    )


def dodaj_finansowanie(projekt, grantodawca, **kwargs):
    kwargs.setdefault("typ", Finansowanie.TYP_GRANT)
    kwargs.setdefault("nazwa_programu", "OPUS 24")
    kwargs.setdefault("kwota", None)
    return baker.make(Finansowanie, projekt=projekt, instytucja=grantodawca, **kwargs)


# -- serializacja przez provider (jak w produkcji) -----------------------


def _serializuj(uczelnia, set_spec, model, obiekt, serializer):
    """Zserializuj obiekt dokładnie tak, jak robi to warstwa OAI.

    Obiekt jest **ponownie pobierany** przez queryset providera, żeby miał
    komplet ``select_related``/``prefetch_related``. Serializer nie ma
    prawa dotykać bazy, więc test na obiekcie z ``baker.make`` sprawdzałby
    co innego niż produkcja.
    """
    provider = provider_dla_setu(set_spec)
    zaladowany = provider.queryset(uczelnia, model).get(pk=obiekt.pk)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, [zaladowany]),
    )
    return serializer(zaladowany, kontekst)


def serializuj_projekt(uczelnia, projekt):
    return _serializuj(
        uczelnia, const.SET_PROJECTS, Projekt, projekt, cerif_project.serializuj
    )


def serializuj_finansowanie(uczelnia, finansowanie):
    return _serializuj(
        uczelnia,
        const.SET_FUNDING,
        Finansowanie,
        finansowanie,
        cerif_funding.serializuj,
    )


# -- rejestr providerów i serializerów -----------------------------------


def test_slugi_projektu_i_finansowania_maja_serializery():
    """Bez wpisu w ``MODULY_SERIALIZERA`` ``ListRecords`` wywala się
    dopiero w produkcji, na pierwszym rekordzie zwróconym przez provider."""
    assert czasowniki.serializer_dla("pj") is cerif_project.serializuj
    assert czasowniki.serializer_dla("fn") is cerif_funding.serializuj


@pytest.mark.django_db
def test_sety_projektow_i_finansowania_maja_wlasne_providery():
    assert provider_dla_setu(const.SET_PROJECTS).modele == [Projekt]
    assert provider_dla_setu(const.SET_FUNDING).modele == [Finansowanie]
    assert provider_dla_modelu(Projekt) is provider_dla_setu(const.SET_PROJECTS)
    assert provider_dla_modelu(Finansowanie) is provider_dla_setu(const.SET_FUNDING)


# -- provider: zakres tenanta --------------------------------------------


@pytest.mark.django_db
def test_projekt_wychodzi_w_secie(uczelnia, projekt):
    provider = provider_dla_setu(const.SET_PROJECTS)
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=100)
    assert list(obiekty) == [projekt]


@pytest.mark.django_db
def test_projekt_cudzej_uczelni_nie_wychodzi(uczelnia, projekt):
    obca = Uczelnia.objects.create(
        nazwa="Obca uczelnia",
        skrot="OBC",
        site=Site.objects.create(domain="obca.example.org", name="obca"),
    )
    obca_jednostka = Jednostka.objects.create(
        nazwa="Obca jednostka", skrot="OJE", uczelnia=obca
    )
    baker.make(Projekt, tytul="Cudzy projekt", jednostka=obca_jednostka)

    provider = provider_dla_setu(const.SET_PROJECTS)
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=100)
    assert list(obiekty) == [projekt]


@pytest.mark.django_db
def test_finansowanie_cudzej_uczelni_nie_wychodzi(uczelnia, projekt, grantodawca):
    nasze = dodaj_finansowanie(projekt, grantodawca)

    obca = Uczelnia.objects.create(
        nazwa="Obca uczelnia",
        skrot="OBC",
        site=Site.objects.create(domain="obca.example.org", name="obca"),
    )
    obca_jednostka = Jednostka.objects.create(
        nazwa="Obca jednostka", skrot="OJE", uczelnia=obca
    )
    obcy_projekt = baker.make(Projekt, tytul="Cudzy", jednostka=obca_jednostka)
    dodaj_finansowanie(obcy_projekt, grantodawca)

    provider = provider_dla_setu(const.SET_FUNDING)
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=100)
    assert list(obiekty) == [nasze]


@pytest.mark.django_db
def test_provider_odrzuca_obcy_model(uczelnia):
    for set_spec in (const.SET_PROJECTS, const.SET_FUNDING):
        with pytest.raises(identyfikatory.BlednyIdentyfikator):
            provider_dla_setu(set_spec).queryset(uczelnia, Jednostka)


@pytest.mark.django_db
def test_provider_bez_uczelni_podnosi_blad():
    """Cicha degradacja do pustej odpowiedzi udawałaby poprawny harvest."""
    for set_spec, model in (
        (const.SET_PROJECTS, Projekt),
        (const.SET_FUNDING, Finansowanie),
    ):
        with pytest.raises(ValueError):
            provider_dla_setu(set_spec).queryset(None, model)


# -- Funding -------------------------------------------------------------


@pytest.mark.django_db
def test_funding_ma_typ_zawsze(uczelnia, projekt, grantodawca):
    """``Funding/Type`` jest w profilu obowiązkowy i pochodzi ze słownika."""
    finansowanie = dodaj_finansowanie(projekt, grantodawca, typ=Finansowanie.TYP_AWARD)

    el = serializuj_finansowanie(uczelnia, finansowanie)

    typ = el.find(qt("Type"))
    assert typ is not None
    assert typ.text == typy_finansowania.uri_typu(Finansowanie.TYP_AWARD)
    assert nazwy_dzieci(el)[0] == "Type"


@pytest.mark.django_db
def test_funding_ma_identyfikator_rekordu(uczelnia, projekt, grantodawca):
    finansowanie = dodaj_finansowanie(projekt, grantodawca)
    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert el.get("id") == f"Fundings/fn-{finansowanie.pk}"


@pytest.mark.django_db
def test_nieznany_typ_finansowania_podnosi_blad(uczelnia, projekt, grantodawca):
    """Rekord bez ``Type`` byłby niepoprawny wobec XSD, więc lepiej głośno
    wywalić jeden rekord (Rollbar + pominięcie) niż wypuścić zepsuty."""
    finansowanie = dodaj_finansowanie(projekt, grantodawca)
    Finansowanie.objects.filter(pk=finansowanie.pk).update(typ="NieMaTakiego")

    with pytest.raises(ValueError):
        serializuj_finansowanie(uczelnia, finansowanie)


@pytest.mark.django_db
def test_kwota_tylko_przy_wlaczonym_przelaczniku(uczelnia, projekt, grantodawca):
    """``Uczelnia.eksport_cerif_kwoty`` domyślnie wyłączone — kwoty zostają
    w bazie do użytku wewnętrznego."""
    finansowanie = dodaj_finansowanie(
        projekt, grantodawca, kwota=decimal.Decimal("1234567.89"), waluta="PLN"
    )

    assert uczelnia.eksport_cerif_kwoty is False
    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert el.find(q("Amount")) is None

    uczelnia.eksport_cerif_kwoty = True
    uczelnia.save()

    el = serializuj_finansowanie(uczelnia, finansowanie)
    kwota = el.find(q("Amount"))
    assert kwota is not None
    assert kwota.text == "1234567.89"
    assert kwota.get("currency") == "PLN"


@pytest.mark.django_db
def test_kwota_bez_waluty_nie_wychodzi(uczelnia, projekt, grantodawca):
    """``cfAmount__Type`` wymaga atrybutu ``currency`` — kwota bez waluty
    nie ma jak wyjść poprawnie, więc nie wychodzi wcale."""
    uczelnia.eksport_cerif_kwoty = True
    uczelnia.save()
    finansowanie = dodaj_finansowanie(
        projekt, grantodawca, kwota=decimal.Decimal("100.00"), waluta=""
    )

    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert el.find(q("Amount")) is None


@pytest.mark.django_db
def test_grant_doi_idzie_w_dedykowanym_elemencie(uczelnia, projekt, grantodawca):
    finansowanie = dodaj_finansowanie(
        projekt, grantodawca, grant_doi="10.13039/501100004281-XYZ"
    )

    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert el.find(q("GrantDOI")).text == "10.13039/501100004281-XYZ"


@pytest.mark.django_db
def test_bledny_grant_doi_ladzie_w_generycznym_identifier(
    uczelnia, projekt, grantodawca
):
    """``DOI__SimpleType`` ma wzorzec — wartość spoza niego unieważniłaby
    cały rekord, więc odkładamy ją do generycznego ``Identifier``."""
    finansowanie = dodaj_finansowanie(projekt, grantodawca, grant_doi="to-nie-jest-doi")

    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert el.find(q("GrantDOI")) is None
    identyfikator = el.find(q("Identifier"))
    assert identyfikator.text == "to-nie-jest-doi"
    assert identyfikator.get("type") == cerif_funding.TYP_ID_DOI


@pytest.mark.django_db
def test_numer_umowy_jako_identyfikator(uczelnia, projekt, grantodawca):
    finansowanie = dodaj_finansowanie(
        projekt, grantodawca, numer_umowy="UMO-2024/45/B/NZ7/01234"
    )

    el = serializuj_finansowanie(uczelnia, finansowanie)
    numery = [
        el_.text
        for el_ in el.findall(q("Identifier"))
        if el_.get("type") == cerif_funding.TYP_ID_NUMER_UMOWY
    ]
    assert numery == ["UMO-2024/45/B/NZ7/01234"]


@pytest.mark.django_db
def test_funder_to_referencja_do_orgunita(uczelnia, projekt, grantodawca):
    """Po stronie ``Funding`` grantodawca siedzi w elemencie ``Funder``
    (nie ``FundedBy``) i jest osadzonym ``OrgUnit``-em z ``@id``."""
    finansowanie = dodaj_finansowanie(projekt, grantodawca)

    el = serializuj_finansowanie(uczelnia, finansowanie)

    funder = el.find(q("Funder"))
    assert funder is not None
    orgunit = funder.find(q("OrgUnit"))
    assert orgunit.get("id") == f"OrgUnits/if-{grantodawca.pk}"
    assert orgunit.find(q("Acronym")).text == "NCN"
    assert orgunit.find(q("Name")).text == "Narodowe Centrum Nauki"


@pytest.mark.django_db
def test_kolejnosc_elementow_finansowania(uczelnia, projekt, grantodawca):
    """``xs:sequence``: Type, Name, Amount, GrantDOI, Identifier, Funder."""
    uczelnia.eksport_cerif_kwoty = True
    uczelnia.save()
    finansowanie = dodaj_finansowanie(
        projekt,
        grantodawca,
        kwota=decimal.Decimal("1000.00"),
        waluta="PLN",
        grant_doi="10.13039/501100004281-XYZ",
        numer_umowy="UMO-1",
    )

    el = serializuj_finansowanie(uczelnia, finansowanie)
    assert nazwy_dzieci(el) == [
        "Type",
        "Name",
        "Amount",
        "GrantDOI",
        "Identifier",
        "Funder",
    ]


# -- Project -------------------------------------------------------------


@pytest.mark.django_db
def test_projekt_ma_tytuly_daty_i_status(uczelnia, projekt):
    el = serializuj_projekt(uczelnia, projekt)

    assert el.get("id") == f"Projects/pj-{projekt.pk}"
    assert el.find(q("Acronym")).text == "BCW"

    tytuly = el.findall(q("Title"))
    assert [t.text for t in tytuly] == [
        "Badanie czegoś ważnego",
        "A study of something important",
    ]
    from cerif_export.cerif.wspolne import XML_LANG

    assert [t.get(XML_LANG) for t in tytuly] == ["pl", "en"]

    assert el.find(q("StartDate")).text == "2024-01-01"
    assert el.find(q("EndDate")).text == "2026-12-31"

    status = el.find(q("Status"))
    assert status.get("scheme") == const.SCHEMAT_STATUSU_PROJEKTU
    assert status.text == (
        f"{const.SCHEMAT_STATUSU_PROJEKTU}/{Projekt.STATUS_W_TRAKCIE}"
    )


@pytest.mark.django_db
def test_projekt_ma_abstrakty_z_jezykiem(uczelnia, projekt):
    """``Project/Abstract`` to ``cfMLangAnyMixed__Type`` — ``xml:lang``
    jest tam **wymagany**, w odróżnieniu od abstraktów publikacji."""
    from cerif_export.cerif.wspolne import XML_LANG

    el = serializuj_projekt(uczelnia, projekt)
    abstrakty = el.findall(q("Abstract"))
    assert [a.text for a in abstrakty] == [
        "Streszczenie projektu.",
        "Project abstract.",
    ]
    assert [a.get(XML_LANG) for a in abstrakty] == ["pl", "en"]


@pytest.mark.django_db
def test_projekt_ma_koordynatora_z_jednostki(uczelnia, jednostka, projekt):
    el = serializuj_projekt(uczelnia, projekt)

    koordynator = el.find(f"{q('Consortium')}/{q('Coordinator')}")
    assert koordynator is not None
    orgunit = koordynator.find(q("OrgUnit"))
    assert orgunit.get("id") == f"OrgUnits/je-{jednostka.pk}"
    assert orgunit.find(q("Name")).text == "Jednostka CERIF"


@pytest.mark.django_db
def test_ukryta_jednostka_nie_daje_pustego_konsorcjum(uczelnia, jednostka, projekt):
    """Pusty ``<Consortium/>`` jest bezwartościowy, a ujawnienie nazwy
    jednostki z opt-outem byłoby wyciekiem — więc nie ma go wcale."""
    jednostka.nie_eksportuj_przez_api = True
    jednostka.save()

    el = serializuj_projekt(uczelnia, projekt)
    assert el.find(q("Consortium")) is None


@pytest.mark.django_db
def test_projekt_ma_dyscypliny_i_slowa_kluczowe(uczelnia, projekt):
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.5")
    projekt.dyscypliny.add(dyscyplina)
    projekt.slowa_kluczowe.add("onkologia")
    projekt.slowa_kluczowe_eng = ["oncology"]
    projekt.save()

    el = serializuj_projekt(uczelnia, projekt)

    subject = el.find(q("Subject"))
    assert subject.get("scheme") == const.SCHEMAT_DYSCYPLIN
    assert subject.text == f"{const.SCHEMAT_DYSCYPLIN}/3.5"

    assert {k.text for k in el.findall(q("Keyword"))} == {"onkologia", "oncology"}


@pytest.mark.django_db
def test_zespol_projektu_dzieli_sie_na_kierownika_i_czlonkow(
    uczelnia, projekt, fabryka_autorow
):
    kierownik = fabryka_autorow("Kierowniczka")
    wykonawca = fabryka_autorow("Wykonawca")
    Projekt_Autor.objects.create(
        projekt=projekt, autor=kierownik, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    Projekt_Autor.objects.create(
        projekt=projekt, autor=wykonawca, rola=Projekt_Autor.ROLA_WYKONAWCA
    )

    el = serializuj_projekt(uczelnia, projekt)
    zespol = el.find(q("Team"))
    assert zespol is not None

    # ``xs:sequence`` w ``Team``: PrincipalInvestigator przed Member.
    assert nazwy_dzieci(zespol) == ["PrincipalInvestigator", "Member"]

    pi = zespol.find(f"{q('PrincipalInvestigator')}/{q('Person')}")
    assert pi.get("id") == f"Persons/au-{kierownik.pk}"
    czlonek = zespol.find(f"{q('Member')}/{q('Person')}")
    assert czlonek.get("id") == f"Persons/au-{wykonawca.pk}"


@pytest.mark.django_db
def test_team_znika_przy_wylaczonym_eksporcie_osob(uczelnia, projekt, fabryka_autorow):
    """Przy ``eksport_cerif_osoby=False`` osób nie ma w harveście, więc
    referencja z ``Team`` byłaby wisząca — element nie powstaje wcale."""
    kierownik = fabryka_autorow("Kierowniczka")
    Projekt_Autor.objects.create(
        projekt=projekt, autor=kierownik, rola=Projekt_Autor.ROLA_KIEROWNIK
    )

    assert serializuj_projekt(uczelnia, projekt).find(q("Team")) is not None

    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    el = serializuj_projekt(uczelnia, projekt)
    assert el.find(q("Team")) is None
    assert "Kierowniczka" not in etree.tostring(el, encoding="unicode")


@pytest.mark.django_db
def test_autor_z_pokazuj_false_nie_trafia_do_zespolu(
    uczelnia, projekt, fabryka_autorow
):
    ukryty = fabryka_autorow("Ukryta", pokazuj=False)
    Projekt_Autor.objects.create(
        projekt=projekt, autor=ukryty, rola=Projekt_Autor.ROLA_WYKONAWCA
    )

    el = serializuj_projekt(uczelnia, projekt)
    assert el.find(q("Team")) is None


@pytest.mark.django_db
def test_funded_by_to_referencja_a_as_osadza_funding(uczelnia, projekt, grantodawca):
    """Dwie różne rzeczy w jednym kontenerze ``Funded``: ``By`` wskazuje na
    OrgUnit-a grantodawcy, ``As`` niesie pełne ``<Funding>``."""
    finansowanie = dodaj_finansowanie(projekt, grantodawca)

    el = serializuj_projekt(uczelnia, projekt)
    funded = el.find(q("Funded"))
    assert funded is not None
    assert nazwy_dzieci(funded) == ["By", "As"]

    orgunit = funded.find(f"{q('By')}/{q('OrgUnit')}")
    assert orgunit.get("id") == f"OrgUnits/if-{grantodawca.pk}"
    # Referencja, nie pełny rekord — bez identyfikatorów rejestrowych.
    assert orgunit.find(q("FundRefID")) is None

    osadzone = funded.find(f"{q('As')}/{q('Funding')}")
    assert osadzone is not None
    assert osadzone.get("id") == f"Fundings/fn-{finansowanie.pk}"
    assert osadzone.find(qt("Type")) is not None
    assert osadzone.find(f"{q('Funder')}/{q('OrgUnit')}") is not None


@pytest.mark.django_db
def test_kazde_finansowanie_daje_wlasny_funded(uczelnia, projekt, grantodawca):
    """``Funded`` ma ``maxOccurs="unbounded"`` — dwa źródła, dwa kontenery."""
    drugi = baker.make(Instytucja_Finansujaca, nazwa="Agencja Badań Medycznych")
    dodaj_finansowanie(projekt, grantodawca)
    dodaj_finansowanie(projekt, drugi, typ=Finansowanie.TYP_CONTRACT)

    el = serializuj_projekt(uczelnia, projekt)
    assert len(el.findall(q("Funded"))) == 2


@pytest.mark.django_db
def test_projekt_bez_finansowania_serializuje_sie(uczelnia, projekt):
    """``Funded`` ma ``minOccurs="0"`` — projekt bez finansowania jest
    poprawny i nie wolno go odsiewać z eksportu."""
    el = serializuj_projekt(uczelnia, projekt)
    assert el.find(q("Funded")) is None
    assert el.find(q("Title")) is not None

    provider = provider_dla_setu(const.SET_PROJECTS)
    obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=100)
    assert projekt in obiekty


@pytest.mark.django_db
def test_kolejnosc_elementow_projektu(uczelnia, projekt, grantodawca):
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.5")
    projekt.dyscypliny.add(dyscyplina)
    projekt.slowa_kluczowe.add("onkologia")
    dodaj_finansowanie(projekt, grantodawca)
    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=baker.make("bpp.Autor", nazwisko="Nowak", imiona="Jan"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )

    el = serializuj_projekt(uczelnia, projekt)
    kolejnosc = nazwy_dzieci(el)
    assert kolejnosc == [
        "Acronym",
        "Title",
        "Title",
        "StartDate",
        "EndDate",
        "Consortium",
        "Funded",
        "Subject",
        "Keyword",
        "Abstract",
        "Abstract",
        "Status",
    ]


@pytest.mark.django_db
def test_serializacja_strony_nie_rosnie_z_liczba_projektow(
    uczelnia, jednostka, grantodawca
):
    """Reguła „serializer nie dotyka bazy" — mierzona, nie deklarowana.

    Liczba zapytań na stronę harvestu musi być **stała**: cała robota
    siedzi w prefetchach providera i w prekomputowanych zbiorach
    widoczności. Gdy rośnie z liczbą projektów, znaczy że serializer
    dociąga coś sam — i pełny harvest zamienia się w N+1.
    """
    provider = provider_dla_setu(const.SET_PROJECTS)

    def zapytania_dla(ile_projektow):
        Projekt.objects.all().delete()
        for numer in range(ile_projektow):
            nowy = baker.make(Projekt, tytul=f"Projekt {numer}", jednostka=jednostka)
            dodaj_finansowanie(nowy, grantodawca)
            Projekt_Autor.objects.create(
                projekt=nowy,
                autor=baker.make("bpp.Autor", nazwisko=f"Nowak{numer}"),
                rola=Projekt_Autor.ROLA_KIEROWNIK,
            )

        with CaptureQueriesContext(connection) as licznik:
            obiekty, _ = strona_zywych(provider, uczelnia, rozmiar=100)
            obiekty = list(obiekty)
            kontekst = KontekstSerializacji(
                namespace=NAMESPACE,
                uczelnia=uczelnia,
                widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
            )
            for obiekt in obiekty:
                cerif_project.serializuj(obiekt, kontekst)
        return len(licznik.captured_queries)

    assert zapytania_dla(1) == zapytania_dla(5)


# -- zgodność z XSD ------------------------------------------------------


@pytest.mark.django_db
def test_projekt_i_finansowanie_zgodne_z_xsd(
    uczelnia, projekt, grantodawca, fabryka_autorow
):
    from cerif_export.tests.test_serializery import sprawdz, zbuduj_schemat

    uczelnia.eksport_cerif_kwoty = True
    uczelnia.save()

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.5")
    projekt.dyscypliny.add(dyscyplina)
    projekt.slowa_kluczowe.add("onkologia")
    projekt.slowa_kluczowe_eng = ["oncology"]
    projekt.save()

    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Kierowniczka"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )
    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Wykonawca"),
        rola=Projekt_Autor.ROLA_WYKONAWCA,
    )
    finansowanie = dodaj_finansowanie(
        projekt,
        grantodawca,
        kwota=decimal.Decimal("1000.00"),
        waluta="PLN",
        grant_doi="10.13039/501100004281-XYZ",
        numer_umowy="UMO-2024/45/B/NZ7/01234",
    )

    schemat = zbuduj_schemat()
    sprawdz(schemat, serializuj_projekt(uczelnia, projekt))
    sprawdz(schemat, serializuj_finansowanie(uczelnia, finansowanie))


@pytest.mark.django_db
def test_pusty_projekt_zgodny_z_xsd(uczelnia, jednostka):
    """Minimalny projekt — sam tytuł i status; reszta pól pusta."""
    from cerif_export.tests.test_serializery import sprawdz, zbuduj_schemat

    goly = baker.make(
        Projekt,
        tytul="Bez niczego",
        tytul_en="",
        akronim="",
        abstrakt="",
        abstrakt_en="",
        data_rozpoczecia=None,
        data_zakonczenia=None,
        jednostka=jednostka,
    )
    sprawdz(zbuduj_schemat(), serializuj_projekt(uczelnia, goly))


# -- pełny harvest OAI ---------------------------------------------------


@pytest.mark.django_db
def test_sety_wychodza_z_harvestu_oai(uczelnia, projekt, grantodawca):
    """``ListRecords`` bez parametru ``set`` musi wydać oba nowe rekordy.

    Sam queryset providera to za mało — brak wpisu w ``MODULY_SERIALIZERA``
    albo wisząca referencja wychodzą dopiero tutaj.
    """
    finansowanie = dodaj_finansowanie(projekt, grantodawca)

    korzen = czasowniki.odpowiedz(
        czasowniki.Zadanie(
            uczelnia,
            BASE_URL,
            {"verb": "ListRecords", "metadataPrefix": const.METADATA_PREFIX},
        )
    )

    bledy = [el for el in korzen.iter() if el.tag.endswith("}error")]
    assert not bledy, [el.get("code") for el in bledy]

    wydane = {
        el.text for el in korzen.iter() if el.tag.endswith("}identifier") and el.text
    }
    ns = uczelnia.oai_repository_identifier()
    assert identyfikatory.zbuduj(ns, projekt) in wydane
    assert identyfikatory.zbuduj(ns, finansowanie) in wydane
    assert identyfikatory.zbuduj(ns, grantodawca) in wydane


@pytest.mark.django_db
def test_referencje_projektu_sa_rozwiazywalne(
    uczelnia, projekt, grantodawca, fabryka_autorow
):
    """Każdy ``@id`` osadzony w ładunku musi mieć swój rekord w harveście.

    To dokładnie ta kontrola (5a), na której ``openaire-cris-validator``
    odrzuca całe repozytorium.
    """
    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Kierowniczka"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )
    dodaj_finansowanie(projekt, grantodawca)

    korzen = czasowniki.odpowiedz(
        czasowniki.Zadanie(
            uczelnia,
            BASE_URL,
            {"verb": "ListRecords", "metadataPrefix": const.METADATA_PREFIX},
        )
    )

    wydane = {
        el.text.split(":", 2)[-1]
        for el in korzen.iter()
        if el.tag.endswith("}identifier") and el.text
    }
    osadzone = set()
    for metadata in (el for el in korzen.iter() if el.tag.endswith("}metadata")):
        for el in metadata.iter():
            if el.get("id"):
                osadzone.add(el.get("id"))

    assert osadzone, "harvest nie osadził żadnej referencji"
    assert osadzone <= wydane, sorted(osadzone - wydane)
