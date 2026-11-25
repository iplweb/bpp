"""FD#513: rekord, który ma UKRYTĄ pozycję słownika (język, typ MNiSW,
charakter formalny), musi dać się otworzyć i zapisać w adminie — pełnym
POST-em formularza, razem z walidacją modelu."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Typ_KBN,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Ciagle_Tytul,
)


def _bledy(res):
    ret = []
    for e in res.html.select(".errorlist, .errornote"):
        label = e.find_previous("label")
        ret.append((label.get_text() if label else "", e.get_text(" ")))
    return ret


def _formularz(admin_app, obj):
    nazwa = obj._meta.model_name
    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    return page.forms[f"{nazwa}_form"]


def _opcje(form, pole):
    return {wartosc for wartosc, _wybrana, _etykieta in form[pole].options}


@pytest.fixture
def ukryty_jezyk(db):
    return baker.make(Jezyk, nazwa="t-ukryty", skrot="t-uk", widoczny=False)


@pytest.fixture
def inny_ukryty_jezyk(db):
    return baker.make(Jezyk, nazwa="t-ukryty-2", skrot="t-uk2", widoczny=False)


@pytest.fixture
def ukryty_typ(db):
    return baker.make(Typ_KBN, nazwa="t-ukryty", skrot="t-uk", ukryty=True)


def _ukryty_charakter():
    # Po fixturze ``charaktery_formalne`` (ta potrafi przebudować słownik).
    return Charakter_Formalny.objects.create(
        nazwa="t-ukryty", skrot="t-uk", ukryty=True
    )


@pytest.mark.parametrize(
    "fixtura",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "praca_doktorska", "habilitacja"],
)
def test_publikacja_z_ukrytym_jezykiem_i_typem_zapisuje_sie(
    fixtura, request, admin_app, ukryty_jezyk, inny_ukryty_jezyk, ukryty_typ
):
    obj = request.getfixturevalue(fixtura)
    type(obj).objects.filter(pk=obj.pk).update(
        jezyk=ukryty_jezyk, jezyk_alt=ukryty_jezyk, typ_kbn=ukryty_typ
    )

    if fixtura == "praca_doktorska":
        # Fixtura nie ustawia promotora, a formularz go wymaga.
        type(obj).objects.filter(pk=obj.pk).update(promotor=obj.autor)

    form = _formularz(admin_app, obj)
    # Formularz pokazuje dotychczasowe wartości…
    assert form["jezyk"].value == str(ukryty_jezyk.pk)
    assert form["jezyk_alt"].value == str(ukryty_jezyk.pk)
    assert form["typ_kbn"].value == str(ukryty_typ.pk)
    # …ale innej ukrytej pozycji wybrać się nie da — także tam, gdzie pole
    # nie miało dotąd żadnego ograniczenia.
    for pole in ("jezyk", "jezyk_alt", "jezyk_orig"):
        assert str(inny_ukryty_jezyk.pk) not in _opcje(form, pole)
    assert str(ukryty_jezyk.pk) not in _opcje(form, "jezyk_orig")

    form["tytul_oryginalny"].value = "Zmieniony tytuł FD513"
    res = form.submit()
    assert res.status_code == 302, _bledy(res)

    obj.refresh_from_db()
    assert obj.tytul_oryginalny == "Zmieniony tytuł FD513"
    assert obj.jezyk == ukryty_jezyk
    assert obj.jezyk_alt == ukryty_jezyk
    assert obj.typ_kbn == ukryty_typ


@pytest.mark.parametrize("fixtura", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_ukryty_charakter_formalny_tylko_w_rekordzie_ktory_go_ma(
    fixtura, request, admin_app
):
    obj = request.getfixturevalue(fixtura)
    ukryty_charakter = _ukryty_charakter()

    # Rekord z widocznym charakterem: ukrytego nie ma na liście.
    form = _formularz(admin_app, obj)
    assert str(ukryty_charakter.pk) not in _opcje(form, "charakter_formalny")
    assert len(_opcje(form, "charakter_formalny")) > 1

    # Rekord, który już ma ukryty charakter: pokazuje go i zapisuje się.
    type(obj).objects.filter(pk=obj.pk).update(charakter_formalny=ukryty_charakter)
    form = _formularz(admin_app, obj)
    assert form["charakter_formalny"].value == str(ukryty_charakter.pk)
    form["tytul_oryginalny"].value = "Zmieniony tytuł FD513"
    res = form.submit()
    assert res.status_code == 302, _bledy(res)
    obj.refresh_from_db()
    assert obj.charakter_formalny == ukryty_charakter
    assert obj.tytul_oryginalny == "Zmieniony tytuł FD513"


@pytest.mark.parametrize("fixtura", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_nowy_rekord_nie_podpowiada_ukrytych_pozycji(
    fixtura, request, admin_app, ukryty_jezyk, ukryty_typ
):
    request.getfixturevalue(fixtura)  # słowniki
    ukryty_charakter = _ukryty_charakter()
    nazwa = fixtura
    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_add"))
    form = page.forms[f"{nazwa}_form"]
    for pole in ("jezyk", "jezyk_alt", "jezyk_orig"):
        assert str(ukryty_jezyk.pk) not in _opcje(form, pole)
        assert len(_opcje(form, pole)) > 1
    assert str(ukryty_typ.pk) not in _opcje(form, "typ_kbn")
    assert str(ukryty_charakter.pk) not in _opcje(form, "charakter_formalny")


def test_streszczenie_i_tytul_z_ukrytym_jezykiem_zapisuja_sie(
    admin_app, wydawnictwo_ciagle, ukryty_jezyk, inny_ukryty_jezyk
):
    streszczenie = Wydawnictwo_Ciagle_Streszczenie.objects.create(
        rekord=wydawnictwo_ciagle,
        jezyk_streszczenia=ukryty_jezyk,
        streszczenie="stare streszczenie",
    )
    tytul = Wydawnictwo_Ciagle_Tytul.objects.create(
        rekord=wydawnictwo_ciagle, jezyk=ukryty_jezyk, tytul="stary tytuł"
    )

    form = _formularz(admin_app, wydawnictwo_ciagle)
    pole_s = "streszczenia-0-jezyk_streszczenia"
    pole_t = "dodatkowe_tytuly-0-jezyk"
    assert form[pole_s].value == str(ukryty_jezyk.pk)
    assert form[pole_t].value == str(ukryty_jezyk.pk)
    assert str(inny_ukryty_jezyk.pk) not in _opcje(form, pole_s)
    assert str(inny_ukryty_jezyk.pk) not in _opcje(form, pole_t)

    form["streszczenia-0-streszczenie"].value = "nowe streszczenie"
    form["dodatkowe_tytuly-0-tytul"].value = "nowy tytuł"
    res = form.submit()
    assert res.status_code == 302, _bledy(res)

    streszczenie.refresh_from_db()
    tytul.refresh_from_db()
    assert streszczenie.streszczenie == "nowe streszczenie"
    assert streszczenie.jezyk_streszczenia == ukryty_jezyk
    assert tytul.tytul == "nowy tytuł"
    assert tytul.jezyk == ukryty_jezyk


def test_zrodlo_z_ukrytym_jezykiem_zapisuje_sie(
    admin_app, zrodlo, ukryty_jezyk, inny_ukryty_jezyk
):
    type(zrodlo).objects.filter(pk=zrodlo.pk).update(jezyk=ukryty_jezyk)

    form = _formularz(admin_app, zrodlo)
    assert form["jezyk"].value == str(ukryty_jezyk.pk)
    assert str(inny_ukryty_jezyk.pk) not in _opcje(form, "jezyk")

    form["nazwa"].value = "Źródło FD513"
    res = form.submit()
    assert res.status_code == 302, _bledy(res)
    zrodlo.refresh_from_db()
    assert (zrodlo.nazwa, zrodlo.jezyk) == ("Źródło FD513", ukryty_jezyk)
