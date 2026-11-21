"""Integralność referencyjna projektów i finansowania — pełny harvest.

Testy pojedynczych builderów sprawdzają, że ``Project`` i ``Funding``
wyglądają jak trzeba. Nie sprawdzają rzeczy najważniejszej: czy encje, na
które te elementy **wskazują**, faktycznie wychodzą z endpointu. To dwie
niezależne warstwy — provider decyduje o zbiorze rekordów, serializer
o zbiorze referencji — i rozjeżdżają się po cichu.

Dlatego wszystko tutaj idzie przez ``ListRecords``, a nie przez providery
wołane wprost: brak wpisu w rejestrze serializerów albo pomylony ``setSpec``
widać wyłącznie na pełnej ścieżce OAI.

Sprawdzane referencje wychodzące:

* ``Project/Consortium/Coordinator`` → ``OrgUnit`` (jednostka realizująca),
* ``Project/Team/PrincipalInvestigator``, ``Project/Team/Member`` →
  ``Person`` (zespół projektu),
* ``Project/Funded/By`` → ``OrgUnit`` (grantodawca),
* ``Project/Funded/As`` → osadzone ``Funding`` z ``@id``,
* ``Funding/Funder`` → ``OrgUnit`` (grantodawca),

i to samo raz jeszcze wewnątrz ``Publication/OriginatesFrom``, gdzie cały
``<Project>`` jest osadzony w rekordzie publikacji.

Oba przełączniki uczelni (``eksport_cerif_osoby``, ``eksport_cerif_kwoty``)
są przebiegane w obu stanach. Przy wyłączonych osobach referencje do
``Person`` mają **zniknąć**, a nie zawisnąć — to najboleśniejsza klasa
błędu w kontroli integralności walidatora, bo objawia się dopiero na żywym
endpoincie komunikatem o nieznalezionym rekordzie.
"""

import pytest
from lxml import etree
from model_bakery import baker

from bpp.models import (
    Finansowanie,
    Grant,
    Grant_Rekordu,
    Instytucja_Finansujaca,
    Projekt,
    Projekt_Autor,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from cerif_export import const, identyfikatory
from cerif_export.oai import czasowniki
from cerif_export.oai.bledy import NS_PMH

BASE_URL = "https://cerif.example.org/cerif-oai/"

# Nazwa elementu encji CERIF → set, w którym musi wyjść jej pełny rekord.
# Encja osadzona Z identyfikatorem to obietnica: „ten rekord znajdziesz
# w harveście". Mapa zamienia obietnicę w sprawdzalny warunek.
SET_DLA_ENCJI = {
    "OrgUnit": const.SET_ORGUNITS,
    "Person": const.SET_PERSONS,
    "Project": const.SET_PROJECTS,
    "Funding": const.SET_FUNDING,
    "Publication": const.SET_PUBLICATIONS,
    "Patent": const.SET_PATENTS,
    "Event": const.SET_EVENTS,
}


def q(nazwa):
    """Nazwa elementu z przestrzeni nazw profilu CERIF."""
    return f"{{{const.NS_CERIF}}}{nazwa}"


def p(nazwa):
    """Nazwa elementu z przestrzeni nazw koperty OAI-PMH.

    Koperta (``record``, ``header``, ``setSpec``, ``metadata``) i ładunek
    (``Project``, ``OrgUnit``, …) żyją w **różnych** przestrzeniach nazw.
    Wyszukiwanie ``record`` w przestrzeni CERIF-a nic nie znajduje, a test
    milcząco przechodzi na pustym harveście — stąd dwie osobne funkcje.
    """
    return f"{{{NS_PMH}}}{nazwa}"


def lokalny(uczelnia, obj):
    """``@id`` encji tak, jak wystawia go serializer (bez prefiksu ``oai:``)."""
    return identyfikatory.zbuduj(uczelnia.oai_repository_identifier(), obj).split(
        ":", 2
    )[2]


# -- dane ----------------------------------------------------------------


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
        tytul="Badanie integralności",
        tytul_en="A study of integrity",
        akronim="BIN",
        status=Projekt.STATUS_W_TRAKCIE,
        data_rozpoczecia="2024-01-01",
        data_zakonczenia="2026-12-31",
        jednostka=jednostka,
    )


@pytest.fixture
def kierownik(fabryka_autorow):
    return fabryka_autorow("Kierowniczy", orcid="0000-0002-1825-0097")


@pytest.fixture
def wykonawca(fabryka_autorow):
    return fabryka_autorow("Wykonawczy")


