"""``OriginatesFrom`` — powiązanie publikacji i patentów z projektami.

To ogniwo, dla którego sety ``openaire_cris_projects`` i
``openaire_cris_funding`` w ogóle mają sens. Bez niego agregator dostaje
dwie rozłączne listy: osobno publikacje, osobno projekty; walidator
przechodzi, wartość merytoryczna jest zerowa.

Trzy rzeczy pilnowane tu szczególnie, bo wychodzą dopiero pod walidatorem
OpenAIRE albo na pełnym harveście:

1. ``OriginatesFrom`` **osadza** pełne ``<Project>`` (grupa podstawień
   ``ProjectFunding__SubstitutionGroupHead``), a nie referencję — i wypada
   w ``xs:sequence`` w dokładnie jednym miejscu (Publication: między
   ``Status`` a ``PresentedAt``; Patent: między ``Keyword``
   a ``Predecessor``);
2. osadzony projekt ma ``@id``, więc **musi** realnie wyjść w secie
   projektów — stąd odsiew projektów cudzej uczelni (``Grant`` jest
   współdzielony i jego ``projekt`` bywa spoza tenanta);
3. serializer nie dotyka bazy — mierzone licznikiem zapytań, nie
   deklarowane.
"""

import pytest
from django.contrib.sites.models import Site
from django.db import connection
from django.test.utils import CaptureQueriesContext
from lxml import etree
from model_bakery import baker

from bpp.models import (
    Grant,
    Grant_Rekordu,
    Instytucja_Finansujaca,
    Jednostka,
    Projekt,
    Projekt_Autor,
    Uczelnia,
)
from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from cerif_export import const, identyfikatory
from cerif_export.cerif import patent as cerif_patent
from cerif_export.cerif import publication as cerif_publication
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.oai import czasowniki
from cerif_export.providers import provider_dla_setu

NAMESPACE = "cerif.example.org"
BASE_URL = "https://cerif.example.org/cerif-oai/"


def q(nazwa):
    """Nazwa elementu z przestrzeni nazw profilu CERIF."""
    return f"{{{const.NS_CERIF}}}{nazwa}"


def nazwy_dzieci(el):
    """Lokalne nazwy dzieci elementu — w kolejności wystąpienia."""
    return [etree.QName(dziecko).localname for dziecko in el]


# -- budowanie danych ----------------------------------------------------


@pytest.fixture
def grantodawca(db):
    return baker.make(
        Instytucja_Finansujaca,
        nazwa="Narodowe Centrum Nauki",
        akronim="NCN",
        fundref_id="501100004281",
    )


@pytest.fixture
def projekt(jednostka):
    return baker.make(
        Projekt,
        tytul="Badany projekt",
        tytul_en="Studied project",
        akronim="BAP",
        status=Projekt.STATUS_W_TRAKCIE,
        data_rozpoczecia="2024-01-01",
        data_zakonczenia="2026-12-31",
        jednostka=jednostka,
    )


@pytest.fixture
def obca_jednostka(db):
    """Jednostka innej uczelni — ten sam ``Grant`` bywa współdzielony."""
    obca = Uczelnia.objects.create(
        nazwa="Obca uczelnia",
        skrot="OBC",
        site=Site.objects.create(domain="obca.example.org", name="obca"),
    )
    return Jednostka.objects.create(nazwa="Obca jednostka", skrot="OJE", uczelnia=obca)


def przypnij_grant(rekord, numer, projekt=None):
    """Utwórz numer grantu i przypnij go do rekordu."""
    grant = baker.make(Grant, numer_projektu=numer, projekt=projekt)
    Grant_Rekordu.objects.create(rekord=rekord, grant=grant)
    return grant


def dodaj_finansowanie(projekt, grantodawca, **kwargs):
    from bpp.models import Finansowanie

    kwargs.setdefault("typ", Finansowanie.TYP_GRANT)
    kwargs.setdefault("nazwa_programu", "OPUS 24")
    kwargs.setdefault("kwota", None)
    return baker.make(Finansowanie, projekt=projekt, instytucja=grantodawca, **kwargs)


# -- serializacja przez provider (jak w produkcji) -----------------------


