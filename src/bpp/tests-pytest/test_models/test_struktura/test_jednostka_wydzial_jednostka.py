# -*- encoding: utf-8 -*-
from datetime import datetime, timedelta, date

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import InternalError, IntegrityError
from model_mommy import mommy

from bpp.models.struktura import Wydzial, Jednostka, Jednostka_Wydzial, Uczelnia


@pytest.mark.django_db
def test_jednostka_wydzial_aktualna():
    """Sprawdź, czy dodanie obiektów Jednostka_Wydzial spowoduje zmodyfikowanie
    atrybutów "aktualna" oraz "wydzial_id" na obiekcie Jednostka"""

    u = mommy.make(Uczelnia)
    w = mommy.make(Wydzial, uczelnia=u)
    j = mommy.make(Jednostka, uczelnia=u)

    assert j.wydzial == None

    jw = Jednostka_Wydzial.objects.create(
        jednostka=j,
        wydzial=w
    )

    j.refresh_from_db()
    assert j.wydzial == w
    assert j.aktualna == True

    jw.do = datetime.now().date() - timedelta(days=30)
    jw.save()

    j.refresh_from_db()
    assert j.wydzial == w
    assert j.aktualna == False

    jw.delete()
    j.refresh_from_db()
    assert j.wydzial == None
    assert j.aktualna == False


@pytest.mark.django_db(transaction=True)
def test_jednostka_before_insert():
    """Sprawdź, że nie da się przypisać jednostki do wydziału z innej uczelni
    przez edycje tabeli bpp_jednostka"""

    u1 = mommy.make(Uczelnia)
    u2 = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u1)
    w2 = mommy.make(Wydzial, uczelnia=u2)

    with pytest.raises(InternalError):
        j = mommy.make(Jednostka, uczelnia=u2, wydzial=w1)

    j = mommy.make(Jednostka, uczelnia=u2, wydzial=w2)

    for elem in [j, w2, w1, u2, u1]:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_before_insert():
    """Sprawdź, że nie da się przypisać jednostki do wydziału z innej uczelni
    przez edycje tabeli bpp_jednostka_wydzial"""

    u1 = mommy.make(Uczelnia)
    u2 = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u1)
    w2 = mommy.make(Wydzial, uczelnia=u2)

    j1 = mommy.make(Jednostka, uczelnia=u1)
    assert j1.wydzial == None

    jw = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2
    )
    with pytest.raises(InternalError):
        jw.save()

    jw = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1
    )

    for elem in (jw, j1, w2, w1, u2, u1):
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_time_trigger():
    """Sprawdź, czy nie da się przypisać jednej tej samej jednostki do dwóch
    wydziałów w tym samym czasie"""

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)

    w2 = mommy.make(Wydzial, uczelnia=u1)
    j1 = mommy.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
    )

    jw2 = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2,
        od=date(2001, 1, 1)
    )
    with pytest.raises(IntegrityError):
        jw2.save()

    jw2 = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2,
        do=date(2001, 1, 1)
    )
    with pytest.raises(IntegrityError):
        jw2.save()

    for elem in u1, w1, j1, jw1:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_bez_dat_do_w_przyszlosci_constraint():
    """Sprawdź, czy przypisanie daty 'do' w przyszłości da błąd"""
    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u1)
    jw = Jednostka_Wydzial(jednostka=j1, wydzial=w1,
                           od=date.today() - timedelta(days=30),
                           do=date.today())

    with pytest.raises(IntegrityError):
        jw.save()

    for elem in u1, w1, j1:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_time_trigger_delete_1():
    """Sprawdź, czy po zmianie jednostka_id trigger zwróci błąd.
    """

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)

    j1 = mommy.make(Jednostka, uczelnia=u1)
    j2 = mommy.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
    )

    jw1.jednostka = j2

    with pytest.raises(InternalError):
        jw1.save()

    for elem in u1, w1, j1, j2, jw1:
        elem.delete()


@pytest.mark.django_db
def test_jednostka_wydzial_time_trigger_delete_2():
    """Sprawdź, czy po dodaniu wartości do tabeli bpp_jednostka_wydzial
    możliwe będzie usunięcie tychże (że nie wywali wówczas triggera)"""

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    j1 = mommy.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
    )

    jw1.delete()

    j1.refresh_from_db()

    assert j1.wydzial == None
    assert j1.aktualna == False

    for elem in u1, w1, j1:
        elem.delete()


