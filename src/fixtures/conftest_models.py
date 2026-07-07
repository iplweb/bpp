"""Core model fixtures: uczelnia, wydzial, jednostka, autor, zrodlo."""

from datetime import datetime

import pytest
from model_bakery import baker

from bpp.models.autor import Autor, Tytul
from bpp.models.struktura import Jednostka, Uczelnia
from bpp.models.zrodlo import Zrodlo

from .const import JEDNOSTKA_PODRZEDNA, JEDNOSTKA_UCZELNI


def current_rok():
    return datetime.now().date().year


@pytest.fixture
def rok():
    return current_rok()


@pytest.fixture(scope="function")
def uczelnia(db):
    from django.contrib.sites.models import Site

    site, _ = Site.objects.get_or_create(
        domain="testserver", defaults={"name": "testserver"}
    )
    return Uczelnia.objects.get_or_create(
        skrot="TE",
        defaults={"nazwa": "Testowa uczelnia", "site": site},
    )[0]


@pytest.fixture
def uczelnia_z_obca_jednostka(uczelnia, obca_jednostka):
    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()
    return uczelnia


@pytest.mark.django_db
def _wydzial_maker(nazwa, skrot, uczelnia, **kwargs):
    # Faza C (#438): „wydział" = jednostka top-level (``parent IS NULL``).
    return Jednostka.objects.get_or_create(
        uczelnia=uczelnia, skrot=skrot, nazwa=nazwa, parent=None, **kwargs
    )[0]


@pytest.fixture
def wydzial_maker(db):
    return _wydzial_maker


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
    # Faza C (#438): „wydział" to jednostka top-level (root). Jednostka
    # „w wydziale" wisi wprost pod nim (MPTT ``parent``), a denorm ``wydzial``
    # (korzeń) wylicza się przy zapisie.
    parent = kwargs.pop("parent", None)
    if parent is None and wydzial is not None:
        parent = wydzial
    ret = Jednostka.objects.get_or_create(
        nazwa=nazwa,
        skrot=skrot,
        parent=parent,
        uczelnia=wydzial.uczelnia,
        **kwargs,
    )[0]
    ret.refresh_from_db()
    return ret


@pytest.fixture(scope="function")
def jednostka(wydzial, db):
    return _jednostka_maker(JEDNOSTKA_UCZELNI, skrot="Jedn. Ucz.", wydzial=wydzial)


@pytest.fixture(scope="function")
def kolo_naukowe(jednostka: Jednostka):
    from bpp.models import RodzajJednostki

    # Faza B (#438), III-1: wykluczenie kół z rankingu idzie przez FK
    # ``rodzaj`` + flagę ``wyklucz_z_rankingu_autorow`` (CharField
    # ``rodzaj_jednostki`` usunięty).
    rodzaj, _ = RodzajJednostki.objects.get_or_create(
        nazwa="Koło naukowe", defaults={"wyklucz_z_rankingu_autorow": True}
    )
    if not rodzaj.wyklucz_z_rankingu_autorow:
        rodzaj.wyklucz_z_rankingu_autorow = True
        rodzaj.save()
    jednostka.nazwa = "Studenckie Koło Naukowe Przykładowe"
    jednostka.skrot = "SKN"
    jednostka.rodzaj = rodzaj
    jednostka.save()
    return jednostka


@pytest.fixture(scope="function")
def aktualna_jednostka(jednostka: Jednostka, wydzial, db):
    # Faza C (#438): „wydział" to jednostka top-level; metryczka wskazuje
    # wprost na nią (parent).
    jednostka.jednostka_rodzic_set.create(parent=wydzial)
    jednostka.refresh_from_db()
    return jednostka


@pytest.fixture
def drugi_wydzial(uczelnia):
    return baker.make(Jednostka, uczelnia=uczelnia, parent=None)


@pytest.fixture
def druga_aktualna_jednostka(druga_jednostka, drugi_wydzial):
    druga_jednostka.jednostka_rodzic_set.create(parent=drugi_wydzial)
    druga_jednostka.refresh_from_db()
    return druga_jednostka


@pytest.fixture(scope="function")
def jednostka_podrzedna(jednostka):
    return _jednostka_maker(
        JEDNOSTKA_PODRZEDNA, skrot="JP", wydzial=jednostka.wydzial, parent=jednostka
    )


@pytest.fixture(scope="function")
def druga_jednostka(wydzial, db):
    return _jednostka_maker(
        "Druga Jednostka Uczelni", skrot="Dr. Jedn. Ucz.", wydzial=wydzial
    )


@pytest.fixture(scope="function")
def obca_jednostka(wydzial):
    return _jednostka_maker(
        "Obca Jednostka",
        skrot="OJ",
        wydzial=wydzial,
        skupia_pracownikow=False,
        zarzadzaj_automatycznie=False,
        widoczna=False,
        wchodzi_do_rankingu_autorow=False,
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


@pytest.fixture
def kierunek_studiow(wydzial):
    from bpp.models import Kierunek_Studiow

    # Faza C (#438) II-2: ``Kierunek_Studiow.wydzial`` to FK->Jednostka
    # (jednostka top-level = dawny „wydział").
    return Kierunek_Studiow.objects.get_or_create(
        wydzial=wydzial,
        nazwa="memetyka użytkowa",
        skrot="mem. uż.",
        opis="testowy kierunek studiów",
    )[0]