def _serializuj(uczelnia, set_spec, obiekt, serializer):
    """Zserializuj rekord dokładnie tak, jak robi to warstwa OAI.

    Obiekt jest **ponownie pobierany** przez queryset providera, żeby miał
    komplet prefetchy. Serializer nie ma prawa dotykać bazy, więc test na
    obiekcie prosto z ``baker.make`` sprawdzałby co innego niż produkcja.
    """
    provider = provider_dla_setu(set_spec)
    zaladowany = provider.queryset(uczelnia, type(obiekt)).get(pk=obiekt.pk)
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, [zaladowany]),
    )
    return serializer(zaladowany, kontekst)


def serializuj_publikacje(uczelnia, rekord):
    return _serializuj(
        uczelnia, const.SET_PUBLICATIONS, rekord, cerif_publication.serializuj
    )


def serializuj_patent(uczelnia, rekord):
    return _serializuj(uczelnia, const.SET_PATENTS, rekord, cerif_patent.serializuj)


@pytest.fixture
def publikacja(fabryka_wydawnictw, fabryka_autorow):
    return fabryka_wydawnictw(
        Wydawnictwo_Ciagle,
        autor=fabryka_autorow("Autorska"),
        tytul_oryginalny="Praca z projektu",
    )


@pytest.fixture
def wynalazek(jednostka, fabryka_autorow, status_ok):
    rekord = baker.make(
        Patent,
        tytul_oryginalny="Wynalazek z projektu",
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
        numer_prawa_wylacznego="PL 123456",
    )
    rekord.dodaj_autora(fabryka_autorow("Wynalazca"), jednostka)
    return rekord


# -- kiedy elementu NIE ma -----------------------------------------------


@pytest.mark.django_db
def test_publikacja_bez_grantow_nie_ma_originates_from(uczelnia, publikacja):
    """``minOccurs="0"`` — publikacja bez projektu jest poprawna."""
    el = serializuj_publikacje(uczelnia, publikacja)
    assert el.find(q("OriginatesFrom")) is None


@pytest.mark.django_db
def test_publikacja_z_grantem_bez_projektu_nie_ma_originates_from(uczelnia, publikacja):
    """Sam numer grantu to za mało.

    ``Grant`` bez ``projekt`` jest w BPP zwykłą etykietą tekstową — nie ma
    z czego zbudować encji ``Project``, a pusty ``OriginatesFrom`` byłby
    niepoprawny wobec XSD (dziecko z grupy podstawień jest obowiązkowe).
    """
    przypnij_grant(publikacja, "BEZ/PROJEKTU", projekt=None)

    el = serializuj_publikacje(uczelnia, publikacja)
    assert el.find(q("OriginatesFrom")) is None


@pytest.mark.django_db
def test_projekt_cudzej_uczelni_nie_wychodzi_w_originates_from(
    uczelnia, publikacja, obca_jednostka
):
    """``Grant`` jest współdzielony między uczelniami.

    Osadzony ``Project`` zawsze dostaje ``@id``, więc projekt spoza tenanta
    dałby referencję do rekordu, którego harvester nigdy nie zobaczy —
    dokładnie ta klasa błędu, na której walidator odrzuca repozytorium
    (kontrola integralności referencyjnej 5a).
    """
    obcy = baker.make(Projekt, tytul="Cudzy projekt", jednostka=obca_jednostka)
    przypnij_grant(publikacja, "CUDZY/1", projekt=obcy)

    el = serializuj_publikacje(uczelnia, publikacja)
    assert el.find(q("OriginatesFrom")) is None
    assert "Cudzy projekt" not in etree.tostring(el, encoding="unicode")


# -- osadzanie projektu ---------------------------------------------------


@pytest.mark.django_db
def test_publikacja_z_projektem_osadza_pelny_project(uczelnia, publikacja, projekt):
    """``OriginatesFrom`` osadza element z grupy podstawień, nie referencję."""
    przypnij_grant(publikacja, "Z/PROJEKTEM", projekt=projekt)

    el = serializuj_publikacje(uczelnia, publikacja)
    pochodzenie = el.find(q("OriginatesFrom"))
    assert pochodzenie is not None

    osadzony = pochodzenie.find(q("Project"))
    assert osadzony is not None
    assert osadzony.get("id") == f"Projects/pj-{projekt.pk}"
    assert osadzony.find(q("Acronym")).text == "BAP"
    assert [t.text for t in osadzony.findall(q("Title"))] == [
        "Badany projekt",
        "Studied project",
    ]
    assert osadzony.find(q("StartDate")).text == "2024-01-01"


