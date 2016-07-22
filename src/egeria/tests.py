# -*- encoding: utf-8 -*-


import pytest
from django.core.management import call_command

from bpp.models.autor import Tytul, Funkcja_Autora, Autor_Jednostka
from bpp.models.struktura import Uczelnia, Wydzial, Jednostka
from egeria.core import diff_tytuly, diff_funkcje, diff_wydzialy
from egeria.models import EgeriaRow, AlreadyAnalyzedError, Diff_Tytul_Create, Diff_Tytul_Delete, \
    Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete, Diff_Wydzial_Delete, Diff_Wydzial_Create, zrob_skrot, \
    Diff_Jednostka_Create, Diff_Jednostka_Update


@pytest.mark.django_db
def test_egeriaimport_analyze(egeria_import):
    assert EgeriaRow.objects.all().count() == 0

    egeria_import.analyze()

    assert EgeriaRow.objects.all().count() > 10

    with pytest.raises(AlreadyAnalyzedError):
        egeria_import.analyze()


@pytest.mark.django_db
def test_egeria_management_commands_egeria_import(test_file_path):
    with pytest.raises(NotImplementedError):
        call_command('egeria_import', test_file_path)


@pytest.mark.django_db
def test_egeria_core_diff_tytuly_test_commit_all(egeria_import, autor_jan_nowak):
    Tytul.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")

    egeria_import.analyze()
    diff_tytuly(egeria_import)

    for elem in Diff_Tytul_Create.objects.filter(parent=egeria_import):
        elem.commit()

    for elem in Diff_Tytul_Delete.objects.filter(parent=egeria_import):
        elem.commit()


@pytest.mark.django_db
def test_egeria_core_diff_tytuly(egeria_import, autor_jan_nowak):
    assert Diff_Tytul_Create.objects.all().count() == 0
    assert Diff_Tytul_Delete.objects.all().count() == 0

    Tytul.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")
    j = Tytul.objects.create(nazwa="jeden to ma", skrot="j. t. m.")

    autor_jan_nowak.tytul = j
    autor_jan_nowak.save()

    egeria_import.analyze()
    diff_tytuly(egeria_import)

    assert u"nieistniejący tytuł" in Diff_Tytul_Create.objects.all().values_list("nazwa_skrot", flat=True)
    assert u"nikt tego nie ma" not in Diff_Tytul_Create.objects.all().values_list("nazwa_skrot", flat=True)

    assert u"doktor" in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"nikt tego nie ma" in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"jeden to ma" not in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_core_diff_funkcje(egeria_import, autor_jan_nowak, jednostka):
    assert Diff_Funkcja_Autora_Create.objects.all().count() == 0
    assert Diff_Funkcja_Autora_Delete.objects.all().count() == 0

    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")
    j = Funkcja_Autora.objects.create(nazwa="jeden to ma", skrot="j. t. m.")

    Autor_Jednostka.objects.create(autor=autor_jan_nowak, jednostka=jednostka, funkcja=j)

    egeria_import.analyze()
    diff_funkcje(egeria_import)

    assert u"lek. med." in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)
    assert u"nikt tego nie ma" not in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)

    assert u"adiunkt" in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"nikt tego nie ma" in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"jeden to ma" not in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_core_diff_funkcje_test_commit_all(egeria_import, autor_jan_nowak):
    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")

    egeria_import.analyze()
    diff_funkcje(egeria_import)

    for elem in Diff_Funkcja_Autora_Create.objects.filter(parent=egeria_import):
        elem.commit()

    for elem in Diff_Funkcja_Autora_Delete.objects.filter(parent=egeria_import):
        elem.commit()


@pytest.mark.django_db
def test_egeria_core_diff_wydzialy_uczelnia_is_created(egeria_import):
    Uczelnia.objects.all().delete()
    assert Uczelnia.objects.all().count() == 0

    egeria_import.analyze()
    diff_wydzialy(egeria_import)

    Diff_Wydzial_Create.objects.all().first().commit()

    assert Uczelnia.objects.all().count() == 1


@pytest.mark.django_db
def test_egeria_core_diff_wydzialy_kasowanie(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)

    egeria_import.analyze()
    diff_wydzialy(egeria_import)

    assert WYDZIAL['nazwa'] in Diff_Wydzial_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_core_diff_wydzialy_testuj_ukrywanie_wydzialu(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    w = Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)
    assert w.widoczny == True
    assert w.zezwalaj_na_ranking_autorow == True

    Jednostka.objects.create(nazwa="Jednostka", skrot="J", wydzial=w)

    egeria_import.analyze()
    diff_wydzialy(egeria_import)

    for elem in Diff_Wydzial_Delete.objects.all():
        elem.commit()

    w.refresh_from_db()
    assert w.widoczny == False
    assert w.zezwalaj_na_ranking_autorow == False


