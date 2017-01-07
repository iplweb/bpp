# -*- encoding: utf-8 -*-
from datetime import date

import pytest

from bpp.models.struktura import Wydzial
from egeria.models import zrob_skrot
from egeria.models.util import date_range_inside


@pytest.mark.django_db
def test_zrob_skrot(uczelnia):
    assert zrob_skrot("to jest test skrotowania do dlugosci maksymalnej", 7, Wydzial, "skrot") == "TJTSDDM"

    assert zrob_skrot("to tak", 3, Wydzial, "skrot") == "TT"

    Wydzial.objects.create(nazwa="taki istnieje", uczelnia=uczelnia, skrot="TT")
    assert zrob_skrot("to tak", 3, Wydzial, "skrot") == "TT1"

    assert zrob_skrot("to tak", 2, Wydzial, "skrot") == "T1"

    Wydzial.objects.create(nazwa="taki istnieje 2", uczelnia=uczelnia, skrot="T1")
    assert zrob_skrot("to tak", 2, Wydzial, "skrot") == "T2"

def test_date_range_inside():
    s1 = date(2010, 1, 1)
    e1 = date(2010, 1, 31)

    assert True == date_range_inside(
        None, None,
        s1, e1)

    assert True == date_range_inside(
        None, None,
        None, None)

    assert True == date_range_inside(
        s1, e1,
        s1, e1)

    assert True == date_range_inside(
        s1, e1,
        date(2010, 1, 1),
        date(2010, 1, 1)
    )

    assert True == date_range_inside(
        s1, e1,
        date(2010, 1, 31),
        date(2010, 1, 31)
    )

    assert True == date_range_inside(
        s1, e1,
        date(2010, 1, 10),
        date(2010, 1, 10)
    )

    assert True == date_range_inside(
        s1, e1,
        date(2010, 1, 10),
        date(2010, 1, 15)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 12, 1),
        date(2009, 12, 31)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2010, 1, 15),
        date(2010, 2, 1)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2010, 2, 1),
        date(2010, 2, 1)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2010, 2, 2),
        date(2010, 2, 10)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 12, 31),
        date(2010, 2, 1)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 12, 31),
        date(2010, 1, 15)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 12, 1),
        date(2010, 1, 15)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 1, 15),
        date(2010, 2, 1)
    )

    assert False == date_range_inside(
        s1, e1,
        date(2009, 1, 15),
        date(2010, 2, 10)
    )