@pytest.fixture
def finansowanie(projekt, grantodawca):
    return baker.make(
        Finansowanie,
        projekt=projekt,
        instytucja=grantodawca,
        typ=Finansowanie.TYP_GRANT,
        nazwa_programu="OPUS 24",
        numer_umowy="UMO-2024/53/B/NZ7/00001",
        kwota="1234567.89",
        waluta="PLN",
    )


@pytest.fixture
def publikacja(fabryka_wydawnictw, kierownik, projekt):
    """Publikacja przypięta do projektu przez ``Grant_Rekordu``.

    Autorem jest kierownik projektu, ale wykonawca już nie — inaczej test
    nie odróżniłby zbioru widoczności providera publikacji od zbioru
    dołożonego przez ``klucze_osadzonych_projektow``.
    """
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=kierownik)
    grant = baker.make(Grant, numer_projektu="UMO-2024/53/B/NZ7/00001", projekt=projekt)
    Grant_Rekordu.objects.create(rekord=rekord, grant=grant)
    return rekord


@pytest.fixture
def pelny_projekt(
    uczelnia,
    jednostka,
    projekt,
    kierownik,
    wykonawca,
    grantodawca,
    finansowanie,
    publikacja,
):
    """Uczelnia z projektem, zespołem, finansowaniem i publikacją grantową."""
    Projekt_Autor.objects.create(
        projekt=projekt, autor=kierownik, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    Projekt_Autor.objects.create(
        projekt=projekt, autor=wykonawca, rola=Projekt_Autor.ROLA_WYKONAWCA
    )
    return uczelnia


# -- harvest -------------------------------------------------------------


def harvest(uczelnia):
    """Zbierz ``[(setSpec, element metadanych)]`` z całego endpointu.

    Przechodzi tokeny wznowienia, bo pełny harvest bywa wielostronicowy,
    a rekord projektu i rekord finansowania siedzą w różnych setach —
    zatrzymanie się na pierwszej stronie testowałoby połowę problemu.
    """
    wyniki = []
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

        for rekord in korzen.iter(p("record")):
            naglowek = rekord.find(p("header"))
            if naglowek.get("status") == "deleted":
                # Nagrobek (faza 05b) to z definicji sam nagłówek — nie ma
                # ładunku, więc i nie ma referencji, które mogłyby zawisnąć.
                # Integralność referencyjną sprawdzamy na rekordach żywych.
                continue
            metadane = rekord.find(p("metadata"))
            assert metadane is not None and len(metadane), (
                "rekord bez ładunku metadanych"
            )
            wyniki.append((naglowek.findtext(p("setSpec")), metadane[0]))

        tokeny = [el for el in korzen.iter() if el.tag.endswith("}resumptionToken")]
        token = tokeny[0].text if tokeny else None
        if not token:
            return wyniki
    raise AssertionError("Harvest nie zakończył się po 50 stronach")


def wydane_identyfikatory(rekordy):
    """``{@id: setSpec}`` dla encji najwyższego poziomu każdego rekordu."""
    wynik = {}
    for set_spec, encja in rekordy:
        identyfikator = encja.get("id")
        assert identyfikator, f"rekord w secie {set_spec} bez @id"
        wynik[identyfikator] = set_spec
    return wynik


def referencje_wychodzace(rekordy):
    """``[(nazwa encji, @id, ścieżka)]`` dla każdej encji **osadzonej**.

    Encja osadzona bez ``@id`` jest w profilu dozwolona wprost i niczego nie
    obiecuje, więc nie jest referencją i tu nie trafia.
    """
    wynik = []
    for _, encja in rekordy:
        for potomek in encja.iter():
            if potomek is encja:
                continue
            identyfikator = potomek.get("id")
            if not identyfikator:
                continue
            wynik.append(
                (
                    etree.QName(potomek).localname,
                    identyfikator,
                    sciezka(encja, potomek),
                )
            )
    return wynik


def sciezka(korzen, el):
    """Czytelna ścieżka elementu w obrębie rekordu — do komunikatu błędu."""
    czlony = []
    biezacy = el
    while biezacy is not None and biezacy is not korzen:
        czlony.append(etree.QName(biezacy).localname)
        biezacy = biezacy.getparent()
    czlony.append(f"{etree.QName(korzen).localname}[@id={korzen.get('id')}]")
    return "/".join(reversed(czlony))


def encje_setu(rekordy, set_spec):
    """Encje najwyższego poziomu z danego setu."""
    return [encja for spec, encja in rekordy if spec == set_spec]


def jedyna(elementy, opis):
    assert len(elementy) == 1, f"oczekiwano jednego {opis}, jest {len(elementy)}"
    return elementy[0]


def sciezki_id(encja, *czlony):
    """``@id`` wszystkich elementów pod ścieżką złożoną z nazw lokalnych."""
    return [
        el.get("id") for el in encja.findall("/".join(q(nazwa) for nazwa in czlony))
    ]


# -- właściwe testy ------------------------------------------------------


@pytest.mark.parametrize("osoby", [True, False])
@pytest.mark.parametrize("kwoty", [True, False])
@pytest.mark.django_db
def test_zadna_referencja_projektu_nie_wisi(pelny_projekt, osoby, kwoty):
    """Każdy ``@id`` z encji osadzonej ma rekord we właściwym secie.

    Sprawdzenie idzie po **wszystkich** czterech kombinacjach przełączników,
    bo każdy z nich zawęża zbiór wydanych rekordów, a serializerów nie —
    i to jest dokładnie ten rozjazd, który produkuje wiszącą referencję.
    """
    uczelnia = pelny_projekt
    uczelnia.eksport_cerif_osoby = osoby
    uczelnia.eksport_cerif_kwoty = kwoty
    uczelnia.save()

    rekordy = harvest(uczelnia)
    assert rekordy, "harvest nie zwrócił żadnego rekordu"

    wydane = wydane_identyfikatory(rekordy)
    referencje = referencje_wychodzace(rekordy)
    assert referencje, "harvest nie zawiera ani jednej encji osadzonej z @id"

    wiszace = []
    for nazwa, identyfikator, gdzie in referencje:
        oczekiwany_set = SET_DLA_ENCJI.get(nazwa)
        assert oczekiwany_set, f"encja {nazwa!r} spoza mapy setów ({gdzie})"

        faktyczny_set = wydane.get(identyfikator)
        if faktyczny_set != oczekiwany_set:
            wiszace.append((gdzie, identyfikator, faktyczny_set or "BRAK REKORDU"))

    assert not wiszace, f"referencje nie do rozwiązania: {sorted(wiszace)}"


@pytest.mark.django_db
def test_projekt_referuje_zespol_jednostke_i_grantodawce(
    pelny_projekt, jednostka, kierownik, wykonawca, grantodawca, finansowanie
):
    """Komplet referencji rekordu ``Project`` — co do identyfikatora.

    Test „nic nie wisi" przechodzi także wtedy, gdy referencji po prostu
    nie ma. Ten pilnuje drugiej strony: że są i wskazują na te encje,
    na które powinny.
    """
    uczelnia = pelny_projekt
    rekordy = harvest(uczelnia)
    projekt_el = jedyna(encje_setu(rekordy, const.SET_PROJECTS), "rekordu Project")

    assert sciezki_id(projekt_el, "Consortium", "Coordinator", "OrgUnit") == [
        lokalny(uczelnia, jednostka)
    ]
    assert sciezki_id(projekt_el, "Team", "PrincipalInvestigator", "Person") == [
        lokalny(uczelnia, kierownik)
    ]
    assert sciezki_id(projekt_el, "Team", "Member", "Person") == [
        lokalny(uczelnia, wykonawca)
    ]
    assert sciezki_id(projekt_el, "Funded", "By", "OrgUnit") == [
        lokalny(uczelnia, grantodawca)
    ]
    assert sciezki_id(projekt_el, "Funded", "As", "Funding") == [
        lokalny(uczelnia, finansowanie)
    ]


@pytest.mark.django_db
def test_finansowanie_referuje_grantodawce(pelny_projekt, grantodawca):
    """Rekord ``Funding`` wskazuje grantodawcę przez ``Funder``."""
    uczelnia = pelny_projekt
    rekordy = harvest(uczelnia)
    funding_el = jedyna(encje_setu(rekordy, const.SET_FUNDING), "rekordu Funding")

    assert sciezki_id(funding_el, "Funder", "OrgUnit") == [
        lokalny(uczelnia, grantodawca)
    ]


@pytest.mark.django_db
def test_projekt_osadzony_w_publikacji_ma_te_same_referencje(
    pelny_projekt, projekt, jednostka, kierownik, wykonawca, grantodawca, finansowanie
):
    """``Publication/OriginatesFrom`` osadza pełny projekt — z referencjami.

    Zbiory widoczności providera publikacji budowane są z innego kodu niż
    zbiory providera projektów (``klucze_osadzonych_projektow``), więc to
    osobne ryzyko, nie powtórka poprzedniego testu. Wykonawca projektu nie
    jest autorem publikacji: gdyby zbiór nie obejmował zespołu projektu,
    ``Member`` wyszedłby bez ``@id``.
    """
    uczelnia = pelny_projekt
    rekordy = harvest(uczelnia)

    publikacje = encje_setu(rekordy, const.SET_PUBLICATIONS)
    osadzone = [
        el
        for encja in publikacje
        for el in encja.findall(f"{q('OriginatesFrom')}/{q('Project')}")
    ]
    osadzony = jedyna(osadzone, "osadzonego elementu Project")

    assert osadzony.get("id") == lokalny(uczelnia, projekt)
    assert sciezki_id(osadzony, "Consortium", "Coordinator", "OrgUnit") == [
        lokalny(uczelnia, jednostka)
    ]
    assert sciezki_id(osadzony, "Team", "PrincipalInvestigator", "Person") == [
        lokalny(uczelnia, kierownik)
    ]
    assert sciezki_id(osadzony, "Team", "Member", "Person") == [
        lokalny(uczelnia, wykonawca)
    ]
    assert sciezki_id(osadzony, "Funded", "By", "OrgUnit") == [
        lokalny(uczelnia, grantodawca)
    ]
    assert sciezki_id(osadzony, "Funded", "As", "Funding") == [
        lokalny(uczelnia, finansowanie)
    ]


@pytest.mark.django_db
def test_bez_eksportu_osob_zespol_znika_zamiast_zawisnac(pelny_projekt):
    """``eksport_cerif_osoby=False`` usuwa ``Team``, nie tylko ``@id``.

    Zostawienie samego kontenera z osobami bez identyfikatora przeszłoby
    kontrolę integralności, ale wystawiłoby nazwiska osób, których uczelnia
    świadomie nie eksportuje.
    """
    uczelnia = pelny_projekt
    uczelnia.eksport_cerif_osoby = False
    uczelnia.save()

    rekordy = harvest(uczelnia)
    assert not encje_setu(rekordy, const.SET_PERSONS), "set osób miał być pusty"

    # ``iter`` zwraca też sam element startowy, więc rekord ``Project``
    # sprawdza się tym samym przebiegiem, co projekt osadzony w publikacji.
    for set_spec in (const.SET_PROJECTS, const.SET_PUBLICATIONS):
        for encja in encje_setu(rekordy, set_spec):
            for projekt_el in encja.iter(q("Project")):
                assert projekt_el.find(q("Team")) is None, (
                    f"Team przetrwał wyłączenie eksportu osób w {set_spec}"
                )


@pytest.mark.django_db
def test_jednostka_poza_eksportem_znika_z_konsorcjum(pelny_projekt, jednostka):
    """Opt-out jednostki zabiera ``Consortium``, ale nie sam projekt.

    ``nie_eksportuj_przez_api`` dotyczy jednostki jako encji organizacyjnej,
    a nie prowadzonych w niej badań — rekord ``Project`` zostaje. Znika
    natomiast referencja do OrgUnit-a, którego harvester już nie zobaczy;
    kontener ``Consortium`` musi zniknąć razem z nią, bo dziecko jest w nim
    wobec XSD obowiązkowe.
    """
    uczelnia = pelny_projekt
    jednostka.nie_eksportuj_przez_api = True
    jednostka.save()

    rekordy = harvest(uczelnia)
    wydane = wydane_identyfikatory(rekordy)
    assert lokalny(uczelnia, jednostka) not in wydane

    projekt_el = jedyna(encje_setu(rekordy, const.SET_PROJECTS), "rekordu Project")
    assert projekt_el.find(q("Consortium")) is None

    for _, identyfikator, gdzie in referencje_wychodzace(rekordy):
        assert identyfikator in wydane, f"wisząca referencja w {gdzie}"


@pytest.mark.django_db
def test_kwoty_finansowania_zalezne_od_przelacznika(pelny_projekt, finansowanie):
    """``Funding/Amount`` wychodzi wyłącznie przy zgodzie uczelni.

    Sprawdzane na wszystkich wystąpieniach ``Funding`` naraz — rekordzie
    setu i elementach osadzonych w ``Project/Funded/As`` — bo to ta sama
    funkcja serializująca, ale różne konteksty wywołania.
    """
    uczelnia = pelny_projekt

    for wlaczone, oczekiwane in ((True, 1), (False, 0)):
        uczelnia.eksport_cerif_kwoty = wlaczone
        uczelnia.save()

        rekordy = harvest(uczelnia)
        kwoty = [
            el
            for _, encja in rekordy
            for funding in encja.iter(q("Funding"))
            for el in funding.findall(q("Amount"))
        ]
        # Jedno finansowanie, ale trzy wystąpienia elementu ``Funding``:
        # rekord setu, osadzenie w rekordzie projektu i osadzenie
        # w projekcie doczepionym do publikacji.
        assert len(kwoty) == 3 * oczekiwane, (
            f"eksport_cerif_kwoty={wlaczone}: {len(kwoty)} elementów Amount"
        )
        for kwota in kwoty:
            assert kwota.get("currency") == "PLN"
