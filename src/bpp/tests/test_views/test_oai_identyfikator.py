"""Identyfikator repozytorium OAI-PMH pochodzi z konfiguracji uczelni.

W OAI-PMH identyfikator ma postać ``oai:<repozytorium>:<id-lokalny>``, gdzie
człon środkowy wskazuje repozytorium źródłowe. W instalacji multi-hosted
wynika on z uczelni rozstrzygniętej z requestu (domena → Site → Uczelnia),
dzięki czemu każda uczelnia ma własną, rozłączną przestrzeń identyfikatorów.
"""

import pytest
from django.contrib.sites.models import Site
from django.urls import reverse

from bpp.models import Uczelnia
from bpp.models.cache import Rekord
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import any_autor, any_ciagle, any_jednostka
from bpp.util import rebuild_contenttypes

OBCY_IDENTYFIKATOR_REPOZYTORIUM = "inne-repozytorium.example.org"


def _charakter_widoczny_w_oai():
    """Endpoint wydaje wyłącznie rekordy o niepustym ``nazwa_w_primo``."""
    ch, _ = Charakter_Formalny.objects.get_or_create(
        skrot="AC", defaults={"nazwa": "Artykuł w czasopiśmie"}
    )
    if ch.nazwa_w_primo != "Artykuł":
        ch.nazwa_w_primo = "Artykuł"
        ch.save()
    return ch


def _rekord_dla_uczelni(uczelnia, tytul):
    """Publikacja przypisana do uczelni przez jednostkę autorstwa."""
    aut, _ = Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    praca = any_ciagle(
        tytul_oryginalny=tytul, charakter_formalny=_charakter_widoczny_w_oai()
    )
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=praca,
        autor=any_autor(nazwisko=f"Autor {tytul}"),
        jednostka=any_jednostka(uczelnia=uczelnia),
        typ_odpowiedzialnosci=aut,
    )
    return praca


def _uczelnia_na_domenie(domena, nazwa, skrot, identyfikator_oai=""):
    site, _ = Site.objects.get_or_create(domain=domena, defaults={"name": domena})
    return Uczelnia.objects.create(
        nazwa=nazwa,
        skrot=skrot,
        site=site,
        oai_identyfikator_repozytorium=identyfikator_oai,
    )


@pytest.fixture
def oai_url(db):
    rebuild_contenttypes()
    return reverse("bpp:oai")


# --- warstwa modelu -------------------------------------------------------


@pytest.mark.django_db
def test_oai_repository_identifier_bierze_jawne_pole():
    uczelnia = _uczelnia_na_domenie(
        "nowa.example.com", "Uczelnia", "U1", identyfikator_oai="stara.example.com"
    )
    assert uczelnia.oai_repository_identifier() == "stara.example.com"


@pytest.mark.django_db
def test_oai_repository_identifier_puste_pole_to_domena_site():
    uczelnia = _uczelnia_na_domenie("bpp.example.com", "Uczelnia", "U1")
    assert uczelnia.oai_repository_identifier() == "bpp.example.com"


@pytest.mark.django_db
def test_oai_repository_identifier_ignoruje_biale_znaki():
    uczelnia = _uczelnia_na_domenie(
        "bpp.example.com", "Uczelnia", "U1", identyfikator_oai="   "
    )
    assert uczelnia.oai_repository_identifier() == "bpp.example.com"


# --- ListRecords ----------------------------------------------------------


@pytest.mark.django_db
def test_oai_list_records_uzywa_identyfikatora_uczelni(client, oai_url, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = _uczelnia_na_domenie("bpp.przyklad.edu.pl", "Przykładowa", "PRZ")
    _rekord_dla_uczelni(uczelnia, "Publikacja przykładowa")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={"verb": "ListRecords", "metadataPrefix": "oai_dc"},
        HTTP_HOST="bpp.przyklad.edu.pl",
    )

    assert res.status_code == 200
    assert "oai:bpp.przyklad.edu.pl:" in res.content.decode()


@pytest.mark.django_db
def test_oai_list_records_jawne_pole_wygrywa_z_domena(client, oai_url, settings):
    """Uczelnia może zachować identyfikator po zmianie domeny serwisu."""
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = _uczelnia_na_domenie(
        "nowa.przyklad.edu.pl",
        "Przykładowa",
        "PRZ",
        identyfikator_oai="stara.przyklad.edu.pl",
    )
    _rekord_dla_uczelni(uczelnia, "Publikacja przykładowa")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={"verb": "ListRecords", "metadataPrefix": "oai_dc"},
        HTTP_HOST="nowa.przyklad.edu.pl",
    )
    tresc = res.content.decode()

    assert "oai:stara.przyklad.edu.pl:" in tresc
    assert "oai:nowa.przyklad.edu.pl:" not in tresc


