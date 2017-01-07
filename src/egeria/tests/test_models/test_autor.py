# -*- encoding: utf-8 -*-
from datetime import date
from md5 import md5

import pytest
from django.utils import timezone

from bpp.models.autor import Tytul, Funkcja_Autora, Autor_Jednostka, Autor
from bpp.models.struktura import Jednostka
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Delete, Diff_Autor_Update


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
def test_models_Diff_Autor_Delete_check_if_needed(egeria_import, autor_jan_nowak, uczelnia, jednostka, obca_jednostka, wydawnictwo_ciagle):
    egeria_import.od = date(2012, 1, 1)
    egeria_import.save()

    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()

    # Autor bez rekordow
    assert Diff_Autor_Delete.check_if_needed(egeria_import, autor_jan_nowak) == True

    # Autor z rekordem, ale bez powiązanych jednostek - usuwanie nie potrzebne,
    # nie jest nigdzie przypisany ALE powinien byc taki ktoś przypisany do obcej jednostki,
    # zatem
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    assert Diff_Autor_Delete.check_if_needed(egeria_import, autor_jan_nowak) == True

    # Autor z rekordem, ale aktualna jednostka to obca jednostka
    Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=obca_jednostka,
    )
    autor_jan_nowak.refresh_from_db()  # Pobierz zmianę z triggera
    assert autor_jan_nowak.aktualna_jednostka == obca_jednostka
    assert Diff_Autor_Delete.check_if_needed(egeria_import, autor_jan_nowak) == False
    Autor_Jednostka.objects.all().delete()

    # Autor z rekordem, ale aktualna jednsotka jest nie-obca
    Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now(),
    )
    autor_jan_nowak.refresh_from_db()  # Pobierz zmianę z triggera
    assert autor_jan_nowak.aktualna_jednostka == jednostka
    assert Diff_Autor_Delete.check_if_needed(egeria_import, autor_jan_nowak) == True


@pytest.mark.django_db
def test_models_Diff_Autor_Delete_commit(autor_jan_nowak, autor_jan_kowalski, jednostka, obca_jednostka,
                                         druga_jednostka, wydawnictwo_ciagle, egeria_import):
    # Skasuj autora bez powiazan
    dad = Diff_Autor_Delete.objects.create(parent=egeria_import, reference=autor_jan_nowak)
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

    dad = Diff_Autor_Delete.objects.create(parent=egeria_import, reference=autor_jan_kowalski)
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

    dad = Diff_Autor_Delete.objects.create(parent=egeria_import, reference=autor_jan_stefan)
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
def test_models_Diff_Autor_Update_check_if_needed(autor_jan_nowak, jednostka):
    autor_jan_nowak.pesel_md5 = md5("foobar").hexdigest()

    jednostka.dodaj_autora(autor_jan_nowak)

    nowa_jednostka = Jednostka.objects.create(nazwa="nowa zupelnie", skrot="nzj", wydzial=jednostka.wydzial)
    nowy_tytul = Tytul.objects.create(nazwa="nowy tytul", skrot="nt")
    nowa_funkcja_autora = Funkcja_Autora.objects.create(nazwa="nowa funkcja autora", skrot="nfa")

    obecne_nazwisko = autor_jan_nowak.nazwisko
    obecne_imiona = autor_jan_nowak.imiona
    obecna_jednostka = autor_jan_nowak.aktualna_jednostka
    obecny_tytul = autor_jan_nowak.tytul
    obecna_funkcja_autora = autor_jan_nowak.aktualna_funkcja
    obecny_pesel_md5 = autor_jan_nowak.pesel_md5

    # Wszystko to samo
    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona=obecne_imiona,
        jednostka=obecna_jednostka,
        tytul=obecny_tytul,
        funkcja=obecna_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) != True

    # Sprawdzamy dla każdego elementu
    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko="Nowe takie",
        imiona=obecne_imiona,
        jednostka=obecna_jednostka,
        tytul=obecny_tytul,
        funkcja=obecna_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) == True

    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona="Czyzby zmiana imienia",
        jednostka=nowa_jednostka,
        tytul=obecny_tytul,
        funkcja=obecna_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) == True

    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona=obecne_imiona,
        jednostka=nowa_jednostka,
        tytul=obecny_tytul,
        funkcja=obecna_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) == True

    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona=obecne_imiona,
        jednostka=obecna_jednostka,
        tytul=nowy_tytul,
        funkcja=obecna_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) == True

    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona=obecne_imiona,
        jednostka=obecna_jednostka,
        tytul=obecny_tytul,
        funkcja=nowa_funkcja_autora,
        pesel_md5=obecny_pesel_md5
    )) == True

    assert Diff_Autor_Update.check_if_needed(egeria_import, dict(
        reference=autor_jan_nowak,
        nazwisko=obecne_nazwisko,
        imiona=obecne_imiona,
        jednostka=obecna_jednostka,
        tytul=obecny_tytul,
        funkcja=nowa_funkcja_autora,
        pesel_md5=md5('jakis inny pesel').hexdigest()
    )) == True


@pytest.mark.django_db
def test_models_Diff_Autor_Update_commit(egeria_import, autor_jan_nowak, tytuly, funkcje_autorow, druga_jednostka):
    pesel_md5 = md5("pesel").hexdigest()

    nowy_tytul = tytuly.first()

    autor_jan_nowak.tytul = tytuly.last()
    autor_jan_nowak.save()

    assert autor_jan_nowak.aktualna_jednostka != druga_jednostka
    assert autor_jan_nowak.aktualna_funkcja != funkcje_autorow.last()
    assert autor_jan_nowak.tytul != nowy_tytul
    assert autor_jan_nowak.pesel_md5 != pesel_md5

    Diff_Autor_Update.objects.create(
        parent=egeria_import,
        reference=autor_jan_nowak,
        tytul=nowy_tytul,
        funkcja=funkcje_autorow.last(),
        jednostka=druga_jednostka,
        pesel_md5=pesel_md5
    ).commit()

    autor_jan_nowak.refresh_from_db()

    assert autor_jan_nowak.aktualna_jednostka == druga_jednostka
    assert autor_jan_nowak.aktualna_funkcja == funkcje_autorow.last()
    assert autor_jan_nowak.tytul == nowy_tytul
    assert autor_jan_nowak.pesel_md5 == pesel_md5
