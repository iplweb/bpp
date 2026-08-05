"""Walidacja serializerów CERIF względem XSD profilu OpenAIRE 1.2.

Snapshoty tekstowe byłyby tu bezużyteczne — o poprawności decyduje schemat,
bo to jego używa ``openaire-cris-validator`` po stronie OpenAIRE. Schematy
są vendorowane (``tests/xsd/``), a resolver odcina ruch sieciowy: test, który
po cichu pobiera XSD z internetu, przestaje działać w CI bez sieci i zaczyna
walidować co innego niż myślimy.
"""

import datetime
import pathlib

import pytest
from lxml import etree
from model_bakery import baker

from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.cerif import (
    event,
    orgunit,
    patent,
    person,
    publication,
    service,
    wspolne,
)
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.providers import provider_dla_setu

KATALOG_XSD = pathlib.Path(__file__).parent / "xsd"
NAMESPACE = "cerif.example.org"


class ResolverLokalny(etree.Resolver):
    """Mapuje zdalne URL-e schematów na vendorowane pliki.

    Wszystko, czego nie ma lokalnie, kończy się błędem zamiast cichego
    pobrania z sieci.
    """

    def resolve(self, url, identyfikator, kontekst):
        nazwa = url.rsplit("/", 1)[-1]
        for katalog in ("", "includes", "vocabularies", "cached"):
            kandydat = KATALOG_XSD / katalog / nazwa
            if kandydat.is_file():
                return self.resolve_filename(str(kandydat), kontekst)
        raise AssertionError(
            f"Schemat {url!r} nie jest vendorowany — test sięgnąłby do sieci."
        )


def zbuduj_schemat():
    """Zbuduj ``XMLSchema`` profilu z lokalnych plików."""
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(ResolverLokalny())
    korzen = KATALOG_XSD / "openaire-cerif-profile.xsd"
    return etree.XMLSchema(etree.parse(str(korzen), parser))


@pytest.fixture(scope="module")
def schemat():
    return zbuduj_schemat()


def sprawdz(schemat, element):
    """Zwaliduj pojedynczy element encji względem schematu profilu."""
    # Kopia przez serializację: element zbudowany w pamięci bywa bez
    # rozwiązanych przestrzeni nazw, a schemat sprawdza je rygorystycznie.
    dokument = etree.fromstring(etree.tostring(element))
    if not schemat.validate(dokument):
        raise AssertionError(
            f"{element.tag} nie przechodzi XSD:\n"
            + "\n".join(str(b) for b in schemat.error_log)
        )


def kontekst_setu(uczelnia, set_spec):
    provider = provider_dla_setu(set_spec)
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )
    return obiekty, kontekst


def znajdz(obiekty, model):
    return next(o for o in obiekty if type(o) is model)


# -- encje ----------------------------------------------------------------


@pytest.mark.django_db
def test_publication_wydawnictwo_ciagle_zgodne_z_xsd(
    schemat, uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo", skrot="Czas.", issn="1234-5678")
    fabryka_wydawnictw(
        Wydawnictwo_Ciagle,
        autor=fabryka_autorow(),
        zrodlo=zrodlo,
        tytul_oryginalny="Tytuł pracy",
        tom="12",
        nr_zeszytu="3",
        strony="100-110",
    )

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PUBLICATIONS)
    sprawdz(
        schemat, publication.serializuj(znajdz(obiekty, Wydawnictwo_Ciagle), kontekst)
    )


@pytest.mark.django_db
def test_publication_wydawnictwo_zwarte_zgodne_z_xsd(
    schemat, uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    fabryka_wydawnictw(
        Wydawnictwo_Zwarte,
        autor=fabryka_autorow(),
        tytul_oryginalny="Monografia",
        isbn="978-83-01-12345-6",
    )

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PUBLICATIONS)
    sprawdz(
        schemat, publication.serializuj(znajdz(obiekty, Wydawnictwo_Zwarte), kontekst)
    )