@pytest.mark.django_db
def test_oai_list_records_dwie_uczelnie_maja_rozne_namespace(client, oai_url, settings):
    """Jedna instalacja, dwie domeny → dwie rozłączne przestrzenie."""
    settings.ALLOWED_HOSTS = ["*"]
    pierwsza = _uczelnia_na_domenie("pierwsza.example.com", "Pierwsza", "PIE")
    druga = _uczelnia_na_domenie("druga.example.com", "Druga", "DRU")
    _rekord_dla_uczelni(pierwsza, "Praca pierwszej uczelni")
    _rekord_dla_uczelni(druga, "Praca drugiej uczelni")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={"verb": "ListRecords", "metadataPrefix": "oai_dc"},
        HTTP_HOST="pierwsza.example.com",
    )
    tresc = res.content.decode()

    assert "oai:pierwsza.example.com:" in tresc
    assert "oai:druga.example.com:" not in tresc


@pytest.mark.django_db
def test_oai_list_records_bez_uczelni_uzywa_hosta_requestu(client, oai_url, settings):
    """Gdy uczelni nie da się ustalić, namespace bierze się z hosta requestu.

    ``scope_rekord_do_uczelni(qs, None)`` jest wtedy no-opem, więc rekordy
    nadal są wydawane i muszą mieć sensowny identyfikator.
    """
    settings.ALLOWED_HOSTS = ["*"]
    aut, _ = Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
    praca = any_ciagle(
        tytul_oryginalny="Praca bez uczelni",
        charakter_formalny=_charakter_widoczny_w_oai(),
    )
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=praca,
        autor=any_autor(),
        jednostka=any_jednostka(),
        typ_odpowiedzialnosci=aut,
    )
    Uczelnia.objects.all().delete()
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={"verb": "ListRecords", "metadataPrefix": "oai_dc"},
        HTTP_HOST="samotny.example.com",
    )

    assert res.status_code == 200
    assert "oai:samotny.example.com:" in res.content.decode()


# --- GetRecord ------------------------------------------------------------


@pytest.mark.django_db
def test_oai_get_record_wlasny_namespace_zwraca_rekord(client, oai_url, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = _uczelnia_na_domenie("bpp.przyklad.edu.pl", "Przykładowa", "PRZ")
    praca = _rekord_dla_uczelni(uczelnia, "Publikacja szukana")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={
            "verb": "GetRecord",
            "metadataPrefix": "oai_dc",
            "identifier": f"oai:bpp.przyklad.edu.pl:Wydawnictwo_Ciagle/{praca.pk}",
        },
        HTTP_HOST="bpp.przyklad.edu.pl",
    )

    assert res.status_code == 200
    assert "Publikacja szukana" in res.content.decode()


@pytest.mark.django_db
def test_oai_get_record_obcy_namespace_to_blad_protokolu(client, oai_url, settings):
    """Identyfikator spoza tego repozytorium → ``idDoesNotExist``."""
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = _uczelnia_na_domenie("bpp.przyklad.edu.pl", "Przykładowa", "PRZ")
    praca = _rekord_dla_uczelni(uczelnia, "Publikacja szukana")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={
            "verb": "GetRecord",
            "metadataPrefix": "oai_dc",
            "identifier": (
                f"oai:{OBCY_IDENTYFIKATOR_REPOZYTORIUM}:Wydawnictwo_Ciagle/{praca.pk}"
            ),
        },
        HTTP_HOST="bpp.przyklad.edu.pl",
    )

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "idDoesNotExist" in tresc
    assert "Publikacja szukana" not in tresc


@pytest.mark.django_db
@pytest.mark.parametrize(
    "identyfikator",
    [
        "smiec",
        "oai:bpp.przyklad.edu.pl",
        "oai:bpp.przyklad.edu.pl:BezUkosnika",
        "oai:bpp.przyklad.edu.pl:NieMaTakiegoModelu/1",
        "oai:bpp.przyklad.edu.pl:Wydawnictwo_Ciagle/nie-liczba",
    ],
)
def test_oai_get_record_zepsuty_identyfikator_nie_wybucha(
    client, oai_url, settings, identyfikator
):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = _uczelnia_na_domenie("bpp.przyklad.edu.pl", "Przykładowa", "PRZ")
    _rekord_dla_uczelni(uczelnia, "Publikacja szukana")
    Rekord.objects.full_refresh()

    res = client.get(
        oai_url,
        data={
            "verb": "GetRecord",
            "metadataPrefix": "oai_dc",
            "identifier": identyfikator,
        },
        HTTP_HOST="bpp.przyklad.edu.pl",
    )

    assert res.status_code == 200
    assert "idDoesNotExist" in res.content.decode()
