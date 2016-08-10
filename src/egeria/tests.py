# -*- encoding: utf-8 -*-


from datetime import timedelta
from md5 import md5

import pytest
from django.core.management import call_command
from django.utils import timezone

from bpp.models.autor import Tytul, Funkcja_Autora, Autor_Jednostka, Autor
from bpp.models.struktura import Uczelnia, Wydzial, Jednostka
from egeria.models import EgeriaRow, AlreadyAnalyzedError, Diff_Tytul_Create, Diff_Tytul_Delete, \
    Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete, Diff_Wydzial_Delete, Diff_Wydzial_Create, zrob_skrot, \
    Diff_Jednostka_Create, Diff_Jednostka_Update, Diff_Jednostka_Delete
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Delete, Diff_Autor_Update


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
def test_egeria_models_diff_funkcje(egeria_import, autor_jan_nowak, jednostka):
    assert Diff_Funkcja_Autora_Create.objects.all().count() == 0
    assert Diff_Funkcja_Autora_Delete.objects.all().count() == 0

    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")
    j = Funkcja_Autora.objects.create(nazwa="jeden to ma", skrot="j. t. m.")

    Autor_Jednostka.objects.create(autor=autor_jan_nowak, jednostka=jednostka, funkcja=j)

    egeria_import.analyze()
    egeria_import.diff_funkcje()

    assert u"Asystent dr" in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)
    assert u"nikt tego nie ma" not in Diff_Funkcja_Autora_Create.objects.all().values_list("nazwa_skrot", flat=True)

    assert u"nikt tego nie ma" in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)
    assert u"jeden to ma" not in Diff_Funkcja_Autora_Delete.objects.all().values_list("reference__nazwa", flat=True)


@pytest.mark.django_db
def test_egeria_models_diff_funkcje_test_commit_all(egeria_import, autor_jan_nowak):
    Funkcja_Autora.objects.create(nazwa="nikt tego nie ma", skrot="n. t. n. m.")

    egeria_import.analyze()
    egeria_import.diff_funkcje()

    for elem in Diff_Funkcja_Autora_Create.objects.filter(parent=egeria_import):
        elem.commit()

    for elem in Diff_Funkcja_Autora_Delete.objects.filter(parent=egeria_import):
        elem.commit()


@pytest.mark.django_db
def test_egeria_models_diff_wydzialy_uczelnia_is_created(egeria_import):
    Uczelnia.objects.all().delete()
    assert Uczelnia.objects.all().count() == 0

    egeria_import.analyze()
    egeria_import.diff_wydzialy()

    Diff_Wydzial_Create.objects.all().first().commit()

    assert Uczelnia.objects.all().count() == 1


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
def test_egeria_models_Diff_Wydzial_Delete_wariant_1(uczelnia, egeria_import):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    dwd = Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import)
    dwd.commit()
    # Upewnij się, że wydział bez jednostek znikł z bazy
    with pytest.raises(Wydzial.DoesNotExist):
        w.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_Diff_Wydzial_Delete_wariant_2(uczelnia, egeria_import):
    w = Wydzial.objects.create(uczelnia=uczelnia, nazwa="foo", skrot="bar")
    j = Jednostka.objects.create(nazwa="nazwa", skrot="skrt", wydzial=w)
    dwd = Diff_Wydzial_Delete.objects.create(reference=w, parent=egeria_import)
    dwd.commit()
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

    ret = Diff_Jednostka_Update.check_if_needed(dict(
        reference=jednostka,
        wydzial=wydzial))
    assert ret == False

    # wariant 2: jednostka widoczna, ale inny wydział, aktualizacja WYMAGANA\
    ret = Diff_Jednostka_Update.check_if_needed(dict(
        reference=jednostka,
        wydzial=drugi_wydzial))
    assert ret == True

    # wariant 3: jednostka niewidoczna, ten sam wydział, aktualizacja WYMAGANA
    jednostka.widoczna = False
    ret = Diff_Jednostka_Update.check_if_needed(dict(
        reference=jednostka,
        wydzial=wydzial))
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
def test_egeria_models_Diff_Jednostka_Delete_check_if_needed(jednostka, egeria_import):
    jednostka.widoczna = jednostka.wchodzi_do_raportow = True
    jednostka.wydzial.archiwalny = False
    jednostka.wydzial.save()
    jednostka.save()

    # Wariant 1: jednostka jest widoczna i w wydziale nie-archiwalnym
    assert Diff_Jednostka_Delete.check_if_needed(jednostka) == True

    # Wariant 2: jednostka jest niewidoczna, ale w wydziale nie-archiwalnym
    jednostka.widoczna = jednostka.wchodzi_do_raportow = False
    jednostka.save()
    assert Diff_Jednostka_Delete.check_if_needed(jednostka) == True

    # Wariant 3: jednostka jest niewidoczna, w wydziale archiwalnym
    jednostka.wydzial.archiwalny = True
    jednostka.wydzial.save()
    assert Diff_Jednostka_Delete.check_if_needed(jednostka) == False


