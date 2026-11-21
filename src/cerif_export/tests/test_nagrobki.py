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


# -- cztery drogi zniknięcia --------------------------------------------


def _ukryj_kosz(praca, uczelnia):
    praca.delete()


def _ukryj_opt_out(praca, uczelnia):
    praca.nie_eksportuj_przez_api = True
    praca.save()


def _ukryj_status(praca, uczelnia):
    from bpp.models import Status_Korekty
    from bpp.models.uczelnia import Ukryj_Status_Korekty

    status = Status_Korekty.objects.get_or_create(nazwa="wycofany z eksportu")[0]
    # Fixture ``uczelnia`` nie ma żadnego statusu ukrytego w kanale ``cerif``,
    # więc trzecią drogę zniknięcia musimy tu zbudować, a nie pominąć.
    Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=status, cerif=True
    )
    praca.status_korekty = status
    praca.save()

    assert list(uczelnia.ukryte_statusy("cerif")), (
        "test musi mieć status ukryty w kanale cerif — bez tego przypadek "
        "nie odtwarza trzeciej drogi zniknięcia"
    )


def _ukryj_odpiecie_autora(praca, uczelnia):
    # Skasowanie autorstwa to soft-delete (faza 02) — wiersz zostaje w koszu
    # i to on trzyma historyczną atrybucję rekordu do uczelni.
    praca.autorzy_set.first().delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ukryj",
    [_ukryj_kosz, _ukryj_opt_out, _ukryj_status, _ukryj_odpiecie_autora],
    ids=["kosz", "opt_out", "ukryty_status", "odpiecie_autora"],
)
def test_kazda_droga_znikniecia_daje_nagrobek(uczelnia, jednostka, typ_autor, ukryj):
    """Cztery drogi, jeden skutek dla harvestera — więc jeden nagrobek.

    Przypadek ``odpiecie_autora`` jest tu najważniejszy: dowodzi, że
    ``przynaleznosc`` idzie przez ``global_objects`` modelu autorstwa.
    Gdyby szła przez ``objects``, rekord wypadłby z nadzbioru i zniknął
    po cichu — czyli wróciłaby dokładnie ta luka, którą faza zamyka.

    Przypadek ``kosz`` dowodzi tego samego o zewnętrznym managerze rekordu.
    """
    from model_bakery import baker

    from bpp.models import Autor, Wydawnictwo_Ciagle
    from cerif_export import const

    praca = baker.make(Wydawnictwo_Ciagle)
    praca.dodaj_autora(baker.make(Autor, nazwisko="Kowalski", imiona="Jan"), jednostka)

    provider = rejestr_providerow()[const.SET_PUBLICATIONS]
    assert (
        not provider.nagrobki(uczelnia, Wydawnictwo_Ciagle).filter(pk=praca.pk).exists()
    ), "rekord widoczny nie może być nagrobkiem"

    ukryj(praca, uczelnia)

    assert (
        provider.nagrobki(uczelnia, Wydawnictwo_Ciagle).filter(pk=praca.pk).exists()
    ), "rekord przestał być widoczny, a nie dostał nagrobka"


# -- okno from/until i granica strony -----------------------------------


def _ustaw_datestamp(model, pk, wartosc):
    """``ostatnio_zmieniony`` ma ``auto_now``, więc omijamy ``save()``."""
    model.objects.filter(pk=pk).update(ostatnio_zmieniony=wartosc)


def _dzien(numer):
    import datetime

    return datetime.datetime(2024, 3, numer, 12, 0, 0, tzinfo=datetime.UTC)


