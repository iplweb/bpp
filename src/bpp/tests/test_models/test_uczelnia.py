import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia


def test_Uczelnia_wydzialy(uczelnia, wydzial):
    assert uczelnia.wydzialy().exists()


def test_Uczelnia_jednostki(uczelnia, jednostka):
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
