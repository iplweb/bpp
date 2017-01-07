# -*- encoding: utf-8 -*-


import datetime
from md5 import md5

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from model_mommy import mommy

from bpp.models.autor import Tytul, Funkcja_Autora, Autor_Jednostka, Autor
from bpp.models.struktura import Uczelnia, Wydzial, Jednostka
from egeria.models import EgeriaRow, AlreadyAnalyzedError, Diff_Tytul_Create, Diff_Tytul_Delete, \
    Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete, Diff_Wydzial_Delete, Diff_Wydzial_Create
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Delete, Diff_Autor_Update
from egeria.models.core import EgeriaImport


@pytest.mark.django_db
def test_egeriaimport_clean():
    """Sprawdza, czy trigger uniemożliwiający utworzenie obiektu z datą 'Do' w przyszłości jest aktywny"""
    ei = EgeriaImport(do=datetime.date.today())
    with pytest.raises(ValidationError):
        ei.clean()


@pytest.mark.django_db
def test_egeriaimport_analyze(egeria_import):
    assert EgeriaRow.objects.all().count() == 0

    egeria_import.analyze()

    assert EgeriaRow.objects.all().count() > 10

    with pytest.raises(AlreadyAnalyzedError):
        egeria_import.analyze()


@pytest.mark.django_db
def test_egeria_management_commands_egeria_import(test_file_path, uczelnia):
    Tytul.objects.all().delete()
    assert Tytul.objects.all().count() == 0
    call_command('egeria_import', test_file_path)
    assert Tytul.objects.all().count() == 7


@pytest.mark.django_db
def test_egeria_models_EgeriaImport_diff_tytuly_test_commit_all(egeria_import, autor_jan_nowak):
    Tytul.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")

    egeria_import.analyze()
    egeria_import.diff_tytuly()
    egeria_import.commit_tytuly()


@pytest.mark.django_db
def test_egeria_models_EgeriaImport_diff_tytuly(egeria_import, autor_jan_nowak):
    assert Diff_Tytul_Create.objects.all().count() == 0
    assert Diff_Tytul_Delete.objects.all().count() == 0

    Tytul.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")
    j = Tytul.objects.create(nazwa="jeden to ma", skrot="j. t. m.")

    autor_jan_nowak.tytul = j
    autor_jan_nowak.save()

    egeria_import.analyze()
    egeria_import.diff_tytuly()

    assert u"nieistniejący tytuł" in Diff_Tytul_Create.objects.all().values_list("nazwa_skrot", flat=True)
    assert u"nikt tego nie ma" not in Diff_Tytul_Create.objects.all().values_list("nazwa_skrot", flat=True)

    assert u"dr. " in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"nikt tego nie ma" in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"jeden to ma" not in Diff_Tytul_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_models_EgeriaImport_diff_funkcje(egeria_import, autor_jan_nowak, jednostka):
    assert Diff_Funkcja_Autora_Create.objects.all().count() == 0
    assert Diff_Funkcja_Autora_Delete.objects.all().count() == 0

    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")
    j = Funkcja_Autora.objects.create(nazwa="jeden to ma", skrot="j. t. m.")

    Autor_Jednostka.objects.create(autor=autor_jan_nowak, jednostka=jednostka, funkcja=j)

    egeria_import.analyze()
    egeria_import.diff_funkcje()

    assert u"asystent dr" in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)
    assert u"nikt tego nie ma" not in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)

    assert u"nikt tego nie ma" in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"jeden to ma" not in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_models_EgeriaImport_diff_funkcje_test_commit_all(egeria_import, autor_jan_nowak):
    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")

    egeria_import.analyze()
    egeria_import.diff_funkcje()

    for elem in Diff_Funkcja_Autora_Create.objects.filter(parent=egeria_import):
        elem.commit()

    for elem in Diff_Funkcja_Autora_Delete.objects.filter(parent=egeria_import):
        elem.commit()


@pytest.mark.django_db
def test_egeria_models_diff_wydzialy_kasowanie(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)

    egeria_import.analyze()
    egeria_import.diff_wydzialy()

    assert WYDZIAL['nazwa'] in Diff_Wydzial_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_models_diff_wydzialy_testuj_ukrywanie_wydzialu(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    w = Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)
    assert w.widoczny == True
    assert w.zezwalaj_na_ranking_autorow == True

    Jednostka.objects.create(nazwa="Jednostka", skrot="J", wydzial=w)

    egeria_import.analyze()
    egeria_import.diff_wydzialy()

    for elem in Diff_Wydzial_Delete.objects.all():
        elem.commit()

    w.refresh_from_db()
    assert w.widoczny == False
    assert w.zezwalaj_na_ranking_autorow == False


