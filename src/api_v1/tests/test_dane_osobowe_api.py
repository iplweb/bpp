"""Dane osobowe autorów i autorzy ukryci (``pokazuj=False``) w ``/api/v1/``.

Kontrakt: widzą je wyłącznie użytkownicy z uprawnieniem do wprowadzania
danych (grupa ``GR_WPROWADZANIE_DANYCH``) oraz superuser. Pozostali
zalogowani dostają dokładnie to samo, co anonim.
"""

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Autor_Jednostka, Jednostka

EMAIL = "jan.kowalski@example.com"
URODZONY = date(1970, 3, 15)
POPRZEDNIE = "Nowakowska"


def _klient(user=None):
    c = APIClient()
    if user is not None:
        c.force_authenticate(user=user)
    return c


def _anonim():
    return _klient()


def _zwykly_zalogowany():
    return _klient(baker.make("bpp.BppUser", is_staff=False, is_superuser=False))


def _redaktor():
    # Celowo bez is_staff i bez is_superuser — decyduje sama grupa.
    u = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    return _klient(u)


def _superuser():
    return _klient(baker.make("bpp.BppUser", is_staff=True, is_superuser=True))


BEZ_UPRAWNIEN = [
    pytest.param(_anonim, id="anonim"),
    pytest.param(_zwykly_zalogowany, id="zwykly_zalogowany"),
]
Z_UPRAWNIENIAMI = [
    pytest.param(_redaktor, id="redaktor"),
    pytest.param(_superuser, id="superuser"),
]


def _autor(**kw):
    dane = dict(
        nazwisko="Kowalski",
        imiona="Jan",
        pokazuj=True,
        email=EMAIL,
        urodzony=URODZONY,
        poprzednie_nazwiska=POPRZEDNIE,
        pokazuj_poprzednie_nazwiska=False,
    )
    dane.update(kw)
    return baker.make(Autor, **dane)


def _detal(klient, autor):
    return klient.get(reverse("api_v1:autor-detail", args=(autor.pk,)))


def _lista(klient, query=""):
    return klient.get(reverse("api_v1:autor-list") + query)


def _ids(res):
    return [row["id"] for row in res.json()["results"]]


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_autor_detal_bez_danych_osobowych(fabryka):
    autor = _autor()

    res = _detal(fabryka(), autor)

    assert res.status_code == 200
    data = res.json()
    assert "email" not in data
    assert data["urodzony"] is None
    assert data["poprzednie_nazwiska"] == ""
    tekst = str(data)
    assert EMAIL not in tekst
    assert "1970-03-15" not in tekst
    assert POPRZEDNIE not in tekst


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_autor_lista_bez_danych_osobowych(fabryka):
    _autor()

    res = _lista(fabryka())

    tekst = str(res.json())
    assert EMAIL not in tekst
    assert "1970-03-15" not in tekst
    assert POPRZEDNIE not in tekst


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_autor_poprzednie_nazwiska_gdy_autor_zezwala(fabryka):
    autor = _autor(pokazuj_poprzednie_nazwiska=True)

    res = _detal(fabryka(), autor)

    assert res.json()["poprzednie_nazwiska"] == POPRZEDNIE


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", Z_UPRAWNIENIAMI)
def test_autor_detal_z_danymi_osobowymi(fabryka):
    autor = _autor()

    data = _detal(fabryka(), autor).json()

    assert data["email"] == EMAIL
    assert data["urodzony"] == "1970-03-15"
    assert data["poprzednie_nazwiska"] == POPRZEDNIE


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_autor_ukryty_niewidoczny(fabryka):
    widoczny = _autor(nazwisko="Widoczny")
    ukryty = _autor(nazwisko="Ukryty", pokazuj=False)
    klient = fabryka()

    ids = _ids(_lista(klient))

    assert widoczny.pk in ids
    assert ukryty.pk not in ids
    assert _detal(klient, ukryty).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", Z_UPRAWNIENIAMI)
def test_autor_ukryty_widoczny_dla_uprawnionych(fabryka):
    ukryty = _autor(nazwisko="Ukryty", pokazuj=False)
    klient = fabryka()

    assert ukryty.pk in _ids(_lista(klient))
    assert _detal(klient, ukryty).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN + Z_UPRAWNIENIAMI)
