"""Liczniki na ``ImportPracownikow`` (T2.1) — dane kafelków huba."""

import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    STATUS_ZGADYWANIE,
)


def _imp(owner):
    return baker.make(ImportPracownikow, owner=owner)


def _row(imp, confidence):
    return baker.make(
        ImportPracownikowRow,
        parent=imp,
        confidence=confidence,
        zmiany_potrzebne=False,
    )


@pytest.mark.django_db
def test_liczniki_ludzi_koalescencja_none_do_brak(admin_user):
    imp = _imp(admin_user)
    _row(imp, STATUS_TWARDY)
    _row(imp, STATUS_TWARDY)
    _row(imp, STATUS_ZGADYWANIE)
    _row(imp, STATUS_WIELU)
    _row(imp, STATUS_BRAK)
    _row(imp, None)  # stary wiersz z NULL — koalescencja → brak

    liczniki = imp.liczniki_ludzi_z_xls()
    assert liczniki == {"twardy": 2, "zgadywanie": 1, "wielu": 1, "brak": 2}
    # suma == liczba wierszy (dowód, że NULL nie „gubi się")
    assert sum(liczniki.values()) == imp.importpracownikowrow_set.count()


@pytest.mark.django_db
def test_liczniki_ludzi_puste(admin_user):
    imp = _imp(admin_user)
    assert imp.liczniki_ludzi_z_xls() == {
        "twardy": 0,
        "zgadywanie": 0,
        "wielu": 0,
        "brak": 0,
    }


@pytest.mark.django_db
def test_liczniki_jednostek_split_i_pomija_rozstrzygniete(admin_user):
    imp = _imp(admin_user)
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="A",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="B",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=None,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="C",
        tryb=ImportPracownikowJednostka.TRYB_ZGADYWANIE,
        utworzona=None,
    )
    # rozstrzygnięta (utworzona ustawiona) — NIE liczy się
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="D",
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        utworzona=baker.make("bpp.Jednostka"),
    )
    assert imp.liczniki_jednostek() == {"do_utworzenia": 2, "do_sprawdzenia": 1}


@pytest.mark.django_db
def test_liczniki_tytulow_split_i_pomija_rozstrzygniete(admin_user):
    imp = _imp(admin_user)
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="a",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
        utworzony=None,
    )
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="b",
        tryb=ImportPracownikowTytul.TRYB_ZGADYWANIE,
        utworzony=None,
    )
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="c",
        tryb=ImportPracownikowTytul.TRYB_ZGADYWANIE,
        utworzony=None,
    )
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="d",
        tryb=ImportPracownikowTytul.TRYB_ZGADYWANIE,
        utworzony=baker.make("bpp.Tytul"),
    )
    assert imp.liczniki_tytulow() == {"do_utworzenia": 1, "do_sprawdzenia": 2}


@pytest.mark.django_db
def test_liczniki_decyzji_puste(admin_user):
    imp = _imp(admin_user)
    assert imp.liczniki_jednostek() == {"do_utworzenia": 0, "do_sprawdzenia": 0}
    assert imp.liczniki_tytulow() == {"do_utworzenia": 0, "do_sprawdzenia": 0}
