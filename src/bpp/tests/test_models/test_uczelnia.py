import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import override_settings
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.reporting import rollbar_reporter


def test_Uczelnia_wydzialy(uczelnia):
    # Faza B (#438): ``Uczelnia.wydzialy()`` nie zwraca już modeli
    # ``Wydzial`` -- pokazuje widoczne jednostki TOP-LEVEL (tak samo jak
    # ``jednostki()``). Węzły-lustra wydziałów są tworzone jako
    # ``widoczna=False`` (patrz ``struktura_konwersja.py``), więc fixture
    # ``wydzial`` sama w sobie tu nie wystarczy -- potrzebna widoczna
    # jednostka top-level.
    from bpp.tests.util import any_jednostka

    any_jednostka(wydzial=None, uczelnia=uczelnia)
    assert uczelnia.wydzialy().exists()


def test_Uczelnia_jednostki(uczelnia):
    # Faza B (#438): ``Uczelnia.jednostki()`` = jednostki TOP-LEVEL (parent IS
    # NULL) i widoczne. Fixture ``jednostka`` wisi teraz pod ukrytym węzłem-
    # lustrem (nie-top-level), więc tworzymy jednostkę top-level wprost.
    from bpp.tests.util import any_jednostka

    any_jednostka(wydzial=None, uczelnia=uczelnia)
    assert uczelnia.jednostki().exists()


def test_Uczelnia_clean_pbn_biezaco_tak_integracja_nie(uczelnia):
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_integracja = False

    with pytest.raises(ValidationError, match="nie używasz integracji"):
        uczelnia.clean()


@pytest.mark.django_db
def test_Uczelnia_pbn_client():
    uczelnia = baker.make(
        Uczelnia,
        nazwa="Testowa uczelnia",
        skrot="TU",
    )

    uczelnia.save()

    uczelnia.refresh_from_db()

    try:
        res = uczelnia.pbn_client()
        raise Exception(
            f"This should not happen {uczelnia.pbn_app_name} {uczelnia} {uczelnia.pbn_client} {res}"
        )
    except ImproperlyConfigured:
        pass

    uczelnia.pbn_app_name = "foo"
    uczelnia.save()

    uczelnia.pbn_app_token = ""
    uczelnia.save()

    try:
        res = uczelnia.pbn_client()
        raise Exception(
            f"This should not happen {uczelnia.pbn_app_name} {uczelnia} {uczelnia.pbn_client} {res}"
        )
    except ImproperlyConfigured:
        pass

    uczelnia.pbn_app_token = "foo"
    uczelnia.save()

    assert uczelnia.pbn_client()


@pytest.mark.django_db
@override_settings(PBN_CLIENT_HTTP_TIMEOUT="1,9")
def test_uczelnia_pbn_client_injects_bpp_transport_policy(uczelnia):
    uczelnia.pbn_app_name = "app"
    uczelnia.pbn_app_token = "token"
    uczelnia.pbn_api_root = "https://pbn.example"

    client = uczelnia.pbn_client("user-token")

    assert client.transport.timeout == (1.0, 9.0)
    assert client.transport.reporter is rollbar_reporter


@pytest.mark.django_db
def test_uczelnia_deklaracja_dostepnosci_tekst(uczelnia, client):
    TEKST_Z_HTML = b"<h1>TEST</h1>"
    uczelnia.pokazuj_deklaracje_dostepnosci = (
        Uczelnia.DeklaracjaDostepnosciChoices.TEKST
    )
    uczelnia.deklaracja_dostepnosci_tekst = TEKST_Z_HTML
    uczelnia.save()

    url_deklaracji_bpp = reverse("bpp:browse_deklaracja_dostepnosci")
    res = client.get(url_deklaracji_bpp)
    assert TEKST_Z_HTML in res.content

    res = client.get("/", follow=True)
    assert bytes(url_deklaracji_bpp, "ascii") in res.content


@pytest.mark.django_db
def test_uczelnia_deklaracja_dostepnosci_url(uczelnia, client):
    uczelnia.pokazuj_deklaracje_dostepnosci = (
        Uczelnia.DeklaracjaDostepnosciChoices.ZEWNETRZNY_URL
    )
    uczelnia.deklaracja_dostepnosci_url = "https://onet.pl"
    uczelnia.save()

    res = client.get(reverse("bpp:browse_deklaracja_dostepnosci"))
    assert b"https://onet.pl" in res.content

    res = client.get("/", follow=True)
    assert b"https://onet.pl" in res.content