@pytest.mark.parametrize(
    "query",
    [
        f"?email={EMAIL}",
        "?email__icontains=kowalski",
        "?urodzony=1970-03-15",
        "?urodzony__year=1970",
        "?poprzednie_nazwiska=Nowakowska",
    ],
)
def test_autor_brak_filtrowania_po_danych_osobowych(fabryka, query):
    """Filtry po polach osobowych nie istnieją — parametr jest ignorowany,
    więc wynik nie zależy od wartości pola."""
    _autor()
    _autor(nazwisko="Inny", email="inny@example.com", urodzony=date(1980, 1, 1))

    res = _lista(fabryka(), query)

    assert res.status_code == 200
    assert res.json()["count"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
@pytest.mark.parametrize("ordering", ["urodzony", "-urodzony", "email", "-email"])
def test_autor_brak_sortowania_po_danych_osobowych(fabryka, ordering):
    """``?ordering=`` po polach osobowych nie zmienia kolejności wyników."""
    a = _autor(nazwisko="Aaa", email="a@example.com", urodzony=date(1990, 1, 1))
    b = _autor(nazwisko="Bbb", email="b@example.com", urodzony=date(1960, 1, 1))
    klient = fabryka()

    bazowa = _ids(_lista(klient))
    posortowana = _ids(_lista(klient, f"?ordering={ordering}"))

    assert set(bazowa) == {a.pk, b.pk}
    assert posortowana == bazowa


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_autor_jednostka_bez_ukrytych(fabryka):
    jednostka = baker.make(Jednostka)
    widoczny = _autor(nazwisko="Widoczny")
    ukryty = _autor(nazwisko="Ukryty", pokazuj=False)
    aj_widoczny = baker.make(Autor_Jednostka, autor=widoczny, jednostka=jednostka)
    aj_ukryty = baker.make(Autor_Jednostka, autor=ukryty, jednostka=jednostka)
    klient = fabryka()

    ids = _ids(klient.get(reverse("api_v1:autor_jednostka-list")))

    assert aj_widoczny.pk in ids
    assert aj_ukryty.pk not in ids
    res = klient.get(reverse("api_v1:autor_jednostka-detail", args=(aj_ukryty.pk,)))
    assert res.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", Z_UPRAWNIENIAMI)
def test_autor_jednostka_ukryci_widoczni_dla_uprawnionych(fabryka):
    jednostka = baker.make(Jednostka)
    ukryty = _autor(nazwisko="Ukryty", pokazuj=False)
    aj_ukryty = baker.make(Autor_Jednostka, autor=ukryty, jednostka=jednostka)

    ids = _ids(fabryka().get(reverse("api_v1:autor_jednostka-list")))

    assert aj_ukryty.pk in ids


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_nagroda_bez_adnotacji(fabryka):
    nagroda = baker.make(
        "bpp.Nagroda",
        object=baker.make("bpp.Wydawnictwo_Zwarte"),
        adnotacja="notatka wewnetrzna",
    )

    data = fabryka().get(reverse("api_v1:nagroda-detail", args=(nagroda.pk,))).json()

    assert "adnotacja" not in data
    assert "notatka wewnetrzna" not in str(data)


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", Z_UPRAWNIENIAMI)
def test_nagroda_z_adnotacja_dla_uprawnionych(fabryka):
    nagroda = baker.make(
        "bpp.Nagroda",
        object=baker.make("bpp.Wydawnictwo_Zwarte"),
        adnotacja="notatka wewnetrzna",
    )

    data = fabryka().get(reverse("api_v1:nagroda-detail", args=(nagroda.pk,))).json()

    assert data["adnotacja"] == "notatka wewnetrzna"


@pytest.mark.django_db
def test_zapytanie_autor_zwykly_zalogowany_odrzucony():
    res = _zwykly_zalogowany().get(
        "/api/v1/zapytanie/autor/", {"q": 'nazwisko ~ "Kowal"'}
    )
    assert res.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sciezka,q",
    [
        ("/api/v1/zapytanie/autor/", 'email ~ "kowalski"'),
        ("/api/v1/zapytanie/autor/", 'urodzony = "1970-03-15"'),
        ("/api/v1/zapytanie/autorzy/", 'autor.email ~ "kowalski"'),
        ("/api/v1/zapytanie/autorzy/", 'autor.urodzony = "1970-03-15"'),
    ],
)
def test_zapytanie_brak_filtrowania_po_danych_osobowych(sciezka, q):
    """Schemat DjangoQL po API nie wystawia pól osobowych — nawet
    uprawnionemu (agent-facing)."""
    _autor()

    res = _superuser().get(sciezka, {"q": q})

    assert res.status_code == 400


@pytest.mark.django_db
def test_zapytanie_autorzy_kontrola_pozytywna():
    """Kontrola: trawersacja ``autor.*`` istnieje w schemacie /autorzy/,
    więc 400 dla pól osobowych wyżej nie wynika z braku relacji."""
    res = _superuser().get(
        "/api/v1/zapytanie/autorzy/", {"q": 'autor.nazwisko ~ "Kowal"'}
    )

    assert res.status_code == 200
