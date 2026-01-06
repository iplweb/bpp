from datetime import date

import pytest
from model_bakery import baker

from bpp.imports.egeria_2012 import (
    dopasuj_autora,
    dopasuj_jednostke,
    importuj_wiersz,
    mangle_labels,
    znajdz_lub_zrob_stanowisko,
)
from bpp.imports.uml import UML_Egeria_2012_Mangle
from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora
from bpp.tests.util import any_jednostka


class _x:
    def __init__(self, value):
        self.value = value


def test_mangle_labels():
    a = [
        "foo",
        "bar",
        "baz",
        "quux",
        "Stanowisko",
        "foo",
        "bar",
        "quux",
        "Stanowisko",
        "Wydzial ",
        "Stanowisko",
        "Wydzial ",
        "Stanowisko",
        "Wydzial",
    ]

    b = [
        "foo",
        "bar",
        "baz",
        "quux",
        "Stanowisko",
        "foo",
        "bar",
        "quux",
        "Stanowisko_2009",
        "Wydzial_2009",
        "Stanowisko_2010",
        "Wydzial_2010",
        "Stanowisko_2011",
        "Wydzial_2011",
    ]

    assert mangle_labels(a) == b


@pytest.mark.django_db
def test_znajdz_lub_zrob_stanowisko():
    f = znajdz_lub_zrob_stanowisko("Kucharz")
    assert f.nazwa == "Kucharz"
    f1 = znajdz_lub_zrob_stanowisko("Kucharz")
    assert f1 == f


@pytest.mark.django_db
def test_dopasuj_jednostke():
    mangle = UML_Egeria_2012_Mangle
    j1 = any_jednostka(nazwa="Foo")
    j2 = any_jednostka(  # noqa
        nazwa="Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz"
    )
    j3 = any_jednostka(
        nazwa="Katedra i Klinika Ginekologii i Endokrynologii Ginekologicznej"
    )
    j4 = any_jednostka(nazwa="I Katedra i Klinika Ginekologii")
    j5 = any_jednostka(nazwa="II Katedra i Klinika Ginekologii")  # noqa

    assert (
        dopasuj_jednostke(
            "Katedra i Klinika Ginekologii i Endokrynologii Ginekolog.", mangle
        )
        == j3
    )

    assert dopasuj_jednostke("Foo", mangle) == j1

    assert (
        dopasuj_jednostke(
            "Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz", mangle
        )
        is None
    )

    assert dopasuj_jednostke("I Katedra i Klinika Ginekologii", mangle) == j4


@pytest.mark.django_db
def test_dopasuj_autora():
    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a3 = baker.make(Autor, imiona="Jan", nazwisko="Unikalny")

    j1 = any_jednostka()
    j2 = any_jednostka()
    f1 = baker.make(Funkcja_Autora, nazwa="Kucharz")

    Autor_Jednostka.objects.create(autor=a1, jednostka=j1, funkcja=f1)

    Autor_Jednostka.objects.create(autor=a2, jednostka=j2, funkcja=f1)

    assert dopasuj_autora("Jan", "Unikalny", None, None) == a3

    assert dopasuj_autora("Jan", "Kowalski", j1.nazwa, f1) == a1

    assert dopasuj_autora("Jan", "Kowalski", j2.nazwa, f1) == a2


@pytest.mark.django_db
def test_importuj_wiersz():
    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    j1 = any_jednostka(nazwa="Foo")

    importuj_wiersz("Jan", "Kowalski", "Foo", "Kucharz", 2012, UML_Egeria_2012_Mangle)
    assert Autor_Jednostka.objects.get(autor=a1, jednostka=j1).zakonczyl_prace == date(
        2012, 12, 31
    )