@pytest.mark.django_db
def test_jednostka_wydzial_save_trigger_zakres_dat():
    """Sprawdź, walidacja obiektu Jednostka_Wydzial zwróci prawidłowy błąd dla dwóch zachodzących na siebie
    zakresów dat przy przypisaniu. """

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    w2 = mommy.make(Wydzial, uczelnia=u1)

    j1 = mommy.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
        od=date(2000, 1, 1),
        do=date(2000, 2, 1))

    jw2 = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2,
        od=date(2000, 1, 15),
        do=date(2000, 2, 20))

    with pytest.raises(ValidationError):
        jw2.clean()

    jw2 = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2,
        od=date(2001, 1, 15),
        do=None)

    # ValidationError nie został podniesiony
    jw2.clean()


@pytest.mark.django_db
def test_jednostka_wydzial_save_trigger_zmiana_jednostka_id():
    """Sprawdź, czy walidacja obiektu Jednostka_Wydzial zwróci prawidłowy błąd przy próbie zmiany jednostka_id,
    któro to z kolei nie jest obsługiwane przez triggery bazodanowe. """

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    w2 = mommy.make(Wydzial, uczelnia=u1)

    j1 = mommy.make(Jednostka, uczelnia=u1)
    j2 = mommy.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
        od=date(2000, 1, 1),
        do=date(2000, 2, 1))

    jw1.jednostka = j2

    with pytest.raises(ValidationError):
        jw1.clean()


@pytest.mark.django_db
def test_jednostka_save_trigger_rozne_uczelnie():
    """Sprawdź, czy nie da się przypisać jednej tej samej jednostki do dwóch
    różnych uczelni """

    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)

    u2 = mommy.make(Uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=u2)

    j1 = mommy.make(Jednostka, uczelnia=u1)

    jw = Jednostka_Wydzial(
        jednostka=j1,
        wydzial=w2)

    with pytest.raises(ValidationError):
        jw.clean()


@pytest.mark.django_db
def test_jednostka_save_trigger_data_w_przyszlosci():
    """Sprawdź, czy podanie daty "do" w przyszłości nie przejdzie"""
    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u1)
    jw = Jednostka_Wydzial(jednostka=j1, wydzial=w1,
                           od=date.today() - timedelta(days=30),
                           do=date.today())

    with pytest.raises(ValidationError):
        jw.clean()


@pytest.mark.django_db
def test_jednostka_save_trigger_dwa_zakresy_bug():
    u1 = mommy.make(Uczelnia)
    w1 = mommy.make(Wydzial, uczelnia=u1)
    w2 = mommy.make(Wydzial, uczelnia=u1)
    j1 = mommy.make(Jednostka, uczelnia=u1)

    Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
        od=None,
        do=datetime(2013, 1, 1)
    )

    jw = Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w2,
        od=datetime(2013, 1, 2),
        do=None
    )

    # Jednostka ma mieć ustalony wydział nr 2
    j1.refresh_from_db()
    assert j1.wydzial == w2

    jw.do = datetime(2013, 1, 3)
    jw.save()

    Jednostka_Wydzial.objects.create(
        jednostka=j1,
        wydzial=w1,
        od=datetime(2013, 1, 4),
        do=None
    )

    # Jednostka ma mieć ustalony wydział nr 1
    j1.refresh_from_db()
    assert j1.wydzial == w1

@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_1(wydzial, jednostka):
    Jednostka_Wydzial.objects.create(wydzial=wydzial, jednostka=jednostka, od=None, do=date(2012, 6, 1))
    Jednostka_Wydzial.objects.wyczysc_przypisania(jednostka, date(2012, 1, 1), date(2012, 12, 31))
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == None


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_2(wydzial, jednostka):
    Jednostka_Wydzial.objects.create(wydzial=wydzial, jednostka=jednostka)
    Jednostka_Wydzial.objects.wyczysc_przypisania(jednostka, date(2012, 1, 1), date(2012, 12, 31))
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial

@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_3(wydzial, jednostka):
    Jednostka_Wydzial.objects.create(wydzial=wydzial, jednostka=jednostka, od=date(2012, 6, 1), do=None)
    Jednostka_Wydzial.objects.wyczysc_przypisania(jednostka, date(2012, 1, 1), date(2012, 12, 31))
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_corner_case_left(wydzial, jednostka):
    Jednostka_Wydzial.objects.create(wydzial=wydzial, jednostka=jednostka, od=date(2011, 12, 31), do=date(2012, 12, 31))
    Jednostka_Wydzial.objects.wyczysc_przypisania(jednostka, date(2012, 1, 1), date(2012, 12, 31))
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == None
