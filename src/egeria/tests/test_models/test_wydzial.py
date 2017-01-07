# -*- encoding: utf-8 -*-


from datetime import date, timedelta

import pytest

from bpp.models.struktura import Wydzial, Jednostka
from egeria.models import Diff_Wydzial_Delete
from egeria.models.wydzial import Diff_Wydzial_Create


@pytest.mark.django_db
def test_egeria_models_wydzial_check_if_needed(uczelnia):
    class FakeParent:
        od = date.today()
        do = None

    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    w.widoczny = w.zezwalaj_na_ranking_autorow = True
    w.save()
    assert Diff_Wydzial_Delete.check_if_needed(FakeParent, w) == True

    w.widoczny = w.zezwalaj_na_ranking_autorow = False
    w.save()
    # skasowanie tego wydzialu jest potrzebne, mimo, że ukryty
    # bo nie ma żadnych jednostek podlinkowanych, czyli można go wyrzucić.
    assert Diff_Wydzial_Delete.check_if_needed(FakeParent, w) == True

    w.widoczny = w.zezwalaj_na_ranking_autorow = False
    w.save()
    Jednostka.objects.create(wydzial=w, nazwa="foo", skrot="bar")
    # skasowanie tego wydzialu NIE jest potrzebne, ma on podlinkowane
    # jednostki ALE już jest ukryty
    assert Diff_Wydzial_Delete.check_if_needed(FakeParent, w) == False

    w.widoczny = w.zezwalaj_na_ranking_autorow = True
    w.save()
    # skasowanie tego wydzialu jest jest potrzebne, ma on podlinkowane
    # jednostki i nie jest ukryty
    assert Diff_Wydzial_Delete.check_if_needed(FakeParent, w) == True


@pytest.mark.django_db
def test_egeria_models_Diff_Wydzial_Create(egeria_import):
    egeria_import.od = date.today() - timedelta(days=30)
    egeria_import.do = date.today() - timedelta(days=1)
    dwc = Diff_Wydzial_Create.objects.create(
        parent=egeria_import,
        nazwa_skrot="wtf",
    )
    dwc.commit()

    w = Wydzial.objects.get(skrot="W")
    assert w.otwarcie != None
    assert w.otwarcie == egeria_import.od
    assert w.zamkniecie == egeria_import.do


@pytest.mark.django_db
def test_egeria_models_Diff_Wydzial_Delete_wariant_1(uczelnia, egeria_import):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    dwd = Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import)
    dwd.commit()
    # Upewnij się, że wydział bez jednostek znikł z bazy
    with pytest.raises(Wydzial.DoesNotExist):
        w.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_Diff_Wydzial_Delete_wariant_2(uczelnia, egeria_import):

    ten_days_ago = date.today() - timedelta(days=10)
    five_days_ago = date.today() - timedelta(days=5)
    egeria_import.od = ten_days_ago
    egeria_import.do = five_days_ago

    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    j = Jednostka.objects.create(nazwa="nazwa", skrot="skrt", wydzial=w)
    dwd = Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import)
    dwd.commit()
    # Upewnij się, że wydział z jednostką NIE znikł z bazy
    w.refresh_from_db()
    assert w.widoczny == False
    assert w.zamkniecie == ten_days_ago - timedelta(days=1)
