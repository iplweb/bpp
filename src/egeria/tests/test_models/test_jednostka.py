# -*- encoding: utf-8 -*-
from datetime import date

import pytest
from model_mommy import mommy

from bpp.models.autor import Autor_Jednostka
from bpp.models.struktura import Jednostka, Jednostka_Wydzial, Wydzial, Uczelnia
from egeria.models import Diff_Jednostka_Create, Diff_Jednostka_Update, Diff_Jednostka_Delete
from egeria.models.core import EgeriaImport


@pytest.mark.django_db
def test_Diff_Jednostka_Create_commit(wydzial, egeria_import):
    assert Jednostka.objects.all().count() == 0
    d = Diff_Jednostka_Create.objects.create(
        parent=egeria_import,
        nazwa="Test Jednostki",
        wydzial=wydzial
    )
    d.commit()

    assert Jednostka.objects.all().count() == 1
    j = Jednostka.objects.all()[0]
    assert j.nazwa == "Test Jednostki"
    assert j.skrot == "TJ"

    assert Jednostka_Wydzial.objects.filter(jednostka_id=j.pk).count() == 1


@pytest.mark.django_db
def test_Diff_Jednostka_Update_check_if_needed(jednostka, wydzial, drugi_wydzial):
    # wariant 1: jednostka widoczna, ten sam wydział, aktualizacja NIE WYMAGANA
    jednostka.widoczna = True
    jednostka.wchodzi_do_raportow = True
    jednostka.wydzial = None
    jednostka.save()

    jw = Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)

    class FakeParent:
        od = date.today()
        do = None

    ret = Diff_Jednostka_Update.check_if_needed(
        parent=FakeParent,
        elem=dict(reference=jednostka, wydzial=wydzial))
    assert ret == False

    # wariant 2: jednostka widoczna, ale w pliku jest nowy (inny) wydział, aktualizacja WYMAGANA\
    ret = Diff_Jednostka_Update.check_if_needed(
        parent=FakeParent,
        elem=dict(reference=jednostka, wydzial=drugi_wydzial))
    assert ret == True

    # wariant 3: jednostka niewidoczna, ten sam wydział, aktualizacja WYMAGANA
    jednostka.widoczna = False
    ret = Diff_Jednostka_Update.check_if_needed(
        parent=FakeParent,
        elem=dict(reference=jednostka, wydzial=wydzial))
    assert ret == True


@pytest.mark.django_db
def test_Diff_Jednostka_Update_check_if_needed_dwa_zakresy_czasowe(jednostka, wydzial, drugi_wydzial):
    """
    wariant 4: jednostka widoczna, aktualizacja z pliku "obowiązującego" przez rok,
    w trakcie tego roku jednostka jest przypisana do DWÓCH wydziałów, z czego jeden z nich
    jest taki sam jak w pliku importu. Domyślnie, system ma coś takiego nadpisać, stąd też
    check_if_needed ma zwrócić True
    """

    class FakeParent:
        od = date(2013, 1, 1)
        do = date(2013, 12, 31)

    Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial, od=None, do=date(2013, 6, 1))
    Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=drugi_wydzial, od=date(2013, 6, 2), do=None)

    r = Diff_Jednostka_Update.check_if_needed(
        parent=FakeParent,
        elem=dict(reference=jednostka, wydzial=drugi_wydzial)
    )
    assert r == True


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_widocznosc(jednostka, wydzial, drugi_wydzial, egeria_import):
    jednostka.widoczna = jednostka.wchodzi_do_raportow = False
    jednostka.save()

    dju = Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=wydzial
    )

    dju.commit()
    jednostka.refresh_from_db()
    assert jednostka.wydzial == wydzial
    assert jednostka.widoczna == True


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_widocznosc_wydzial(jednostka, wydzial, drugi_wydzial, egeria_import):
    jednostka.widoczna = jednostka.wchodzi_do_raportow = False
    jednostka.save()

    dju = Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial
    )

    dju.commit()
    jednostka.refresh_from_db()
    assert jednostka.wydzial == drugi_wydzial
    assert jednostka.widoczna == True


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_czasu_w_przeszlosci():
    ei = mommy.make(EgeriaImport, od=date(2013, 1, 1), do=date(2013, 12, 31))

    u = mommy.make(Uczelnia)
    j = mommy.make(Jednostka, uczelnia=u)
    w1 = mommy.make(Wydzial, uczelnia=u)
    w2 = mommy.make(Wydzial, uczelnia=u)
    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=w1)

    j.refresh_from_db()
    assert j.wydzial == w1

    # Koniec inicjalizacji

    Diff_Jednostka_Update.objects.create(
        parent=ei,
        reference=j,
        wydzial=w2
    ).commit()

    j.refresh_from_db()
    assert j.wydzial == w1
    assert j.wydzial_dnia(date(2012, 1, 3)) == w1
    assert j.wydzial_dnia(date(2012, 12, 31)) == w1
    assert j.wydzial_dnia(date(2013, 1, 3)) == w2
    assert j.wydzial_dnia(date(2014, 1, 3)) == w1


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_typowa_sytuacja_w_obecnej_bpp(jednostka, wydzial, drugi_wydzial,
                                                                           egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.save()
    Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)

    Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial
    ).commit()

    jednostka.refresh_from_db()
    assert jednostka.wydzial == drugi_wydzial

    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 2)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == drugi_wydzial


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_case_1(jednostka, wydzial, drugi_wydzial, egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.do = date(2012, 12, 31)
    egeria_import.save()

    Jednostka_Wydzial.objects.create(
        jednostka=jednostka, wydzial=wydzial,
        od=date(2011, 1, 1), do=date(2012, 6, 1))

    Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial).commit()

    jednostka.refresh_from_db()
    assert jednostka.wydzial == drugi_wydzial
    assert jednostka.aktualna == False
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 2)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == None


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_case_2(jednostka, wydzial, drugi_wydzial, egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.do = date(2012, 12, 31)
    egeria_import.save()

    Jednostka_Wydzial.objects.create(
        jednostka=jednostka, wydzial=wydzial,
        od=date(2012, 2, 1), do=date(2012, 6, 1))

    Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial).commit()

    jednostka.refresh_from_db()
    assert jednostka.wydzial == drugi_wydzial
    assert jednostka.aktualna == False
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 2)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == None


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_case_3(jednostka, wydzial, drugi_wydzial, egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.do = date(2012, 12, 31)
    egeria_import.save()

    Jednostka_Wydzial.objects.create(
        jednostka=jednostka, wydzial=wydzial,
        od=date(2012, 6, 1), do=date(2013, 6, 1))

    Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial).commit()

    jednostka.refresh_from_db()
    assert jednostka.wydzial == wydzial
    assert jednostka.aktualna == False
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == None
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 2)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial


