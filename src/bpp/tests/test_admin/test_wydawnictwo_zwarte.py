import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.admin.wydawnictwo_zwarte import Wydawnictwo_ZwarteForm
from bpp.models import Wydawca, Wydawnictwo_Zwarte
from bpp.tests import normalize_html
from pbn_api.models import Publication

TEST_PBN_ID = 50000


@pytest.mark.parametrize(
    "fld,value",
    [
        # ("pbn_uid", TEST_PBN_ID),
        ("doi", "10.10/123123"),
        # 13.04.2025 mpasternak duplikaty WWW i public WWW już nie powstaną, system dopisze
        # do nich losowy ciąg znaków...
        # ("www", "https://foobar.pl"),
        # ("public_www", "https://foobar.pl"),
    ],
)
def test_Wydawnictwo_Zwarte_Admin_sprawdz_duplikaty_www_doi(admin_app, fld, value):
    if fld == "pbn_uid":
        value = baker.make(Publication, pk=TEST_PBN_ID)

    baker.make(Wydawnictwo_Zwarte, rok=2020, **{fld: value})
    w2 = baker.make(Wydawnictwo_Zwarte, rok=2020)
    if fld == "pbn_uid":
        value = TEST_PBN_ID  # baker.make(Publication, pk=TEST_PBN_ID)

    url = "admin:bpp_wydawnictwo_zwarte_change"
    page = admin_app.get(reverse(url, args=(w2.pk,)))

    if fld == "pbn_uid":
        page.forms["wydawnictwo_zwarte_form"][fld].force_value(value)
    else:
        page.forms["wydawnictwo_zwarte_form"][fld].value = value
    res = page.forms["wydawnictwo_zwarte_form"].submit().maybe_follow()

    assert "inne rekordy z identycznym polem" in normalize_html(
        res.content.decode("utf-8")
    )


# Freshdesk #385: dziedziczenie wydawcy po wydawnictwie nadrzędnym (rozdziale).


def _form_z_pustym_cleaned_data():
    """Zwraca instancję formularza gotową do testu helpera dziedziczenia.

    Helper ``_dziedzicz_wydawce_po_nadrzednym`` operuje wyłącznie na
    przekazanym ``cleaned_data`` i ``self._warnings`` — nie wymaga
    pełnego zbindowania formularza."""
    form = Wydawnictwo_ZwarteForm()
    form._warnings = []
    return form


@pytest.mark.django_db
def test_dziedziczenie_wydawcy_rozdzial_bez_wlasnego_wydawcy(wydawca):
    """Rozdział bez własnego wydawcy dziedziczy wydawcę po nadrzędnym."""
    nadrzedne = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Monografia", wydawca=wydawca
    )

    form = _form_z_pustym_cleaned_data()
    cleaned_data = {"wydawca": None}
    form._dziedzicz_wydawce_po_nadrzednym(cleaned_data, nadrzedne)

    assert cleaned_data["wydawca"] == wydawca
    assert form._warnings  # operator dostaje informację o dziedziczeniu


@pytest.mark.django_db
def test_dziedziczenie_wydawcy_nie_nadpisuje_jawnie_podanego(wydawca):
    """Jawnie wpisany wydawca NIE jest nadpisywany wydawcą nadrzędnego."""
    inny_wydawca = Wydawca.objects.create(nazwa="Inny Wydawca")
    nadrzedne = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Monografia", wydawca=wydawca
    )

    form = _form_z_pustym_cleaned_data()
    cleaned_data = {"wydawca": inny_wydawca}
    form._dziedzicz_wydawce_po_nadrzednym(cleaned_data, nadrzedne)

    assert cleaned_data["wydawca"] == inny_wydawca
    assert not form._warnings


@pytest.mark.django_db
def test_dziedziczenie_wydawcy_nadrzedne_bez_wydawcy_nic_nie_robi():
    """Gdy nadrzędne nie ma wydawcy — pole pozostaje puste, bez ostrzeżeń."""
    nadrzedne = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Monografia", wydawca=None
    )

    form = _form_z_pustym_cleaned_data()
    cleaned_data = {"wydawca": None}
    form._dziedzicz_wydawce_po_nadrzednym(cleaned_data, nadrzedne)

    assert cleaned_data["wydawca"] is None
    assert not form._warnings


@pytest.mark.django_db
def test_dziedziczenie_wydawcy_brak_nadrzednego_nic_nie_robi(wydawca):
    """Bez wydawnictwa nadrzędnego (nie-rozdział) nic się nie dzieje."""
    form = _form_z_pustym_cleaned_data()
    cleaned_data = {"wydawca": None}
    form._dziedzicz_wydawce_po_nadrzednym(cleaned_data, None)

    assert cleaned_data["wydawca"] is None
    assert not form._warnings