@pytest.mark.django_db
def test_publication_zrodlo_jako_kanal_wydawniczy_zgodne_z_xsd(
    schemat, uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """``Zrodlo`` wychodzi jako ``Publication`` typu *journal*."""
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo", skrot="Czas.", issn="1234-5678")
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=fabryka_autorow(), zrodlo=zrodlo)

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PUBLICATIONS)
    sprawdz(schemat, publication.serializuj(znajdz(obiekty, Zrodlo), kontekst))


@pytest.mark.django_db
def test_person_zgodne_z_xsd(schemat, uczelnia, fabryka_autorow):
    fabryka_autorow("Nowak", orcid="0000-0002-1825-0097")

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PERSONS)
    sprawdz(schemat, person.serializuj(obiekty[0], kontekst))


@pytest.mark.django_db
def test_orgunit_zgodne_z_xsd(schemat, uczelnia, jednostka):
    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_ORGUNITS)
    for obiekt in obiekty:
        sprawdz(schemat, orgunit.serializuj(obiekt, kontekst))


@pytest.mark.django_db
def test_patent_zgodne_z_xsd(schemat, uczelnia, jednostka, fabryka_autorow, status_ok):
    rekord = baker.make(
        Patent,
        tytul_oryginalny="Wynalazek",
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
        numer_prawa_wylacznego="PL 123456",
    )
    rekord.dodaj_autora(fabryka_autorow("Wynalazca"), jednostka)

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PATENTS)
    sprawdz(schemat, patent.serializuj(obiekty[0], kontekst))


@pytest.mark.django_db
def test_event_zgodne_z_xsd(schemat, uczelnia, fabryka_autorow, fabryka_wydawnictw):
    konferencja = baker.make(
        Konferencja,
        nazwa="Konferencja Testowa",
        skrocona_nazwa="KT",
        miasto="Lublin",
        panstwo="PL",
    )
    fabryka_wydawnictw(
        Wydawnictwo_Ciagle, autor=fabryka_autorow(), konferencja=konferencja
    )

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_EVENTS)
    sprawdz(schemat, event.serializuj(obiekty[0], kontekst))


@pytest.mark.django_db
def test_service_zgodne_z_xsd(schemat, uczelnia):
    _, kontekst = kontekst_setu(uczelnia, const.SET_ORGUNITS)
    sprawdz(schemat, service.serializuj(uczelnia, kontekst))


# -- integralność osadzonych encji ---------------------------------------