@pytest.mark.django_db
def test_osadzony_projekt_niesie_wlasne_finansowanie(
    uczelnia, publikacja, projekt, grantodawca
):
    """Łańcuch domyka się dopiero na finansowaniu.

    ``Project/Funded/As`` osadza pełne ``<Funding>`` z ``@id``, więc rekord
    finansowania też musi być w harveście — ``ProviderFinansowania``
    filtruje identycznie jak ``ProviderProjektow``.
    """
    finansowanie = dodaj_finansowanie(projekt, grantodawca)
    przypnij_grant(publikacja, "Z/FINANSOWANIEM", projekt=projekt)

    el = serializuj_publikacje(uczelnia, publikacja)
    funded = el.find(f"{q('OriginatesFrom')}/{q('Project')}/{q('Funded')}")
    assert funded is not None
    assert nazwy_dzieci(funded) == ["By", "As"]

    orgunit = funded.find(f"{q('By')}/{q('OrgUnit')}")
    assert orgunit.get("id") == f"OrgUnits/if-{grantodawca.pk}"

    osadzone = funded.find(f"{q('As')}/{q('Funding')}")
    assert osadzone.get("id") == f"Fundings/fn-{finansowanie.pk}"


@pytest.mark.django_db
def test_zespol_osadzonego_projektu_ma_id_osoby(
    uczelnia, publikacja, projekt, fabryka_autorow
):
    """Zbiór ``autorzy`` providera publikacji musi objąć też zespół projektu.

    Kierownik projektu nie musi być autorem publikacji — bez rozszerzenia
    zbioru widoczności ``Team/PrincipalInvestigator`` osadzałby ``Person``
    bez ``@id``.
    """
    kierowniczka = fabryka_autorow("Kierowniczka")
    Projekt_Autor.objects.create(
        projekt=projekt, autor=kierowniczka, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    przypnij_grant(publikacja, "Z/ZESPOLEM", projekt=projekt)

    el = serializuj_publikacje(uczelnia, publikacja)
    osoba = el.find(
        f"{q('OriginatesFrom')}/{q('Project')}/{q('Team')}"
        f"/{q('PrincipalInvestigator')}/{q('Person')}"
    )
    assert osoba is not None
    assert osoba.get("id") == f"Persons/au-{kierowniczka.pk}"


@pytest.mark.django_db
def test_koordynator_osadzonego_projektu_ma_id_jednostki(
    uczelnia, publikacja, fabryka_autorow
):
    """Jednostka realizująca bywa inna niż jednostka autorów publikacji."""
    inna = Jednostka.objects.create(
        nazwa="Katedra Projektowa", skrot="KPR", uczelnia=uczelnia
    )
    wlasny = baker.make(Projekt, tytul="Projekt katedry", jednostka=inna)
    przypnij_grant(publikacja, "Z/KATEDRY", projekt=wlasny)

    el = serializuj_publikacje(uczelnia, publikacja)
    orgunit = el.find(
        f"{q('OriginatesFrom')}/{q('Project')}/{q('Consortium')}"
        f"/{q('Coordinator')}/{q('OrgUnit')}"
    )
    assert orgunit is not None
    assert orgunit.get("id") == f"OrgUnits/je-{inna.pk}"


@pytest.mark.django_db
def test_dwa_granty_tego_samego_projektu_daja_jeden_originates_from(
    uczelnia, publikacja, projekt
):
    """Deduplikacja po projekcie.

    Jeden projekt bywa rozliczany kilkoma numerami grantu; dwa identyczne
    ``OriginatesFrom`` przy jednej publikacji to czysty szum w harveście.
    """
    przypnij_grant(publikacja, "PIERWSZY/1", projekt=projekt)
    przypnij_grant(publikacja, "DRUGI/2", projekt=projekt)

    el = serializuj_publikacje(uczelnia, publikacja)
    assert len(el.findall(q("OriginatesFrom"))) == 1


@pytest.mark.django_db
def test_dwa_rozne_projekty_daja_dwa_originates_from(uczelnia, publikacja, projekt):
    """``maxOccurs="unbounded"`` — publikacja bywa efektem dwóch projektów."""
    drugi = baker.make(Projekt, tytul="Drugi projekt", jednostka=projekt.jednostka)
    przypnij_grant(publikacja, "PIERWSZY/1", projekt=projekt)
    przypnij_grant(publikacja, "DRUGI/2", projekt=drugi)

    el = serializuj_publikacje(uczelnia, publikacja)
    osadzone = {
        p.get("id") for p in el.findall(f"{q('OriginatesFrom')}/{q('Project')}")
    }
    assert osadzone == {f"Projects/pj-{projekt.pk}", f"Projects/pj-{drugi.pk}"}


# -- miejsce w xs:sequence ------------------------------------------------


@pytest.mark.django_db
def test_originates_from_wypada_przed_presented_at(uczelnia, publikacja, projekt):
    """``xs:sequence`` profilu: ... Keyword, Abstract, Status,
    **OriginatesFrom**, PresentedAt, ... — zła kolejność to niepoprawny
    dokument, a walidator odrzuca cały rekord."""
    publikacja.konferencja = baker.make(
        Konferencja, nazwa="Konferencja Testowa", skrocona_nazwa="KT"
    )
    publikacja.save()
    publikacja.slowa_kluczowe.add("onkologia")
    przypnij_grant(publikacja, "Z/KOLEJNOSCIA", projekt=projekt)

    kolejnosc = nazwy_dzieci(serializuj_publikacje(uczelnia, publikacja))
    assert "OriginatesFrom" in kolejnosc
    assert kolejnosc.index("Keyword") < kolejnosc.index("OriginatesFrom")
    assert kolejnosc.index("OriginatesFrom") < kolejnosc.index("PresentedAt")


@pytest.mark.django_db
def test_patent_osadza_project_po_slowach_kluczowych(uczelnia, wynalazek, projekt):
    """``Patent/OriginatesFrom`` ma identyczną strukturę co w publikacji,
    ale inne miejsce w sekwencji: ... Keyword, **OriginatesFrom**,
    Predecessor, References, FileLocations."""
    wynalazek.slowa_kluczowe.add("chemia")
    przypnij_grant(wynalazek, "PATENT/1", projekt=projekt)

    el = serializuj_patent(uczelnia, wynalazek)
    osadzony = el.find(f"{q('OriginatesFrom')}/{q('Project')}")
    assert osadzony is not None
    assert osadzony.get("id") == f"Projects/pj-{projekt.pk}"

    kolejnosc = nazwy_dzieci(el)
    assert kolejnosc.index("Keyword") < kolejnosc.index("OriginatesFrom")


@pytest.mark.django_db
def test_patent_bez_projektu_nie_ma_originates_from(uczelnia, wynalazek):
    przypnij_grant(wynalazek, "PATENT/BEZ", projekt=None)
    assert serializuj_patent(uczelnia, wynalazek).find(q("OriginatesFrom")) is None


@pytest.mark.django_db
def test_projekt_cudzej_uczelni_nie_wychodzi_w_patencie(
    uczelnia, wynalazek, obca_jednostka
):
    obcy = baker.make(Projekt, tytul="Cudzy projekt", jednostka=obca_jednostka)
    przypnij_grant(wynalazek, "PATENT/CUDZY", projekt=obcy)
    assert serializuj_patent(uczelnia, wynalazek).find(q("OriginatesFrom")) is None


# -- zgodność z XSD -------------------------------------------------------


@pytest.mark.django_db
def test_publikacja_i_patent_z_projektem_zgodne_z_xsd(
    uczelnia, publikacja, wynalazek, projekt, grantodawca, fabryka_autorow
):
    from cerif_export.tests.test_serializery import sprawdz, zbuduj_schemat

    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Kierowniczka"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )
    dodaj_finansowanie(projekt, grantodawca)
    publikacja.konferencja = baker.make(
        Konferencja, nazwa="Konferencja", skrocona_nazwa="K"
    )
    publikacja.save()
    publikacja.slowa_kluczowe.add("onkologia")
    wynalazek.slowa_kluczowe.add("chemia")
    przypnij_grant(publikacja, "XSD/PUB", projekt=projekt)
    przypnij_grant(wynalazek, "XSD/PAT", projekt=projekt)

    schemat = zbuduj_schemat()
    sprawdz(schemat, serializuj_publikacje(uczelnia, publikacja))
    sprawdz(schemat, serializuj_patent(uczelnia, wynalazek))


# -- integralność referencyjna na pełnym harveście ------------------------


@pytest.mark.django_db
def test_referencje_osadzonego_projektu_sa_rozwiazywalne(
    uczelnia, publikacja, wynalazek, projekt, grantodawca, fabryka_autorow
):
    """Każdy ``@id`` osadzony w ładunku ma swój rekord w harveście.

    To ta sama kontrola (5a), na której ``openaire-cris-validator``
    odrzuca całe repozytorium — tylko że tutaj referencje wychodzą
    z publikacji i patentu, a nie z rekordu projektu.
    """
    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Kierowniczka"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )
    dodaj_finansowanie(projekt, grantodawca)
    przypnij_grant(publikacja, "HARVEST/PUB", projekt=projekt)
    przypnij_grant(wynalazek, "HARVEST/PAT", projekt=projekt)

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
        el.text.split(":", 2)[-1]
        for el in korzen.iter()
        if el.tag.endswith("}identifier") and el.text
    }
    ns = uczelnia.oai_repository_identifier()
    assert identyfikatory.zbuduj(ns, projekt).split(":", 2)[-1] in wydane

    osadzone = set()
    for metadata in (el for el in korzen.iter() if el.tag.endswith("}metadata")):
        for el in metadata.iter():
            if el.get("id"):
                osadzone.add(el.get("id"))

    assert f"Projects/pj-{projekt.pk}" in osadzone
    assert osadzone <= wydane, sorted(osadzone - wydane)