@pytest.mark.django_db
def test_egeria_models_diff_wydzialy_testuj_kasowanie_wydzialu(egeria_import, uczelnia):
    WYDZIAL = dict(nazwa="tego wydzialu bankowo nie ma w pliku importu", skrot="twbn")
    w = Wydzial.objects.create(uczelnia=uczelnia, **WYDZIAL)

    egeria_import.analyze()
    egeria_import.diff_wydzialy()

    for elem in Diff_Wydzial_Delete.objects.all():
        elem.commit()

    with pytest.raises(Wydzial.DoesNotExist):
        w.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_EgeriaImport_diff_jednostki(egeria_import, uczelnia, autor_jan_kowalski):
    assert Jednostka.objects.all().count() == 0

    wt = Wydzial.objects.create(nazwa="Wydział Nauk o Zdrowiu", skrot="WZ", uczelnia=uczelnia)

    j = Jednostka.objects.create(
        nazwa=u'II Katedra i Klinika Chirurgii Og\xf3lnej, Gastroenterologicznej i Nowotwor\xf3w Uk\u0142adu Pokarmowego',
        skrot="123",
        wydzial=wt)

    jdu = Jednostka.objects.create(
        nazwa="Jednostka do usunięcia",
        skrot="JDU",
        wydzial=wt)

    jdsch = Jednostka.objects.create(
        nazwa="Jednostka do schowania",
        skrot="JDSCH",
        wydzial=wt
    )
    Autor_Jednostka.objects.create(
        autor=autor_jan_kowalski,
        jednostka=jdsch)

    egeria_import.analyze()

    egeria_import.diff_wydzialy()
    egeria_import.commit_wydzialy()

    egeria_import.diff_jednostki()
    egeria_import.commit_jednostki()

    assert Jednostka.objects.all().count() == 14  # 13 w pliku importu + jednostka do schowania

    j.refresh_from_db()
    assert j.wydzial != wt

    with pytest.raises(Jednostka.DoesNotExist):
        jdu.refresh_from_db()

    jdsch.refresh_from_db()
    assert jdsch.widoczna == False
    assert jdsch.wchodzi_do_raportow == False


@pytest.mark.django_db
def test_models_EgeriaImport_reset_import_steps(egeria_import):
    egeria_import.everything(cleanup=False)
    assert egeria_import.analysis_level != 0

    egeria_import.reset_import_steps()
    assert egeria_import.analysis_level == 0


@pytest.mark.django_db
def test_models_core_EgeriaImport_diff_autorzy_creates(egeria_import):
    egeria_import.everything(return_after_match_autorzy=True)
    egeria_import.diff_autorzy()
    assert Diff_Autor_Create.objects.all().count() == 0
    assert Diff_Autor_Update.objects.all().count() == 0
    assert Diff_Autor_Delete.objects.all().count() == 0


@pytest.mark.django_db
def test_models_core_diff_autorzy_updates(egeria_import, egeria_import_imported):
    t = Tytul.objects.create(nazwa="123", skrot="456")
    mommy.make(Autor, tytul=t, nazwisko="Kowalska", imiona="Oleg", pesel_md5=md5("aaa").hexdigest())

    # Zmieni tytuł
    egeria_import.everything(return_after_match_autorzy=True)
    egeria_import.diff_autorzy()
    assert Diff_Autor_Create.objects.all().count() == 0
    assert Diff_Autor_Update.objects.all().count() == 1
    assert Diff_Autor_Delete.objects.all().count() == 0


@pytest.mark.django_db
def test_models_core_diff_autorzy_deletes(egeria_import, egeria_import_imported):
    a = mommy.make(Autor, nazwisko="Kowalska 5", imiona="Oleg 10", pesel_md5=md5("xx123123123aaa").hexdigest())
    u = mommy.make(Uczelnia)
    w = mommy.make(Wydzial, uczelnia=u)
    j = mommy.make(Jednostka, wydzial=w, uczelnia=u)
    j.dodaj_autora(a)

    egeria_import.analyze()
    egeria_import.rows().first().delete()

    egeria_import.everything(return_after_match_autorzy=True, dont_analyze=True)
    egeria_import.diff_autorzy()
    assert Diff_Autor_Create.objects.all().count() == 0
    assert Diff_Autor_Update.objects.all().count() == 0
    assert Diff_Autor_Delete.objects.all().count() == 1
