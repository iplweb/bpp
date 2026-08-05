"""Integralność referencyjna całego eksportu.

Profil wymaga, żeby każdy identyfikator użyty w powiązaniu dało się
rozwiązać na rekord w tym samym endpoincie. To najczęstszy powód odrzuceń
przez ``openaire-cris-validator`` i jednocześnie błąd, którego testy
jednostkowe pojedynczych serializerów nie łapią — widać go dopiero, gdy
zestawi się pełny harvest z pełną listą wydanych identyfikatorów.
"""

import pytest
from lxml import etree
from model_bakery import baker

from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.oai import czasowniki

BASE_URL = "https://cerif.example.org/cerif-oai/"


@pytest.fixture
def pelne_dane(uczelnia, jednostka, fabryka_autorow, fabryka_wydawnictw, status_ok):
    """Po jednym rekordzie każdego eksportowanego typu, z powiązaniami."""
    autor = fabryka_autorow("Kowalski", orcid="0000-0002-1825-0097")
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)

    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo", skrot="Czas.", issn="1234-5678")
    konferencja = baker.make(
        Konferencja, nazwa="Konferencja", skrocona_nazwa="KONF", miasto="Lublin"
    )

    ciagle = fabryka_wydawnictw(
        Wydawnictwo_Ciagle, autor=autor, zrodlo=zrodlo, konferencja=konferencja
    )
    # Publikacja z autorem ukrytym — sprawdza, że osadzenie bez @id nie
    # produkuje wiszącej referencji.
    ciagle.dodaj_autora(ukryty, jednostka)

    fabryka_wydawnictw(Wydawnictwo_Zwarte, autor=autor)

    baker.make(
        Praca_Doktorska,
        jednostka=jednostka,
        autor=autor,
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )

    patent = baker.make(
        Patent,
        tytul_oryginalny="Wynalazek",
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    patent.dodaj_autora(autor, jednostka)
    return uczelnia


def harvest(uczelnia):
    """Zbierz wszystkie rekordy ze wszystkich setów, przechodząc tokeny."""
    rekordy = []
    token = None
    for _ in range(50):
        argumenty = (
            {"verb": "ListRecords", "resumptionToken": token}
            if token
            else {"verb": "ListRecords", "metadataPrefix": const.METADATA_PREFIX}
        )
        korzen = czasowniki.odpowiedz(czasowniki.Zadanie(uczelnia, BASE_URL, argumenty))
        bledy = [el for el in korzen.iter() if el.tag.endswith("}error")]
        assert not bledy, [el.get("code") for el in bledy]

        rekordy.extend(el for el in korzen.iter() if el.tag.endswith("}record"))

        tokeny = [el for el in korzen.iter() if el.tag.endswith("}resumptionToken")]
        token = tokeny[0].text if tokeny else None
        if not token:
            return rekordy
    raise AssertionError("Harvest nie zakończył się po 50 stronach")


def identyfikatory_naglowkow(rekordy):
    wynik = set()
    for rekord in rekordy:
        for el in rekord.iter():
            if el.tag.endswith("}identifier") and el.text:
                wynik.add(el.text)
    return wynik


def identyfikatory_osadzone(rekordy):
    """Wszystkie atrybuty ``id`` z ładunku metadanych."""
    wynik = set()
    for rekord in rekordy:
        for metadata in (el for el in rekord.iter() if el.tag.endswith("}metadata")):
            for el in metadata.iter():
                wartosc = el.get("id")
                if wartosc:
                    wynik.add(wartosc)
    return wynik


@pytest.mark.django_db
def test_kazde_powiazanie_da_sie_rozwiazac(pelne_dane):
    """Zbiór identyfikatorów w powiązaniach ⊆ zbiór wydanych rekordów."""
    uczelnia = pelne_dane
    rekordy = harvest(uczelnia)
    assert rekordy, "harvest nie zwrócił żadnego rekordu"

    wydane = identyfikatory_naglowkow(rekordy)
    # Identyfikatory rekordów są w nagłówku w formie oai:...; w ładunku
    # CERIF-a wewnętrzne @id to sama część lokalna.
    lokalne = {x.split(":", 2)[-1] for x in wydane}

    wiszace = {
        x
        for x in identyfikatory_osadzone(rekordy)
        if x not in wydane and x not in lokalne
    }

    assert not wiszace, (
        f"powiązania wskazują rekordy, których nie ma w endpoincie: {sorted(wiszace)}"
    )


@pytest.mark.django_db
def test_identyfikatory_sa_unikalne_w_calym_eksporcie(pelne_dane):
    """Profil wymaga unikalności ``id`` w obrębie WSZYSTKICH typów encji.

    Klucze główne kolidują między modelami (``Wydawnictwo_Ciagle`` nr 5
    i ``Autor`` nr 5), więc rozróżnia je dopiero slug w identyfikatorze.
    """
    rekordy = harvest(pelne_dane)
    wydane = [
        el.text
        for rekord in rekordy
        for el in rekord.iter()
        if el.tag.endswith("}identifier") and el.text
    ]

    assert len(wydane) == len(set(wydane)), "identyfikator wydany dwa razy"


@pytest.mark.django_db
def test_harvest_jest_poprawnym_xml_em(pelne_dane):
    """Cały dokument musi się serializować bez wyjątku."""
    korzen = czasowniki.odpowiedz(
        czasowniki.Zadanie(
            pelne_dane,
            BASE_URL,
            {"verb": "ListRecords", "metadataPrefix": const.METADATA_PREFIX},
        )
    )
    bajty = czasowniki.na_xml(korzen)
    assert etree.fromstring(bajty) is not None