@pytest.mark.django_db
def test_egeria_core_diff_wydzialy_testuj_kasowanie_wydzialu(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    w = Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)

    egeria_import.analyze()
    diff_wydzialy(egeria_import)

    for elem in Diff_Wydzial_Delete.objects.all():
        elem.commit()

    with pytest.raises(Wydzial.DoesNotExist):
        w.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_wydzial_check_if_needed(uczelnia):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    w.widoczny = w.zezwalaj_na_ranking_autorow = True
    w.save()
    assert Diff_Wydzial_Delete.check_if_needed(w) == True

    w.widoczny = w.zezwalaj_na_ranking_autorow = False
    w.save()
    # skasowanie tego wydzialu jest potrzebne, mimo, że ukryty
    # bo nie ma żadnych jednostek podlinkowanych, czyli można go wyrzucić.
    assert Diff_Wydzial_Delete.check_if_needed(w) == True

    w.widoczny = w.zezwalaj_na_ranking_autorow = False
    w.save()
    Jednostka.objects.create(wydzial=w, nazwa="foo", skrot="bar")
    # skasowanie tego wydzialu NIE jest potrzebne, ma on podlinkowane
    # jednostki ALE już jest ukryty
    assert Diff_Wydzial_Delete.check_if_needed(w) == False

    w.widoczny = w.zezwalaj_na_ranking_autorow = True
    w.save()
    # skasowanie tego wydzialu jest jest potrzebne, ma on podlinkowane
    # jednostki i nie jest ukryty
    assert Diff_Wydzial_Delete.check_if_needed(w) == True


@pytest.mark.django_db
def test_egeria_models_wydzial_test_kasowania(uczelnia, egeria_import):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import).commit()
    # Upewnij się, że wydział bez jednostek znikł z bazy
    with pytest.raises(Wydzial.DoesNotExist):
        w.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_wydzial_test_kasowania_2(uczelnia, egeria_import):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    j = Jednostka.objects.create(nazwa="nazwa", skrot="skrt", wydzial=w)
    Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import).commit()
    # Upewnij się, że wydział z jednostką NIE znikł z bazy
    w.refresh_from_db()
    assert w.widoczny == False


@pytest.mark.django_db
def test_zrob_skrot(uczelnia):
    assert zrob_skrot("to jest test skrotowania do dlugosci maksymalnej", 7, Wydzial, "skrot") == "TJTSDDM"

    assert zrob_skrot("to tak", 3, Wydzial, "skrot") == "TT"

    Wydzial.objects.create(nazwa="taki istnieje", uczelnia=uczelnia, skrot="TT")
    assert zrob_skrot("to tak", 3, Wydzial, "skrot") == "TT1"

    assert zrob_skrot("to tak", 2, Wydzial, "skrot") == "T1"

    Wydzial.objects.create(nazwa="taki istnieje 2", uczelnia=uczelnia, skrot="T1")
    assert zrob_skrot("to tak", 2, Wydzial, "skrot") == "T2"


@pytest.mark.django_db
def test_egeria_models_Diff_Jednostka_Create_commit(wydzial, egeria_import):
    assert Jednostka.objects.all().count() == 0
    d = Diff_Jednostka_Create.objects.create(
        parent=egeria_import,
        nazwa="Test Jednostki",
        wydzial=wydzial
    )
    d.commit()

    assert d.commited
    assert Jednostka.objects.all().count() == 1
    j = Jednostka.objects.all()[0]
    assert j.nazwa == "Test Jednostki"
    assert j.skrot == "TJ"

@pytest.mark.django_db
def test_egeria_models_Diff_Jednostka_Update_check_if_needed(jednostka, wydzial, drugi_wydzial):

    # wariant 1: jednostka widoczna, ten sam wydział, aktualizacja NIE WYMAGANA
    jednostka.widoczna = True
    jednostka.wchodzi_do_raportow = True
    jednostka.wydzial = wydzial
    jednostka.save()

    ret = Diff_Jednostka_Update.check_if_needed(
        reference=jednostka,
        wydzial=wydzial)
    assert ret == False

    # wariant 2: jednostka widoczna, ale inny wydział, aktualizacja WYMAGANA\
    ret = Diff_Jednostka_Update.check_if_needed(
        reference=jednostka,
        wydzial=drugi_wydzial
    )
    assert ret == True

    # wariant 3: jednostka niewidoczna, ten sam wydział, aktualizacja WYMAGANA
    jednostka.widoczna = False
    ret = Diff_Jednostka_Update.check_if_needed(
        reference=jednostka,
        wydzial=wydzial
    )
    assert ret == True

@pytest.mark.django_db
def test_egeria_models_Diff_Jednostka_Update_commit(jednostka, wydzial, drugi_wydzial, egeria_import):

    jednostka.widoczna = jednostka.wchodzi_do_raportow = False
    jednostka.save()

    dju = Diff_Jednostka_Update.objects.create(
        parent=egeria_import,
        reference=jednostka,
        wydzial=drugi_wydzial
    )

    assert jednostka.wydzial == wydzial
    dju.commit()
    jednostka.refresh_from_db()
    assert jednostka.wydzial == drugi_wydzial
    assert jednostka.widoczna == True


@pytest.mark.django_db
@pytest.mark.xfail
def test_egeria_core_Diff_Jednostka_Delete_check_if_needed(uczelnia, egeria_import):
    raise NotImplementedError

@pytest.mark.django_db
@pytest.mark.xfail
def test_egeria_core_Diff_Jednostka_Delete_comit(uczelnia, egeria_import):
    raise NotImplementedError