@pytest.mark.django_db
def test_okno_od_do_obejmuje_nagrobki(uczelnia, jednostka):
    """Nagrobek jest datowany i podlega ``from``/``until`` jak żywy rekord.

    Znacznik bierze się z ``ostatnio_zmieniony``, który soft-delete bumpuje
    (kontrakt PINNED fazy 01) — bez tego harvest przyrostowy nigdy by
    nagrobka nie zobaczył, bo konsument pyta zawsze o okno „od ostatniego
    razu".
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )
    _ustaw_datestamp(Jednostka, ukryta.pk, _dzien(10))

    provider = rejestr_providerow()[const.SET_ORGUNITS]

    def pk_jednostek(**kwargs):
        pary, _ = provider.strona(uczelnia, rozmiar=100, **kwargs)
        return {
            obiekt.pk for obiekt, _nagrobek in pary if isinstance(obiekt, Jednostka)
        }

    assert ukryta.pk in pk_jednostek(od=_dzien(9)), (
        "nagrobek wypadł z okna `from` — harvest przyrostowy go nie zobaczy"
    )
    assert ukryta.pk in pk_jednostek(od=_dzien(9), do=_dzien(11))
    assert ukryta.pk not in pk_jednostek(do=_dzien(9)), (
        "nagrobek z przyszłości wszedł w okno `until`"
    )
    assert ukryta.pk not in pk_jednostek(od=_dzien(11))


@pytest.mark.django_db
def test_harvest_po_tokenach_nie_gubi_i_nie_dubluje_na_granicy_nagrobka(
    uczelnia, jednostka
):
    """Strona kończy się DOKŁADNIE na nagrobku — bez duplikatu i bez luki.

    To tu żyły wcześniejsze bugi ``Trunc``/``tzinfo`` opisane
    w ``z_datestampem``: kursor i wartość sortowania rozjeżdżały się
    o mikrosekundy albo o offset strefy, więc rekord graniczny wracał na
    następnej stronie (duplikat) albo znikał (luka). Nagrobki nie mogą tego
    przywrócić, bo płyną tym samym strumieniem i tym samym kursorem.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const

    ROZMIAR = 3

    _ustaw_datestamp(Jednostka, jednostka.pk, _dzien(1))
    oczekiwane = {jednostka.pk: False}

    # Pozycje 3 i 6 w porządku dat są nagrobkami — przy rozmiarze 3 pierwsza
    # strona kończy się dokładnie na nagrobku.
    for numer in range(2, 8):
        widoczna = numer not in (3, 6)
        obiekt = baker.make(
            Jednostka,
            uczelnia=uczelnia,
            nazwa=f"Jednostka {numer}",
            skrot=f"J{numer}",
            widoczna=widoczna,
        )
        _ustaw_datestamp(Jednostka, obiekt.pk, _dzien(numer))
        oczekiwane[obiekt.pk] = not widoczna

    provider = rejestr_providerow()[const.SET_ORGUNITS]

    pierwsza, kursor = provider.strona(uczelnia, rozmiar=ROZMIAR)
    assert kursor is not None, "harvest musi być wielostronicowy"
    assert pierwsza[-1][1] is True, (
        "setup się rozjechał: strona nie kończy się na nagrobku, "
        "czyli test nie bada granicy, o którą chodzi"
    )

    zebrane = list(pierwsza)
    for _ in range(50):
        if kursor is None:
            break
        partia, kursor = provider.strona(uczelnia, kursor=kursor, rozmiar=ROZMIAR)
        zebrane.extend(partia)
    else:
        raise AssertionError("harvest nie zakończył się po 50 stronach")

    klucze = [(type(obiekt).__name__, obiekt.pk) for obiekt, _nagrobek in zebrane]
    assert len(klucze) == len(set(klucze)), (
        f"rekord wyszedł dwa razy na granicy strony: {klucze}"
    )

    otrzymane = {
        obiekt.pk: nagrobek
        for obiekt, nagrobek in zebrane
        if isinstance(obiekt, Jednostka)
    }
    assert otrzymane == oczekiwane, (
        "harvest zgubił rekord albo pomylił żywego z nagrobkiem"
    )


# -- walidacja XSD odpowiedzi z nagrobkami ------------------------------


@pytest.fixture(scope="module")
def schemat_koperty():
    """``XMLSchema`` koperty OAI-PMH razem z ładunkiem profilu CERIF.

    Testy serializerów walidują pojedyncze encje względem profilu; tu
    walidujemy CAŁĄ odpowiedź, bo ``status="deleted"`` jest konstrukcją
    koperty OAI-PMH, nie profilu. Bez tego łatwo wyemitować XML, który
    agregator odrzuci — a dowiedzielibyśmy się o tym od niego.
    """
    import pathlib

    from lxml import etree

    from cerif_export.tests.test_serializery import ResolverLokalny

    katalog = pathlib.Path(__file__).parent / "xsd"
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(ResolverLokalny())
    return etree.XMLSchema(etree.parse(str(katalog / "oai-pmh-z-profilem.xsd"), parser))


def _zwaliduj(schemat, korzen):
    from lxml import etree

    dokument = etree.fromstring(etree.tostring(korzen))
    if not schemat.validate(dokument):
        raise AssertionError(
            "odpowiedź nie przechodzi XSD OAI-PMH:\n"
            + "\n".join(str(b) for b in schemat.error_log)
        )


@pytest.mark.django_db
@pytest.mark.parametrize("czasownik", ["ListRecords", "ListIdentifiers"])
def test_odpowiedz_z_nagrobkiem_przechodzi_xsd(
    schemat_koperty, uczelnia, jednostka, czasownik
):
    """Nagrobek obok żywego rekordu musi być poprawny wobec schematu."""
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const

    baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )

    korzen = _wykonaj(
        uczelnia,
        verb=czasownik,
        metadataPrefix=const.METADATA_PREFIX,
        set=const.SET_ORGUNITS,
    )

    naglowki = korzen.findall(f".//{{{NS_PMH}}}header")
    assert [h for h in naglowki if h.get("status") == "deleted"], (
        "odpowiedź bez nagrobka nie testuje tego, o co chodzi"
    )
    assert [h for h in naglowki if h.get("status") is None], (
        "odpowiedź bez żywego rekordu nie sprawdza sąsiedztwa obu rodzajów"
    )

    _zwaliduj(schemat_koperty, korzen)


@pytest.mark.django_db
def test_getrecord_z_nagrobkiem_przechodzi_xsd(schemat_koperty, uczelnia):
    """GetRecord na nagrobku: ``<record>`` z samym ``<header>``.

    Schemat dopuszcza ``<metadata>`` jako ``minOccurs="0"``, więc rekord bez
    ładunku jest poprawny — ale tylko dlatego, że NIE dokładamy pustego
    ``<metadata>``.
    """
    from model_bakery import baker

    from bpp.models import Jednostka
    from cerif_export import const, identyfikatory

    ukryta = baker.make(
        Jednostka, uczelnia=uczelnia, nazwa="Ukryta", skrot="UKR", widoczna=False
    )
    zadanie = _zadanie_dla(uczelnia)

    korzen = _wykonaj(
        uczelnia,
        verb="GetRecord",
        identifier=identyfikatory.zbuduj(zadanie.namespace, ukryta),
        metadataPrefix=const.METADATA_PREFIX,
    )
    _zwaliduj(schemat_koperty, korzen)
