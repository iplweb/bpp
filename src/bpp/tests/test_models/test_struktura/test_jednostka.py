from datetime import date

import pytest
from model_bakery import baker

from bpp.models.struktura import Jednostka, Jednostka_Wydzial, Wydzial


@pytest.mark.django_db
def test_jednostka_publiczna(wydzial, uczelnia):
    j = baker.make(Jednostka, widoczna=True, uczelnia=uczelnia, aktualna=True)
    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=wydzial)
    assert Jednostka.objects.publiczne().count() == 1


@pytest.mark.django_db
def test_jednostka_widoczne():
    j = baker.make(Jednostka, widoczna=True, aktualna=True)
    assert Jednostka.objects.widoczne().count() == 1

    j.widoczna = False
    j.save()
    assert Jednostka.objects.widoczne().count() == 0


@pytest.mark.django_db
def test_jednostka_test_wydzial_dnia_pusty():
    j = baker.make(Jednostka, nazwa="Jednostka")
    w = baker.make(Wydzial, nazwa="Wydzial", uczelnia=j.uczelnia)

    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=w)

    assert j.wydzial_dnia(date(1, 1, 1)) == w
    assert j.wydzial_dnia(date(2030, 1, 1)) == w
    assert j.wydzial_dnia(date(9999, 12, 31)) == w


@pytest.mark.django_db
def test_jednostka_test_wydzial_dnia():
    j = baker.make(Jednostka)
    w = baker.make(Wydzial, uczelnia=j.uczelnia)

    Jednostka_Wydzial.objects.create(
        jednostka=j, wydzial=w, od=date(2015, 1, 1), do=date(2015, 2, 1)
    )

    assert j.wydzial_dnia(date(1, 1, 1)) is None
    assert j.wydzial_dnia(date(2015, 1, 1)) == w
    assert j.wydzial_dnia(date(2015, 1, 2)) == w
    assert j.wydzial_dnia(date(2015, 2, 1)) == w
    assert j.wydzial_dnia(date(2015, 2, 2)) is None


@pytest.mark.django_db
def test_jednostka_test_przypisania_dla_czasokresu():
    j = baker.make(Jednostka)
    w = baker.make(Wydzial, uczelnia=j.uczelnia)
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
def test_jednostka_get_default_ordering(uczelnia):

    assert Jednostka.objects.get_default_ordering() == ("nazwa",)

    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    assert Jednostka.objects.get_default_ordering() == ("nazwa",)

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()

    assert Jednostka.objects.get_default_ordering() == (
        "kolejnosc",
        "nazwa",
    )
