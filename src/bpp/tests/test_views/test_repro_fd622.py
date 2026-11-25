"""FD#622 — szukanie odpowiednika po ISBN / DOI nie znajdowało rekordu,
który w PBN istnieje (PBN przy wysyłce: „Publikacja o identycznym ISBN lub
ISMN już istnieje").

Przypadek klienta: rozdział książki wprowadzony jako wydawnictwo zwarte
z ISBN-em książki. PBN ma rekord KSIĄŻKI z tym ISBN-em — inny tytuł, często
inny rok. Stary kod pytał PBN o jedną formę ISBN-u z filtrem roku, odrzucał
rekordy, których nie umiał automatycznie dopasować do pracy w BPP (tytuł +
rok), a lokalnie szukał po dokładnym ISBN-ie i roku — więc nie znajdował nic.

Od FD#515 osobne adresy „Pobierz po ISBN" / „Pobierz po DOI" nie istnieją —
te same zachowania pilnowane są na jednym widoku przycisku „Pobierz z PBN"
(``api_get_pbn_by_identifiers``). Różnica względem pierwotnych asercji:
rekord znaleziony po samym ISBN-ie przy innym tytule nie trafia do pola
automatycznie (brak ``id``), tylko na listę kandydatów do wyboru.
"""

import json

import pytest
from django.urls import reverse

from bpp.views.api.pbn_odpowiednik import (
    BRAK,
    DO_WYBORU,
    PEWNY,
    PobierzOdpowiednikPublikacjiView,
)
from fixtures.pbn_api import pbn_general_json
from pbn_api.models import Publication

UID_KSIAZKI = "6accb7c13d7d997e0c94d1b6"
UID_ROZDZIALU = "6accb7c13d7d997e0c94d1b7"
ISBN_Z_MYSLNIKAMI = "978-0-12-819517-8"
ISBN = "9780128195178"
DOI_ROZDZIALU = "10.1016/B978-0-12-819517-8.00012-6"
TYTUL_KSIAZKI = "Environmental Impact of Agro-Food Industry and Food Consumption"
TYTUL_ROZDZIALU = "Utilities in the Food Factories"


def _ksiazka_json(isbn=ISBN_Z_MYSLNIKAMI):
    return pbn_general_json(
        {"type": "BOOK", "title": TYTUL_KSIAZKI, "year": 2020, "isbn": isbn},
        mongoId=UID_KSIAZKI,
    )


def _rozdzial_json():
    return pbn_general_json(
        {
            "type": "CHAPTER",
            "title": TYTUL_ROZDZIALU,
            "year": 2021,
            "doi": DOI_ROZDZIALU,
            "book": {"title": TYTUL_KSIAZKI, "isbn": ISBN_Z_MYSLNIKAMI},
        },
        mongoId=UID_ROZDZIALU,
    )


class FakePBNSearch:
    """Wyszukiwarka PBN: zwraca rekord tylko dla DOKŁADNIE tej formy
    identyfikatora, która jest w ``odpowiada_na``; filtr ``year`` działa jak
    w PBN (zawęża)."""

    def __init__(self, rekord, element, odpowiada_na):
        self.rekord = rekord
        self.element = element
        self.odpowiada_na = odpowiada_na
        self.zapytania = []

    def __call__(self, **kw):
        self.zapytania.append(kw)
        obj = self.rekord["versions"][0]["object"]
        if kw.get(self.element) != self.odpowiada_na:
            return []
        if "year" in kw and kw["year"] != obj.get("year"):
            return []
        return [{"mongoId": self.rekord["mongoId"]}]


@pytest.fixture
def rozdzial_w_bpp(wydawnictwo_zwarte):
    wydawnictwo_zwarte.tytul_oryginalny = TYTUL_ROZDZIALU
    wydawnictwo_zwarte.isbn = ISBN_Z_MYSLNIKAMI
    wydawnictwo_zwarte.doi = DOI_ROZDZIALU.lower()
    wydawnictwo_zwarte.rok = 2021
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


def _post(rf, pole, user, uczelnia, t, rok="2021", tytul=""):
    """Żądanie przycisku „Pobierz z PBN" z jednym wypełnionym polem
    identyfikatora (``isbn`` albo ``doi``)."""
    req = rf.post("/", data={pole: t, "rok": rok, "tytul_oryginalny": tytul})
    req.user = user
    req._uczelnia = uczelnia
    return json.loads(PobierzOdpowiednikPublikacjiView.as_view()(req).content)


def _kandydaci(res):
    return [k["id"] for k in res["kandydaci"]]