@pytest.mark.django_db
def test_niewidoczna_encja_osadzona_bez_identyfikatora(
    schemat, uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Encja spoza zbioru widoczności idzie bez ``@id``, ale nadal waliduje.

    To jest dokładnie ten przypadek, na którym łatwo złamać integralność
    referencyjną: kusi, żeby wypisać identyfikator, bo obiekt jest pod ręką.
    """
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=ukryty)

    obiekty, kontekst = kontekst_setu(uczelnia, const.SET_PUBLICATIONS)
    element = publication.serializuj(znajdz(obiekty, Wydawnictwo_Ciagle), kontekst)

    sprawdz(schemat, element)
    osoby = [el for el in element.iter() if el.tag.endswith("Person")]
    assert osoby and all(el.get("id") is None for el in osoby)


# -- schemat licencji ----------------------------------------------------


@pytest.mark.parametrize(
    "uri,oczekiwany",
    [
        ("https://creativecommons.org/licenses/by/4.0/", wspolne.SCHEMAT_LICENCJI_CC),
        (
            "https://creativecommons.org/publicdomain/zero/1.0/",
            wspolne.SCHEMAT_LICENCJI_CC,
        ),
        ("https://spdx.org/licenses/MIT.html", wspolne.SCHEMAT_LICENCJI_SPDX),
        ("", wspolne.SCHEMAT_LICENCJI_SPDX),
        (None, wspolne.SCHEMAT_LICENCJI_SPDX),
        # Regresja (CodeQL py/incomplete-url-substring-sanitization): domena
        # w query stringu nie może przebrać obcego adresu za Creative Commons.
        (
            "https://example.invalid/?x=creativecommons.org",
            wspolne.SCHEMAT_LICENCJI_SPDX,
        ),
        ("https://creativecommons.org.example.invalid/", wspolne.SCHEMAT_LICENCJI_SPDX),
    ],
)
def test_schemat_licencji_porownuje_host_nie_podciag(uri, oczekiwany):
    assert wspolne.schemat_licencji(uri) == oczekiwany


# -- embargo a prawo dostępu ---------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "czas_skrot,miesiecy,data,oczekiwane",
    [
        # Otwarte od razu — bez embarga.
        ("AT_PUBLICATION", None, None, "OPEN"),
        ("BEFORE_PUBLICATION", None, None, "OPEN"),
        # Embargo trwa.
        ("AFTER_PUBLICATION", 12, datetime.date(2099, 1, 1), "EMBARGOED"),
        # „Po opublikowaniu", ale nie wiadomo po ilu miesiącach.
        ("AFTER_PUBLICATION", None, None, "EMBARGOED"),
        # Znamy okres, ale nie datę — nadal nie wiemy, czy minęło.
        ("AFTER_PUBLICATION", 6, None, "EMBARGOED"),
        # Embargo dawno minęło — praca jest realnie otwarta.
        ("AFTER_PUBLICATION", 6, datetime.date(2000, 1, 1), "OPEN"),
    ],
)
def test_embargo_nie_jest_raportowane_jako_open_access(
    czas_skrot, miesiecy, data, oczekiwane
):
    """Tryb dostępu mówi GDZIE, nie KIEDY.

    Praca w otwartym czasopiśmie, ale pod embargiem, nie jest w tej chwili
    dostępna — profil ma na to osobny termin ``embargoed access``.
    """
    from types import SimpleNamespace

    from cerif_export.cerif.publication import _pod_embargiem
    from cerif_export.slowniki import dostep

    obj = SimpleNamespace(
        openaccess_czas_publikacji=SimpleNamespace(skrot=czas_skrot),
        openaccess_ilosc_miesiecy=miesiecy,
        openaccess_data_opublikowania=data,
    )

    pod_embargiem = _pod_embargiem(obj, dzisiaj=datetime.date(2026, 8, 4))
    wynik = dostep.EMBARGOED if pod_embargiem else dostep.OPEN

    assert wynik == getattr(dostep, oczekiwane)


@pytest.mark.django_db
def test_embargo_na_granicy_okresu():
    """Miesiąc 30-dniowy SKRACAŁ embargo o kilka dni.

    Przez to okno rekord raportował ``open access``, będąc jeszcze pod
    embargiem — czyli błąd dokładnie w tę stronę, którą docstring
    ``_pod_embargiem`` odrzuca. Stąd ``relativedelta``, nie ``timedelta``.
    """
    from types import SimpleNamespace

    from cerif_export.cerif.publication import _pod_embargiem

    obj = SimpleNamespace(
        openaccess_czas_publikacji=SimpleNamespace(skrot="AFTER_PUBLICATION"),
        openaccess_ilosc_miesiecy=12,
        openaccess_data_opublikowania=datetime.date(2025, 1, 15),
    )

    # 12 miesięcy od 2025-01-15 to 2026-01-15. Przybliżenie 30-dniowe dałoby
    # koniec 2025-12-11, więc te dwie daty rozstrzygały wtedy błędnie.
    assert _pod_embargiem(obj, dzisiaj=datetime.date(2025, 12, 20)) is True
    assert _pod_embargiem(obj, dzisiaj=datetime.date(2026, 1, 14)) is True
    assert _pod_embargiem(obj, dzisiaj=datetime.date(2026, 1, 15)) is False