@pytest.mark.django_db
def test_egeria_models_Diff_Jednostka_Delete_comit_wariant_1(jednostka, wydzial, wydzial_archiwalny, autor,
                                                             egeria_import):
    wydzial.archiwalny = False
    wydzial.save()

    jednostka.wydzial = wydzial
    jednostka.widoczna = jednostka.wchodzi_do_raportow = True
    jednostka.save()

    aj = Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka
    )

    # Wariant 1: jednostka jest powiązana z innymi rekordami w bazie danych,
    # w rezultacie ma pozostać niewidoczna oraz przesunięta do wydziału archiwalnego
    djd = Diff_Jednostka_Delete.objects.create(
        parent=egeria_import,
        reference=jednostka
    )
    djd.commit()

    jednostka.refresh_from_db()
    assert jednostka.widoczna == jednostka.wchodzi_do_raportow == False
    assert jednostka.wydzial == wydzial_archiwalny


@pytest.mark.django_db
def test_egeria_models_Diff_Jednostka_Delete_comit_wariant_2(jednostka, wydzial, wydzial_archiwalny, autor,
                                                             egeria_import):
    wydzial.archiwalny = False
    wydzial.save()

    jednostka.wydzial = wydzial
    jednostka.widoczna = jednostka.wchodzi_do_raportow = True
    jednostka.save()

    # Wariant 2: jednostka nie jest powiązana z innymi rekordami w bazie danych,
    # ma zostać fizycznie usunięta
    djd = Diff_Jednostka_Delete.objects.create(
        parent=egeria_import,
        reference=jednostka
    )
    djd.commit()

    with pytest.raises(Jednostka.DoesNotExist):
        jednostka.refresh_from_db()


@pytest.mark.django_db
def test_egeria_models_diff_jednostki(egeria_import, uczelnia, autor_jan_kowalski):
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
def test_egeria_models_core_EgeriaImport_match_autorzy(egeria_import, jednostka):

    egeria_import.rows().delete()

    pesel_md5 = md5("foobar").hexdigest()

    row = EgeriaRow.objects.create(
        parent=egeria_import,
        lp=1,
        tytul_stopien="foobar",
        nazwisko="Kowalski",
        imie="Stefan",
        pesel_md5=pesel_md5,
        stanowisko="kierownik",
        nazwa_jednostki=jednostka.nazwa,
        wydzial=jednostka.wydzial.nazwa
    )

    # Strategia 0 - nowy rekord
    egeria_import.match_autorzy()
    row.refresh_from_db()
    assert row.unmatched_because_new


    # Strategia 1
    autor = Autor.objects.create(
        nazwisko="Kowalski",
        imiona="Stefan",
        pesel_md5="hmmm... "
    )

    egeria_import.match_autorzy()
    row.refresh_from_db()
    assert row.matched_autor == autor

    row.matched_autor = None
    row.save()

    # Strategia 2
    # Dwóch autorów o identycznych personalniach, jeden ma inny pesel md5 hash
    autor2 = Autor.objects.create(
        nazwisko="Kowalski",
        imiona="Stefan",
        pesel_md5=pesel_md5
    )

    egeria_import.match_autorzy()
    row.refresh_from_db()
    assert row.matched_autor == autor2

    # Strategia 3
    # Dwóch autorów o identycznych personaliach, jeden ma jednostke w zatrudnieniu
    autor2.pesel_md5 = "inny niz byl"
    autor2.save()

    row.matched_autor = None
    row.matched_jednostka = jednostka
    row.save()

    autor2.dodaj_jednostke(jednostka)

    egeria_import.match_autorzy()
    row.refresh_from_db()
    assert row.matched_autor == autor2


    row.matched_autor = None
    row.save()
    Autor_Jednostka.objects.filter(autor=autor2).delete()

    # Strategia 4 - nie można określić
    egeria_import.match_autorzy()
    row.refresh_from_db()
    assert row.unmatched_because_multiple == True

@pytest.mark.django_db
def test_models_Diff_Autor_Create(jednostka, funkcje_autorow, tytuly):
    c = Diff_Autor_Create(
        nazwisko="Foo",
        imiona="Bar",
        pesel_md5="ha",

        jednostka=jednostka,
        funkcja=funkcje_autorow.first(),
        tytul=tytuly.first(),
    )

    c.commit()

    assert Autor.objects.all().count() == 1

    # Upewnij się, że powstał obiekt
    assert Autor_Jednostka.objects.all().count() == 1
    assert Autor_Jednostka.objects.all().first().autor.nazwisko == "Foo"