@pytest.mark.django_db
def test_osoby_wylaczone_nie_wyciekaja_przez_osadzony_projekt(
    uczelnia, publikacja, projekt, fabryka_autorow
):
    """Przy ``eksport_cerif_osoby=False`` zespół projektu znika razem
    z resztą osób — inaczej wyłączenie setu byłoby pozorne, bo dane
    osobowe wychodziłyby okrężną drogą przez publikacje."""
    Projekt_Autor.objects.create(
        projekt=projekt,
        autor=fabryka_autorow("Kierowniczka"),
        rola=Projekt_Autor.ROLA_KIEROWNIK,
    )
    przypnij_grant(publikacja, "OSOBY/1", projekt=projekt)

    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    el = serializuj_publikacje(uczelnia, publikacja)
    osadzony = el.find(f"{q('OriginatesFrom')}/{q('Project')}")
    assert osadzony is not None
    assert osadzony.find(q("Team")) is None
    assert "Kierowniczka" not in etree.tostring(osadzony, encoding="unicode")


# -- koszt: serializer nie dotyka bazy ------------------------------------


@pytest.mark.django_db
def test_serializacja_publikacji_nie_rosnie_z_liczba_projektow(
    uczelnia, jednostka, fabryka_autorow, fabryka_wydawnictw, grantodawca
):
    """Osadzanie projektu w każdej publikacji to naturalny kandydat na N+1.

    Liczba zapytań na stronę harvestu musi być **stała**: cała robota
    siedzi w prefetchach providera i w prekomputowanych zbiorach
    widoczności. Gdy rośnie z liczbą publikacji z projektami, znaczy że
    serializer dociąga coś sam.
    """
    provider = provider_dla_setu(const.SET_PUBLICATIONS)
    autor = fabryka_autorow("Autorska")

    def zapytania_dla(ile):
        Grant_Rekordu.objects.all().delete()
        Grant.objects.all().delete()
        Wydawnictwo_Ciagle.objects.all().delete()
        Projekt.objects.all().delete()

        for numer in range(ile):
            wlasny = baker.make(Projekt, tytul=f"Projekt {numer}", jednostka=jednostka)
            dodaj_finansowanie(wlasny, grantodawca)
            Projekt_Autor.objects.create(
                projekt=wlasny,
                autor=baker.make("bpp.Autor", nazwisko=f"Nowak{numer}"),
                rola=Projekt_Autor.ROLA_KIEROWNIK,
            )
            rekord = fabryka_wydawnictw(
                Wydawnictwo_Ciagle,
                autor=autor,
                tytul_oryginalny=f"Praca {numer}",
            )
            przypnij_grant(rekord, f"NR/{numer}", projekt=wlasny)

        with CaptureQueriesContext(connection) as licznik:
            obiekty, _ = provider.strona(uczelnia, rozmiar=100)
            obiekty = list(obiekty)
            kontekst = KontekstSerializacji(
                namespace=NAMESPACE,
                uczelnia=uczelnia,
                widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
            )
            for obiekt in obiekty:
                if isinstance(obiekt, Wydawnictwo_Ciagle):
                    cerif_publication.serializuj(obiekt, kontekst)
        return len(licznik.captured_queries)

    assert zapytania_dla(1) == zapytania_dla(5)