def _podepnij_pbn(mocker, pbn_client, fake, *rekordy):
    mocker.patch.object(pbn_client, "search_publications", side_effect=fake)
    for rekord in rekordy:
        pbn_client.transport.return_values[
            f"/api/v1/publications/id/{rekord['mongoId']}"
        ] = rekord


@pytest.mark.django_db
def test_fd622_isbn_rozdzialu_znajduje_ksiazke_w_pbn(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    """Sedno zgłoszenia: rekord PBN (książka) ma inny tytuł i rok niż
    rozdział w BPP — mimo to musi zostać pokazany redaktorowi."""
    fake = FakePBNSearch(_ksiazka_json(), "isbn", ISBN)
    _podepnij_pbn(mocker, pbn_client, fake, _ksiazka_json())

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, rozdzial_w_bpp.isbn)

    # Pokazany do wyboru — inny tytuł, więc nie jest wstawiany sam.
    assert res["status"] == DO_WYBORU, res
    assert _kandydaci(res) == [UID_KSIAZKI]
    assert "id" not in res
    assert res["kandydaci"][0]["typ"] == "BOOK"
    # Rekord został zapisany lokalnie, żeby wyszukiwarka pola go pokazała.
    assert Publication.objects.filter(pk=UID_KSIAZKI).exists()


@pytest.mark.django_db
def test_fd622_bez_automatycznego_wiazania(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp, zwarte_maker
):
    """Widok tylko podpowiada — nie ustawia odpowiednika w PBN żadnemu
    rekordowi BPP (stary kod robił to po cichu z rekordem dopasowanym po
    tytule)."""
    ksiazka_w_bpp = zwarte_maker(
        tytul_oryginalny=TYTUL_KSIAZKI, rok=2020, isbn=ISBN_Z_MYSLNIKAMI
    )
    fake = FakePBNSearch(_ksiazka_json(), "isbn", ISBN)
    _podepnij_pbn(mocker, pbn_client, fake, _ksiazka_json())

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, ISBN, "2020", tytul=TYTUL_KSIAZKI)

    assert res["status"] == PEWNY, res
    assert res.get("id") == UID_KSIAZKI, res
    ksiazka_w_bpp.refresh_from_db()
    rozdzial_w_bpp.refresh_from_db()
    assert ksiazka_w_bpp.pbn_uid_id is None
    assert rozdzial_w_bpp.pbn_uid_id is None


@pytest.mark.django_db
def test_fd622_pbn_odpowiada_tylko_na_isbn_z_myslnikami(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    """Gdy PBN nie znajduje formy bez myślników, próbujemy z myślnikami."""
    fake = FakePBNSearch(_ksiazka_json(), "isbn", ISBN_Z_MYSLNIKAMI)
    _podepnij_pbn(mocker, pbn_client, fake, _ksiazka_json())

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, ISBN)

    assert _kandydaci(res) == [UID_KSIAZKI], res
    assert [z["isbn"] for z in fake.zapytania][:1] == [ISBN]


@pytest.mark.django_db
def test_fd622_isbn10_znajduje_rekord_z_isbn13(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    fake = FakePBNSearch(_ksiazka_json(), "isbn", ISBN)
    _podepnij_pbn(mocker, pbn_client, fake, _ksiazka_json())

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, "0-12-819517-7")

    assert _kandydaci(res) == [UID_KSIAZKI], res


@pytest.mark.django_db
def test_fd622_najpierw_lokalnie_bez_pytania_pbn(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    """Rekordy z lokalnej kopii PBN (książka i rozdział, oba z ISBN-em
    książki) — znalezione bez zapytania do PBN, oba pokazane do wyboru."""
    from pbn_integrator.utils import zapisz_mongodb

    zapisz_mongodb(_ksiazka_json(), Publication)
    zapisz_mongodb(_rozdzial_json(), Publication)
    search = mocker.patch.object(pbn_client, "search_publications")

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, ISBN_Z_MYSLNIKAMI)

    search.assert_not_called()
    # Dwa rekordy → lista do wyboru (nic nie jest wstawiane samo),
    # a pierwszy na liście jest rekord z rokiem z formularza (rozdział, 2021).
    assert res["status"] == DO_WYBORU
    assert "id" not in res
    assert _kandydaci(res) == [UID_ROZDZIALU, UID_KSIAZKI]


@pytest.mark.django_db
def test_fd622_lokalnie_przez_rekord_bpp_z_odpowiednikiem(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp, zwarte_maker
):
    """Książka w BPP ma już odpowiednik w PBN, a jej ISBN zapisano inaczej
    (bez myślników) niż w szukanym rekordzie — to też jest trafienie."""
    from pbn_integrator.utils import zapisz_mongodb

    pub = zapisz_mongodb(_ksiazka_json(isbn="brak"), Publication)
    zwarte_maker(tytul_oryginalny=TYTUL_KSIAZKI, rok=2020, isbn=ISBN, pbn_uid=pub)
    search = mocker.patch.object(pbn_client, "search_publications")

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, ISBN_Z_MYSLNIKAMI)

    search.assert_not_called()
    assert _kandydaci(res) == [UID_KSIAZKI], res


