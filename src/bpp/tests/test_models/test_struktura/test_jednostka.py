# -*- encoding: utf-8 -*-
from datetime import date

import pytest
from model_mommy import mommy

from bpp.models import Uczelnia
from bpp.models.struktura import Jednostka, Wydzial, Jednostka_Wydzial


@pytest.mark.django_db
def test_jednostka_test_wydzial_dnia_pusty():
    j = mommy.make(Jednostka, nazwa="Jednostka")
    w = mommy.make(Wydzial, nazwa="Wydzial", uczelnia=j.uczelnia)

    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=w)

    assert j.wydzial_dnia(date(1, 1, 1)) == w
    assert j.wydzial_dnia(date(2030, 1, 1)) == w
    assert j.wydzial_dnia(date(9999, 12, 31)) == w


@pytest.mark.django_db
def test_jednostka_test_wydzial_dnia():
    j = mommy.make(Jednostka)
    w = mommy.make(Wydzial, uczelnia=j.uczelnia)

    Jednostka_Wydzial.objects.create(
        jednostka=j, wydzial=w, od=date(2015, 1, 1), do=date(2015, 2, 1)
    )

    assert j.wydzial_dnia(date(1, 1, 1)) == None
    assert j.wydzial_dnia(date(2015, 1, 1)) == w
    assert j.wydzial_dnia(date(2015, 1, 2)) == w
    assert j.wydzial_dnia(date(2015, 2, 1)) == w
    assert j.wydzial_dnia(date(2015, 2, 2)) == None


@pytest.mark.django_db
def test_jednostka_test_przypisania_dla_czasokresu():
    j = mommy.make(Jednostka)
    w = mommy.make(Wydzial, uczelnia=j.uczelnia)
    Jednostka_Wydzial.objects.create(
        jednostka=j, wydzial=w, od=date(2015, 1, 1), do=date(2015, 2, 1)
    )

    ret = j.przypisania_dla_czasokresu(date(2015, 2, 1), date(2015, 2, 20))
    assert ret.count() == 1

    ret = j.przypisania_dla_czasokresu(date(2015, 2, 2), date(2015, 2, 20))
    assert ret.count() == 0

    ret = j.przypisania_dla_czasokresu(date(2014, 12, 1), date(2014, 12, 31))
    assert ret.count() == 0

    ret = j.przypisania_dla_czasokresu(date(2014, 12, 1), date(2015, 1, 1))
    assert ret.count() == 1


@pytest.mark.django_db
def test_jednostka_get_default_ordering():
    assert Jednostka.objects.get_default_ordering() == ("nazwa",)

    uczelnia = mommy.make(Uczelnia, sortuj_jednostki_alfabetycznie=True)

    assert Jednostka.objects.get_default_ordering() == ("nazwa",)

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()

    assert Jednostka.objects.get_default_ordering() == ("kolejnosc", "nazwa",)