@pytest.mark.django_db
def test_Diff_Jednostka_Update_commit_zakres_druga_typowa_sytuacja_w_obecnej_bpp(jednostka, wydzial, drugi_wydzial,
                                                                                 egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.do = date(2012, 12, 31)
    egeria_import.save()
    Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)

    Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial
    ).commit()

    jednostka.refresh_from_db()
    assert jednostka.wydzial == wydzial

    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 2)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) == drugi_wydzial
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial


@pytest.mark.django_db
def test_Diff_Jednostka_Delete_check_if_needed(jednostka, egeria_import):
    jednostka.zarzadzaj_automatycznie = jednostka.widoczna = jednostka.wchodzi_do_raportow = True
    jednostka.save()

    wydzial = jednostka.wydzial
    wydzial.zarzadzaj_automatycznie = True
    wydzial.save()

    jw = Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)
    jednostka.refresh_from_db()
    assert jednostka.aktualna

    # Wariant 1: jednostka jest widoczna, aktualna, zarzadzana automatycznie i w wydziale zarzadzanym automatycznie
    assert Diff_Jednostka_Delete.check_if_needed(egeria_import, jednostka) == True

    # jednostka niewidoczna, nie w raportach ale aktualna
    jednostka.widoczna = jednostka.wchodzi_do_raportow = False
    jednostka.save()
    assert Diff_Jednostka_Delete.check_if_needed(egeria_import, jednostka) == True

    # jednostka niewidoczna, nie w raportach, nieaktualna
    jw.delete()
    jednostka.refresh_from_db()
    assert Diff_Jednostka_Delete.check_if_needed(egeria_import, jednostka) == False


@pytest.mark.django_db
def test_Diff_Jednostka_Delete_check_if_needed_nie_zarzadzaj_automatycznie(jednostka, egeria_import):
    jednostka.widoczna = jednostka.wchodzi_do_raportow = True
    jednostka.zarzadzaj_automatycznie = False
    jednostka.save()

    wydzial = jednostka.wydzial
    wydzial.zarzadzaj_automatycznie = True
    wydzial.save()

    jw = Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)
    jednostka.refresh_from_db()
    assert jednostka.aktualna

    assert Diff_Jednostka_Delete.check_if_needed(egeria_import, jednostka) == False

    jednostka.zarzadzaj_automatycznie = True
    jednostka.save()
    wydzial.zarzadzaj_automatycznie = False
    wydzial.save()
    assert Diff_Jednostka_Delete.check_if_needed(egeria_import, jednostka) == False


@pytest.mark.django_db
def test_Diff_Jednostka_Delete_comit_wariant_1(jednostka, wydzial, autor, egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.save()
    jw = Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)

    # Wariant 1: jednostka jest powiązana z innymi rekordami w bazie danych,
    # w rezultacie ma pozostać niewidoczna oraz przesunięta do wydziału archiwalnego
    aj = Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka
    )

    Diff_Jednostka_Delete.objects.create(
        parent=egeria_import,
        reference=jednostka,
    ).commit()

    jednostka.refresh_from_db()
    assert jednostka.wchodzi_do_raportow == False
    assert jednostka.widoczna == False
    assert jednostka.wydzial == wydzial
    assert jednostka.aktualna == False

    jw.refresh_from_db()
    assert jw.do == date(2011, 12, 31)


@pytest.mark.django_db
def test_Diff_Jednostka_Delete_comit_wariant_2(jednostka, wydzial, egeria_import):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.save()
    jw = Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)

    # Wariant 2: jednostka nie jest powiązana z innymi rekordami w bazie danych,
    # ma zostać fizycznie usunięta
    Diff_Jednostka_Delete.objects.create(
        parent=egeria_import,
        reference=jednostka,
    ).commit()

    with pytest.raises(Jednostka.DoesNotExist):
        jednostka.refresh_from_db()

    with pytest.raises(Jednostka_Wydzial.DoesNotExist):
        jw.refresh_from_db()