@pytest.mark.django_db
def test_fd622_doi_lokalnie_bez_wzgledu_na_wielkosc_liter(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    """PBN trzyma DOI wielkimi literami, redaktor wpisał adres doi.org
    małymi — stary kod porównywał lokalnie dokładnie i nie znajdował."""
    from pbn_integrator.utils import zapisz_mongodb

    zapisz_mongodb(_rozdzial_json(), Publication)
    search = mocker.patch.object(pbn_client, "search_publications")

    res = _post(
        rf,
        "doi",
        admin_user,
        pbn_uczelnia,
        "https://doi.org/" + DOI_ROZDZIALU.lower(),
    )

    search.assert_not_called()
    assert res.get("id") == UID_ROZDZIALU, res


@pytest.mark.django_db
def test_fd622_doi_w_pbn_w_oryginalnej_wielkosci_liter(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user, rozdzial_w_bpp
):
    """PBN odpowiada tylko na DOI zapisane tak jak u siebie (wielkie litery);
    stary kod wysyłał wyłącznie małe litery i filtr roku."""
    fake = FakePBNSearch(_rozdzial_json(), "doi", DOI_ROZDZIALU)
    _podepnij_pbn(mocker, pbn_client, fake, _rozdzial_json())

    res = _post(
        rf,
        "doi",
        admin_user,
        pbn_uczelnia,
        "https://doi.org/" + DOI_ROZDZIALU,
        rok="2022",
    )

    assert res.get("id") == UID_ROZDZIALU, res


@pytest.mark.django_db
def test_fd622_nic_nie_znaleziono_podaje_sprawdzone_formy(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user
):
    fake = FakePBNSearch(_ksiazka_json(), "isbn", "nigdy")
    _podepnij_pbn(mocker, pbn_client, fake)

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, ISBN)

    assert res["status"] == BRAK
    assert res["kandydaci"] == []
    assert ISBN in res["komunikat"]
    assert ISBN_Z_MYSLNIKAMI in res["komunikat"]


def test_fd622_formy_isbn():
    from bpp.views.api.pbn_get_by_parameter import formy_isbn

    assert formy_isbn(ISBN_Z_MYSLNIKAMI) == [
        ISBN,
        "0128195177",
        ISBN_Z_MYSLNIKAMI,
        "0-12-819517-7",
    ]
    assert formy_isbn("") == []
    assert formy_isbn("  ") == []


def test_fd622_formy_doi():
    from bpp.views.api.pbn_get_by_parameter import formy_doi

    assert formy_doi("https://doi.org/" + DOI_ROZDZIALU) == [
        DOI_ROZDZIALU,
        DOI_ROZDZIALU.lower(),
    ]
    assert formy_doi("") == []


@pytest.mark.django_db
def test_fd622_wyszukiwarka_pola_znajduje_isbn_z_myslnikami(admin_client):
    """Wyszukiwarka pola „Odpowiednik w PBN": ISBN z myślnikami trafia
    w rekord zapisany bez myślników, a podpowiedź pokazuje rodzaj rekordu."""
    from pbn_integrator.utils import zapisz_mongodb

    zapisz_mongodb(_ksiazka_json(), Publication)

    res = admin_client.get(
        reverse("bpp:publication-autocomplete"), {"q": ISBN_Z_MYSLNIKAMI}
    )

    wyniki = res.json()["results"]
    assert [w["id"] for w in wyniki] == [UID_KSIAZKI]
    assert "[książka]" in wyniki[0]["text"]


@pytest.mark.django_db
def test_fd622_smieci_zamiast_isbn_nie_lapia_przypadkowych_rekordow(
    rf, mocker, pbn_uczelnia, pbn_client, admin_user
):
    """Wpis niebędący ISBN-em („83") nie może trafić lokalnie w każdy
    rekord, którego ISBN zawiera ten ciąg."""
    from pbn_integrator.utils import zapisz_mongodb

    zapisz_mongodb(_ksiazka_json(isbn="978-83-01-00000-0"), Publication)
    fake = FakePBNSearch(_ksiazka_json(), "isbn", "nigdy")
    _podepnij_pbn(mocker, pbn_client, fake)

    res = _post(rf, "isbn", admin_user, pbn_uczelnia, "83")

    assert res["status"] == BRAK, res
    assert res["kandydaci"] == []