@pytest.mark.django_db
def test_models_Diff_Autor_Delete_check_if_needed(autor_jan_nowak, jednostka, obca_jednostka, wydawnictwo_ciagle):
    # Autor bez rekordow
    assert Diff_Autor_Delete.check_if_needed(autor_jan_nowak) == True

    # Autor z rekordem, ale bez jednostek
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    assert Diff_Autor_Delete.check_if_needed(autor_jan_nowak) == True

    # Autor z rekordem, ale aktualna jednostka to obca jednostka
    Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=obca_jednostka,
        rozpoczal_prace=timezone.now(),
    )
    autor_jan_nowak.save()
    assert autor_jan_nowak.aktualna_jednostka == obca_jednostka
    assert Diff_Autor_Delete.check_if_needed(autor_jan_nowak) != True
    Autor_Jednostka.objects.all().delete()

    # Autor z rekordem, ale aktualna jednsotka jest nie-obca
    Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now(),
    )
    autor_jan_nowak.save()
    assert autor_jan_nowak.aktualna_jednostka == jednostka
    assert Diff_Autor_Delete.check_if_needed(autor_jan_nowak) == True

@pytest.mark.django_db
def test_models_Diff_Autor_Delete_commit(autor_jan_nowak, autor_jan_kowalski, jednostka, obca_jednostka, druga_jednostka, wydawnictwo_ciagle):

    # Skasuj autora bez powiazan
    dad = Diff_Autor_Delete.objects.create(reference=autor_jan_nowak)
    dad.commit()
    with pytest.raises(Diff_Autor_Delete.DoesNotExist):
        dad.refresh_from_db()

    # "Skasuj" autora z powiazaniami, czyli:
    # - zakończ pracę we wszystkich jednostkach
    # - dodaj obca jednostke do jego jednostek,
    aj = Autor_Jednostka.objects.create(
        autor=autor_jan_kowalski,
        jednostka=jednostka)

    # Autor musi mieć powiązania z jakimikolwiek rekordami, aby być przeniesiony do "Obcej jednostki",
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    dad = Diff_Autor_Delete.objects.create(reference=autor_jan_kowalski)
    dad.commit()
    with pytest.raises(Diff_Autor_Delete.DoesNotExist):
        dad.refresh_from_db()

    assert Autor_Jednostka.objects.all().count() == 2

    # "Skasuj" autora z powiązaniami, ale z już dodaną obcą jednostką, czyli:
    # - zakończ pracę we wszystkich jednostkach
    # - rozpocznij pracę w obcej jednostce
    trzy_miesiace_temu = (timezone.now() - timedelta(days=90)).date()
    autor_jan_stefan = Autor.objects.create(nazwisko="Stefan", imiona="Jan")
    wydawnictwo_ciagle.dodaj_autora(autor_jan_stefan, jednostka)
    aj1 = Autor_Jednostka.objects.create(autor=autor_jan_stefan, jednostka=jednostka)
    aj2 = Autor_Jednostka.objects.create(autor=autor_jan_stefan, jednostka=obca_jednostka)
    aj3 = Autor_Jednostka.objects.create(autor=autor_jan_stefan, jednostka=druga_jednostka,
                                         zakonczyl_prace=trzy_miesiace_temu)


    dad = Diff_Autor_Delete.objects.create(reference=autor_jan_stefan)
    dad.commit()
    with pytest.raises(Diff_Autor_Delete.DoesNotExist):
        dad.refresh_from_db()

    for elem in aj1, aj2, aj3:
        elem.refresh_from_db()

    assert aj1.rozpoczal_prace == None
    assert aj1.zakonczyl_prace != None

    assert aj2.rozpoczal_prace == timezone.now().date()
    assert aj2.zakonczyl_prace == None

    assert aj3.rozpoczal_prace == None
    assert aj3.zakonczyl_prace == trzy_miesiace_temu


@pytest.mark.django_db
def test_models_Diff_Autor_Update_check_if_needed(autor_jan_nowak):
    raise NotImplementedError


@pytest.mark.django_db
def test_models_Diff_Autor_Update_commit(autor_jan_nowak, tytuly, funkcje_autorow, druga_jednostka):
    Diff_Autor_Update.objects.create(
        reference=autor_jan_nowak,
        tytul=tytuly.first(),
        funkcja=funkcje_autorow.last(),
        jednostka=druga_jednostka
    ).commit()

