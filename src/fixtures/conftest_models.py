"""Core model fixtures: uczelnia, wydzial, jednostka, autor, zrodlo."""

from datetime import datetime

import pytest
from model_bakery import baker

from bpp.models.autor import Autor, Tytul
from bpp.models.struktura import Jednostka, Uczelnia, Wydzial
from bpp.models.zrodlo import Zrodlo


def current_rok():
    return datetime.now().date().year


@pytest.fixture
def rok():
    return current_rok()


@pytest.fixture(scope="function")
def uczelnia(db):
    return Uczelnia.objects.get_or_create(
        skrot="TE",
        nazwa="Testowa uczelnia",
    )[0]


@pytest.fixture
def uczelnia_z_obca_jednostka(uczelnia, obca_jednostka):
    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()
    return uczelnia


@pytest.mark.django_db
def _wydzial_maker(nazwa, skrot, uczelnia, **kwargs):
    return Wydzial.objects.get_or_create(
        uczelnia=uczelnia, skrot=skrot, nazwa=nazwa, **kwargs
    )[0]


@pytest.mark.django_db
@pytest.fixture
def wydzial_maker(db):
    return _wydzial_maker


@pytest.mark.django_db
@pytest.fixture(scope="function")
def wydzial(uczelnia, db):
    return _wydzial_maker(uczelnia=uczelnia, skrot="W1", nazwa="Wydział Testowy I")


def _autor_maker(imiona, nazwisko, tytul="dr", **kwargs):
    tytul = Tytul.objects.get(skrot=tytul)
    return Autor.objects.get_or_create(
        tytul=tytul, imiona=imiona, nazwisko=nazwisko, **kwargs
    )[0]


@pytest.fixture
def autor_maker(db):
    return _autor_maker


@pytest.fixture(scope="function")
def autor_jan_nowak(db, tytuly) -> Autor:
    return _autor_maker(imiona="Jan", nazwisko="Nowak")


@pytest.fixture(scope="function")
def autor(db, tytuly) -> Autor:
    return baker.make(Autor)


@pytest.fixture(scope="function")
def autor_jan_kowalski(db, tytuly) -> Autor:
    return _autor_maker(imiona="Jan", nazwisko="Kowalski", tytul="prof. dr hab. med.")


def _jednostka_maker(nazwa, skrot, wydzial, **kwargs):
    ret = Jednostka.objects.get_or_create(
        nazwa=nazwa, skrot=skrot, wydzial=wydzial, uczelnia=wydzial.uczelnia, **kwargs
    )[0]
    ret.refresh_from_db()
    return ret


JEDNOSTKA_UCZELNI = "Jednostka Uczelni"


@pytest.mark.django_db
@pytest.fixture(scope="function")
def jednostka(wydzial, db):
    return _jednostka_maker(JEDNOSTKA_UCZELNI, skrot="Jedn. Ucz.", wydzial=wydzial)


@pytest.mark.django_db
@pytest.fixture(scope="function")
def kolo_naukowe(jednostka: Jednostka):
    jednostka.nazwa = "Studenckie Koło Naukowe Przykładowe"
    jednostka.skrot = "SKN"
    jednostka.rodzaj_jednostki = Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
    jednostka.save()
    return jednostka


@pytest.mark.django_db
@pytest.fixture(scope="function")
def aktualna_jednostka(jednostka: Jednostka, wydzial, db):
    jednostka.jednostka_wydzial_set.create(wydzial=wydzial)
    jednostka.refresh_from_db()
    return jednostka


@pytest.mark.django_db
@pytest.fixture
def drugi_wydzial(uczelnia):
    return baker.make(Wydzial, uczelnia=uczelnia)


@pytest.mark.django_db
@pytest.fixture
def druga_aktualna_jednostka(druga_jednostka, drugi_wydzial):
    druga_jednostka.jednostka_wydzial_set.create(wydzial=drugi_wydzial)
    druga_jednostka.refresh_from_db()
    return druga_jednostka


JEDNOSTKA_PODRZEDNA = "Jednostka P-rzedna"


@pytest.mark.django_db
@pytest.fixture(scope="function")
def jednostka_podrzedna(jednostka):
    return _jednostka_maker(
        JEDNOSTKA_PODRZEDNA, skrot="JP", wydzial=jednostka.wydzial, parent=jednostka
    )


@pytest.mark.django_db
@pytest.fixture(scope="function")
def druga_jednostka(wydzial, db):
    return _jednostka_maker(
        "Druga Jednostka Uczelni", skrot="Dr. Jedn. Ucz.", wydzial=wydzial
    )


@pytest.mark.django_db
@pytest.fixture(scope="function")
def obca_jednostka(wydzial):
    return _jednostka_maker(
        "Obca Jednostka",
        skrot="OJ",
        wydzial=wydzial,
        skupia_pracownikow=False,
        zarzadzaj_automatycznie=False,
        widoczna=False,
        wchodzi_do_raportow=False,
    )


@pytest.fixture
def jednostka_maker():
    return _jednostka_maker


def _zrodlo_maker(nazwa, skrot, **kwargs):
    return baker.make(Zrodlo, nazwa=nazwa, skrot=skrot, **kwargs)


@pytest.fixture
def zrodlo_maker():
    return _zrodlo_maker


@pytest.fixture(scope="function")
def zrodlo(db):
    return _zrodlo_maker(nazwa="Testowe Źródło", skrot="Test. Źr.")
