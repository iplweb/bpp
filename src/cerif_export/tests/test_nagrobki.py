"""Faza 05b soft-delete: nagrobki dla konsumentów przyrostowych.

Nagrobek = rekord, który NALEŻY do tenanta, ale nie jest już wystawiany.
Dopełniamy ekspozycję, nigdy przynależność — dopełnienie przynależności
wystawiłoby w multi-hosted rekordy cudzych uczelni.
"""

import pytest

from cerif_export.oai.czasowniki import rejestr_providerow


def test_kazdy_provider_deklaruje_przynaleznosc():
    """Kontrakt musi być kompletny, inaczej nagrobki milkną w losowym secie.

    Provider bez ``przynaleznosc`` wywaliłby się dopiero przy harveście
    akurat tego setu — czyli u konsumenta, nie w testach.
    """
    for set_spec, provider in rejestr_providerow().items():
        assert hasattr(provider, "przynaleznosc"), (
            f"Provider setu {set_spec} nie deklaruje przynaleznosc()"
        )


@pytest.fixture
def druga_uczelnia(db):
    """Druga uczelnia z własną jednostką — multi-hosted."""
    from django.contrib.sites.models import Site

    from bpp.models import Jednostka, Uczelnia

    site = Site.objects.create(domain="druga.example.org", name="druga")
    uczelnia = Uczelnia.objects.create(nazwa="Druga", skrot="DRU", site=site)
    Jednostka.objects.create(nazwa="Jednostka Drugiej", skrot="JDR", uczelnia=uczelnia)
    return uczelnia


@pytest.mark.django_db
def test_nagrobki_nie_wyciekaja_miedzy_uczelniami(uczelnia, druga_uczelnia):
    """Dopełnienie NIE może objąć rekordów cudzego tenanta.

    To jedyne ryzyko, które dopełnienie widoczności wnosi wprost:
    ``widoczne_jednostki()`` filtruje ``uczelnia=uczelnia``, więc naiwne
    „wszystko minus widoczne" zamieniłoby każdą jednostkę drugiej uczelni
    w nagrobek pierwszej — wyciek identyfikatorów i lawina szumu.
    """
    from bpp.models import Jednostka
    from cerif_export import const

    provider = rejestr_providerow()[const.SET_ORGUNITS]
    nagrobki = provider.nagrobki(uczelnia, Jednostka)

    obce = Jednostka.objects.filter(uczelnia=druga_uczelnia)
    assert obce.exists(), "fixture musi utworzyć jednostkę drugiej uczelni"
    assert not nagrobki.filter(pk__in=obce.values("pk")).exists(), (
        "nagrobki uczelni A zawierają jednostkę uczelni B — wyciek tenanta"
    )


@pytest.mark.django_db
def test_konferencja_bez_widocznych_publikacji_to_nagrobek(
    uczelnia, jednostka, typ_autor
):
    """Provider pochodny: konferencja znika, gdy znikną jej publikacje.

    Widoczność konferencji jest wyprowadzona z publikacji. Gdy jedyna
    publikacja wskazująca konferencję przestaje być widoczna, konferencja
    też wypada z feedu — i musi dostać nagrobek, a nie zniknąć po cichu.
    """
    from model_bakery import baker

    from bpp.models import Konferencja, Wydawnictwo_Ciagle
    from cerif_export import const

    konferencja = baker.make(Konferencja)
    praca = baker.make(Wydawnictwo_Ciagle, konferencja=konferencja)
    # Nazwisko/imiona jawnie: baker generuje 500-znakowe losowe łańcuchy,
    # a ``dodaj_autora`` skleja z nich ``zapisany_jako`` (max 512 znaków).
    praca.dodaj_autora(
        baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan"), jednostka
    )

    provider = rejestr_providerow()[const.SET_EVENTS]
    assert (
        not provider.nagrobki(uczelnia, Konferencja).filter(pk=konferencja.pk).exists()
    ), "konferencja z widoczną publikacją nie jest nagrobkiem"

    praca.nie_eksportuj_przez_api = True
    praca.save()

    assert (
        provider.nagrobki(uczelnia, Konferencja).filter(pk=konferencja.pk).exists()
    ), (
        "konferencja straciła jedyną widoczną publikację, a nie dostała "
        "nagrobka — znika z feedu po cichu"
    )


