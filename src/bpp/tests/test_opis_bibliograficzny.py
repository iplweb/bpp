import os

import pytest
from dbtemplates.models import Template
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

import bpp
from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)
from pbn_api.models import Publication


def _sync_opis_template_z_dysku():
    """Wymuś, by dbtemplate ``opis_bibliograficzny.html`` w bazie testowej miał
    aktualną treść z dysku.

    Baza testowa ładuje baseline, w którym wiersz dbtemplate bywa starszy niż
    plik na dysku (to dokładnie problem #329 — loader dbtemplates zasłania
    dysk). Aby przetestować *logikę* szablonu niezależnie od mechanizmu
    dystrybucji, synchronizujemy wiersz z dyskiem."""
    sciezka = os.path.join(
        os.path.dirname(bpp.__file__), "templates", "opis_bibliograficzny.html"
    )
    with open(sciezka, encoding="utf-8") as f:
        tresc = f.read()
    Template.objects.update_or_create(
        name="opis_bibliograficzny.html", defaults={"content": tresc}
    )


@pytest.mark.django_db
def test_Template_name_idx():
    Template.objects.create(name="test", content="test")
    with pytest.raises(IntegrityError):
        Template.objects.create(name="test", content="test")


@pytest.mark.django_db
def test_nulltest_idx():
    test_template = Template.objects.create(name="test", content="test")

    if not SzablonDlaOpisuBibliograficznego.objects.filter(model=None).exists():
        # przy ponownym uruchamianiu testow moze byc taka sytuacja
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)

    with pytest.raises(IntegrityError):
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)


@pytest.mark.django_db
def test_rozne_opisy_rozne_klasy(wydawnictwo_ciagle, wydawnictwo_zwarte):
    SzablonDlaOpisuBibliograficznego.objects.all().delete()

    test_template = Template.objects.create(name="test", content="test")
    second_template = Template.objects.create(name="2nd", content="2nd")

    # Szablon dla każdej klasy
    try:
        sz = SzablonDlaOpisuBibliograficznego.objects.get(model=None)
        sz.template = test_template
        sz.save()
    except SzablonDlaOpisuBibliograficznego.DoesNotExist:
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == test_template.content

    # Szablon tylko dla zwartych
    SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Zwarte),
        template=second_template,
    )

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == second_template.content


@pytest.mark.django_db
def test_opis_bibliograficzny_wydawnictwo_nadrzedne(
    wydawnictwo_zwarte,
):
    """Rozdział z wydawnictwo_nadrzedne pokazuje 'W: tytuł'."""
    parent = Wydawnictwo_Zwarte.objects.create(
        tytul_oryginalny="Monografia Testowa",
        charakter_formalny=wydawnictwo_zwarte.charakter_formalny,
        typ_kbn=wydawnictwo_zwarte.typ_kbn,
        jezyk=wydawnictwo_zwarte.jezyk,
        status_korekty=wydawnictwo_zwarte.status_korekty,
        rok=wydawnictwo_zwarte.rok,
    )
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = parent
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    opis = wydawnictwo_zwarte.opis_bibliograficzny()
    assert "W: Monografia Testowa." in opis


@pytest.mark.django_db
def test_opis_bibliograficzny_wydawnictwo_nadrzedne_w_pbn(
    wydawnictwo_zwarte,
):
    """Rozdział z wydawnictwo_nadrzedne_w_pbn pokazuje 'W: tytuł'."""
    pbn_pub = Publication.objects.create(
        mongoId="test-pbn-parent-id",
        title="PBN Monografia Testowa",
    )
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    opis = wydawnictwo_zwarte.opis_bibliograficzny()
    assert "W: PBN Monografia Testowa." in opis


@pytest.mark.django_db
def test_opis_bibliograficzny_wydawnictwo_nadrzedne_z_pbn_object_book(
    wydawnictwo_zwarte,
):
    """Rozdział zaimportowany z PBN: rodzic siedzi w surowym JSON-ie
    publikacji (``object.book.title``), bez ustawionego FK BPP ani kurowanego
    FK PBN. Opis i tak pokazuje 'W: tytuł' (ticket #329)."""
    pbn_pub = Publication.objects.create(
        mongoId="test-pbn-rozdzial-id",
        versions=[
            {
                "current": True,
                "object": {"book": {"title": "Rodzic z surowego PBN"}},
            }
        ],
    )
    wydawnictwo_zwarte.pbn_uid = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    _sync_opis_template_z_dysku()
    opis = wydawnictwo_zwarte.opis_bibliograficzny()
    assert "W: Rodzic z surowego PBN." in opis


@pytest.mark.django_db
def test_opis_bibliograficzny_fk_bpp_wygrywa_nad_pbn_object_book(
    wydawnictwo_zwarte,
):
    """Gdy ustawiony jest FK BPP, ma pierwszeństwo nad ``object.book`` z PBN."""
    parent = Wydawnictwo_Zwarte.objects.create(
        tytul_oryginalny="Rodzic w BPP",
        charakter_formalny=wydawnictwo_zwarte.charakter_formalny,
        typ_kbn=wydawnictwo_zwarte.typ_kbn,
        jezyk=wydawnictwo_zwarte.jezyk,
        status_korekty=wydawnictwo_zwarte.status_korekty,
        rok=wydawnictwo_zwarte.rok,
    )
    pbn_pub = Publication.objects.create(
        mongoId="test-pbn-rozdzial-id-2",
        versions=[{"current": True, "object": {"book": {"title": "Rodzic z PBN"}}}],
    )
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = parent
    wydawnictwo_zwarte.pbn_uid = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    opis = wydawnictwo_zwarte.opis_bibliograficzny()
    assert "W: Rodzic w BPP." in opis
    assert "Rodzic z PBN" not in opis


@pytest.mark.django_db
def test_opis_bibliograficzny_bez_wydawnictwa_nadrzednego(
    wydawnictwo_zwarte,
):
    """Bez wydawnictwa nadrzędnego nie wyświetla 'W:'."""
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    opis = wydawnictwo_zwarte.opis_bibliograficzny()
    assert "W:" not in opis
