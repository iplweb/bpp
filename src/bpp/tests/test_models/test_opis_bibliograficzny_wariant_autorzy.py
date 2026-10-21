"""Wariant opisu ``browse/praca_tabela.html`` — linkowanie autorów.

Test charakteryzujący: spisuje zachowanie pętli autorów DLA KAŻDEGO trybu
``links`` **przed** refaktorem bloku ``<a>`` (rozbity na dwie gałęzie `{% if %}`,
przez co djlint widzi sieroty). Refaktor ma być bezzmianowy semantycznie —
ten test tego pilnuje.

Kontrakt:

* ``links="admin"``  → nazwisko w linku do admina, bez zmiany wielkości liter,
* ``links="normal"`` → nazwisko w linku do strony autora, j.w.,
* ``links`` prawdziwe, ale inne → nazwisko bez linku, bez zmiany wielkości,
* ``links`` fałszywe → nazwisko WERSALIKAMI, bez linku.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


@pytest.fixture
def praca_z_autorem(db):
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    praca = baker.make(Wydawnictwo_Zwarte)
    praca.dodaj_autora(autor, jednostka, zapisany_jako="Kowalski Jan", kolejnosc=0)

    SzablonDlaOpisuBibliograficznego.objects.update_or_create(
        model=None, defaults={"nazwa_szablonu": "browse/praca_tabela.html"}
    )
    return praca, autor


@pytest.mark.django_db
def test_wariant_autorzy_links_admin(praca_z_autorem):
    praca, autor = praca_z_autorem
    opis = praca.opis_bibliograficzny(links="admin")

    assert f"/admin/bpp/autor/{autor.pk}/change/" in opis
    assert "Kowalski Jan" in opis
    assert "KOWALSKI JAN" not in opis


@pytest.mark.django_db
def test_wariant_autorzy_links_normal(praca_z_autorem):
    praca, autor = praca_z_autorem
    opis = praca.opis_bibliograficzny(links="normal")

    assert f"/bpp/autor/{autor.slug}/" in opis
    assert "Kowalski Jan" in opis
    assert "KOWALSKI JAN" not in opis


@pytest.mark.django_db
def test_wariant_autorzy_links_inny_ciag(praca_z_autorem):
    """``links`` prawdziwe, ale nie admin/normal: nazwisko bez linku."""
    praca, autor = praca_z_autorem
    opis = praca.opis_bibliograficzny(links="cokolwiek")

    assert "Kowalski Jan" in opis
    assert "KOWALSKI JAN" not in opis
    assert "<a href" not in opis


@pytest.mark.django_db
def test_wariant_autorzy_bez_links(praca_z_autorem):
    """Brak ``links``: nazwisko WERSALIKAMI, bez linku."""
    praca, autor = praca_z_autorem
    opis = praca.opis_bibliograficzny(links=None)

    assert "KOWALSKI JAN" in opis
    assert "<a href" not in opis