@pytest.mark.django_db
def test_strona_miesza_zywe_i_nagrobki_w_porzadku_dat(uczelnia, jednostka, typ_autor):
    """Jeden strumień, jeden kursor.

    Nagrobki NIE mogą iść osobnym przebiegiem po żywych rekordach:
    ``resumptionToken`` niesie jeden kursor ``(datestamp, pk)`` i zakłada
    jeden porządek. Dwa strumienie zepsułyby przyrostowość ``from``/``until``,
    czyli dokładnie to, co ta faza naprawia.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )

    provider = rejestr_providerow()[const.SET_ORGUNITS]
    pary, _kursor = provider.strona(uczelnia, rozmiar=100)

    mapa = {obiekt.pk: nagrobek for obiekt, nagrobek in pary}
    assert mapa.get(ukryta.pk) is True, "jednostka ukryta ma być nagrobkiem"
    assert mapa.get(jednostka.pk) is False, "jednostka widoczna ma być żywa"


BASE_URL = "https://bpp.example.org/cerif/"
NS_PMH = "http://www.openarchives.org/OAI/2.0/"


def _zadanie_dla(uczelnia):
    """Żądanie OAI oderwane od HTTP — jak ``wykonaj`` w ``test_oai.py``."""
    from cerif_export.oai import czasowniki

    return czasowniki.Zadanie(uczelnia, BASE_URL)


def _wykonaj(uczelnia, **argumenty):
    from cerif_export.oai import czasowniki

    return czasowniki.odpowiedz(czasowniki.Zadanie(uczelnia, BASE_URL, argumenty))


@pytest.mark.django_db
def test_listrecords_emituje_nagrobek_bez_metadanych(uczelnia, jednostka):
    """Rekord usunięty to SAM nagłówek — dokładanie <metadata> łamie schemat."""
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const

    baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )

    korzen = _wykonaj(
        uczelnia,
        verb="ListRecords",
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_ORGUNITS,
    )
    naglowki = korzen.findall(f".//{{{NS_PMH}}}header")
    usuniete = [h for h in naglowki if h.get("status") == "deleted"]
    assert usuniete, "brak nagrobka w ListRecords"

    for naglowek in usuniete:
        rekord = naglowek.getparent()
        assert rekord.find(f"{{{NS_PMH}}}metadata") is None, (
            "nagrobek nie może nieść <metadata>"
        )


@pytest.mark.django_db
def test_getrecord_na_usunietym_zwraca_nagrobek(uczelnia):
    """Usunięty rekord ma nagrobek, nie błąd.

    ``idDoesNotExist`` znaczy „nigdy o takim nie słyszałem" — dla rekordu,
    który harvester dostał od nas wcześniej, to odpowiedź myląca.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const, identyfikatory

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )
    zadanie = _zadanie_dla(uczelnia)
    identyfikator = identyfikatory.zbuduj(zadanie.namespace, ukryta)

    korzen = _wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier=identyfikator,
        metadataPrefix=const.METADATA_PREFIX,
    )
    naglowek = korzen.find(f".//{{{NS_PMH}}}header")
    assert naglowek is not None, "GetRecord nie zwrócił nagłówka (błąd protokołu?)"
    assert naglowek.get("status") == "deleted"
    assert korzen.find(f".//{{{NS_PMH}}}metadata") is None


@pytest.mark.django_db
def test_identify_deklaruje_transient(uczelnia):
    """Deklaracja to obietnica wobec harvestera, nie kosmetyka.

    ``no`` znaczy „nie dowiesz się o usunięciach — rób pełny re-harvest".
    ``transient`` znaczy „ogłaszam usunięcia, ale nie gwarantuję, że
    nagrobek zostanie na zawsze" — i to jest prawda: husk może zniknąć przy
    twardym kasowaniu albo czyszczeniu kosza w fazie 07.
    """
    korzen = _wykonaj(uczelnia, verb="Identify")
    element = korzen.find(f".//{{{NS_PMH}}}deletedRecord")
    assert element is not None, "Identify nie zwrócił deletedRecord"
    assert element.text == "transient"
