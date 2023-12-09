from datetime import date, timedelta

import pytest
from model_bakery import baker

from django.utils import timezone

from bpp.models import Autor_Jednostka
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


def test_Jednostka_aktualni_autorzy(jednostka, autor_jan_nowak, druga_jednostka):
    assert len(jednostka.aktualni_autorzy()) == 0

    aj = Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor_jan_nowak)

    assert len(jednostka.aktualni_autorzy()) == 1

    daj = Autor_Jednostka.objects.create(
        jednostka=druga_jednostka, autor=autor_jan_nowak, podstawowe_miejsce_pracy=True
    )

    assert len(jednostka.aktualni_autorzy()) == 0
    assert len(druga_jednostka.aktualni_autorzy()) == 1

    daj.zakonczyl_prace = timezone.now() - timedelta(days=5)
    daj.save()

    # Po zakończeniu pracy w domyślnym miejscu pracy 5 dni temu, aktualną jednostką
    # pozostanie jednostka pierwsza
    assert len(jednostka.aktualni_autorzy()) == 1
    assert len(druga_jednostka.aktualni_autorzy()) == 0

    aj.zakonczyl_prace = timezone.now() - timedelta(days=5)
    aj.save()

    # Po zakonczeniu pracy w pierwszej jednostce, aktualna jednostka będzie pusta
    assert len(jednostka.aktualni_autorzy()) == 0
    assert len(druga_jednostka.aktualni_autorzy()) == 0


def test_Jednostka_pracownicy(jednostka, autor_jan_nowak):
    Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor_jan_nowak)
    assert jednostka.pracownicy().count() == 1


def test_Jednostka_wspolpracowali(autor_jan_nowak, druga_jednostka, wydawnictwo_ciagle):
    daj = Autor_Jednostka.objects.create(
        jednostka=druga_jednostka, autor=autor_jan_nowak, podstawowe_miejsce_pracy=True
    )
    daj.zakonczyl_prace = timezone.now() - timedelta(days=5)
    daj.save()

    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka_id is None

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, druga_jednostka)

    assert druga_jednostka.wspolpracowali().count() == 1


def test_Jednostka_wspolpracowali_alt(
    jednostka,
    uczelnia,
    wydzial,
    autor_jan_nowak,
    autor_jan_kowalski,
    wydawnictwo_ciagle,
):
    Autor_Jednostka.objects.all().delete()

    assert autor_jan_nowak.pk not in jednostka.aktualni_autorzy()

    # Kowalski to obecny pracownik
    Autor_Jednostka.objects.create(
        autor=autor_jan_kowalski, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )

    assert autor_jan_nowak.pk not in jednostka.aktualni_autorzy()

    # Nowak to osoba ktora wczesniej miala publikacje
    wydawnictwo_ciagle.dodaj_autora(autor=autor_jan_nowak, jednostka=jednostka)

    # usuń powiązanie Nowaka z jednostką, wydawnictwo_ciagle.dodaj_autora przez
    # DodajAutoraMixin automatycznie tworzy powiązanie (przy ustawieniu
    # BPP_DODAWAJ_JEDNOSTKE_PRZY_ZAPISIE_PRACY
    Autor_Jednostka.objects.filter(autor=autor_jan_nowak).delete()

    assert autor_jan_kowalski in jednostka.pracownicy()
    assert autor_jan_nowak not in jednostka.pracownicy()

    assert autor_jan_nowak in jednostka.wspolpracowali()
    assert autor_jan_kowalski not in jednostka.wspolpracowali()
