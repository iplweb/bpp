"""System data fixtures: typy_odpowiedzialnosci, jezyki, charaktery_formalne, etc."""

import json
import os
import random

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from bpp import const
from bpp.fixtures import get_openaccess_data
from bpp.models import Zewnetrzna_Baza_Danych
from bpp.models.autor import Funkcja_Autora, Tytul
from bpp.models.system import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
)
from bpp.util import get_fixture


def fixture(name):
    return json.load(
        open(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../bpp", "fixtures", name)
            ),
            "rb",
        )
    )


@pytest.fixture(scope="function")
def typ_odpowiedzialnosci_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=const.TO_AUTOR
    )[0]


@pytest.fixture(scope="function")
def typ_odpowiedzialnosci_redaktor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="red.", nazwa="redaktor", typ_ogolny=const.TO_REDAKTOR
    )[0]


@pytest.fixture(scope="function")
def typy_odpowiedzialnosci(db):
    for elem in fixture("typ_odpowiedzialnosci_v2.json"):
        Typ_Odpowiedzialnosci.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return {x.skrot: x for x in Typ_Odpowiedzialnosci.objects.all()}


@pytest.fixture(scope="function")
def tytuly():
    for elem in fixture("tytul.json"):
        Tytul.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def jezyki():
    pl, created = Jezyk.objects.get_or_create(pk=1, skrot="pol.", nazwa="polski")
    pl.skrot_dla_pbn = "PL"
    pl.save()
    assert pl.pk == 1

    ang, created = Jezyk.objects.get_or_create(
        pk=2,
        skrot="ang.",
        nazwa="angielski",
    )
    ang.skrot_dla_pbn = "EN"
    ang.skrot_crossref = "en"
    ang.save()
    assert ang.pk == 2

    for elem in fixture("jezyk.json"):
        Jezyk.objects.get_or_create(**elem["fields"])

    return {jezyk.skrot: jezyk for jezyk in Jezyk.objects.all()}


@pytest.fixture(scope="function")
def charaktery_formalne():
    Charakter_Formalny.objects.all().delete()
    for elem in fixture("charakter_formalny.json"):
        Charakter_Formalny.objects.get_or_create(pk=elem["pk"], **elem["fields"])

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_ksp.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_KSIAZKA
    chf_ksp.charakter_sloty = const.CHARAKTER_SLOTY_KSIAZKA
    chf_ksp.nazwa_w_primo = "Książka"
    chf_ksp.save()

    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")
    chf_roz.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_ROZDZIAL
    chf_roz.charakter_sloty = const.CHARAKTER_SLOTY_ROZDZIAL
    chf_roz.save()

    return {x.skrot: x for x in Charakter_Formalny.objects.all()}


@pytest.fixture(scope="function")
def ksiazka_polska(charaktery_formalne):
    return charaktery_formalne["KSP"]


@pytest.fixture(scope="function")
def charakter_formalny_rozdzial(charaktery_formalne):
    return charaktery_formalne["ROZ"]


@pytest.fixture(scope="function")
def artykul_w_czasopismie(charaktery_formalne):
    return charaktery_formalne["AC"]


@pytest.fixture(scope="function")
def typy_kbn():
    for elem in fixture("typ_kbn.json"):
        Typ_KBN.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def statusy_korekt():
    for elem in fixture("status_korekty.json"):
        Status_Korekty.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return {status.nazwa: status for status in Status_Korekty.objects.all()}


@pytest.fixture(scope="function")
def przed_korekta(statusy_korekt):
    return statusy_korekt["przed korektą"]


@pytest.fixture(scope="function")
def po_korekcie(statusy_korekt):
    return statusy_korekt["po korekcie"]


@pytest.fixture(scope="function")
def w_trakcie_korekty(statusy_korekt):
    return statusy_korekt["w trakcie korekty"]


@pytest.fixture(scope="function")
def funkcje_autorow():
    for elem in get_fixture("funkcja_autora").values():
        Funkcja_Autora.objects.get_or_create(**elem)


@pytest.fixture(scope="function")
def standard_data(
    typy_odpowiedzialnosci,
    tytuly,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    funkcje_autorow,
):
    class StandardData:
        @classmethod
        def clean(self):
            for model in (
                Typ_Odpowiedzialnosci,
                Tytul,
                Jezyk,
                Charakter_Formalny,
                Typ_KBN,
                Status_Korekty,
                Funkcja_Autora,
            ):
                model.objects.all().delete()

    return StandardData


@pytest.mark.django_db
@pytest.fixture(scope="function")
def openaccess_data():
    from django.contrib.contenttypes.models import ContentType

    for model_name, skrot, nazwa in get_openaccess_data():
        klass = ContentType.objects.get_by_natural_key("bpp", model_name).model_class()
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


@pytest.fixture
def denorms():
    from denorm import denorms

    yield denorms


@pytest.fixture
def api_client(client):
    return APIClient()


@pytest.fixture
def baza_wos():
    return Zewnetrzna_Baza_Danych.objects.get_or_create(
        nazwa="Web of Science", skrot="WOS"
    )[0]


def gen_kod_dyscypliny_func():
    top = random.randint(1, 8)
    bottom = random.randint(1, 500)
    return f"{top}.{bottom}"


baker.generators.add(
    "bpp.models.dyscyplina_naukowa.KodDyscyplinyField", gen_kod_dyscypliny_func
)
