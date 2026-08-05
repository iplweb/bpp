"""#438: ``Jednostka.przyjmuje_afiliacje()`` — czy autor pracy może afiliować
(``afiliuje=True``) do danej jednostki.

Zwraca ``False`` dla jednostek obcych (``skupia_pracownikow=False``) oraz
jednostek, których rodzaj zabrania afiliacji
(``RodzajJednostki.autor_moze_afiliowac=False``, np. węzeł-lustro „Wydział").
Jest to instancyjny odpowiednik logiki z
``BazaModeluOdpowiedzialnosciAutorow._waliduj_afiliacje``.
"""

import pytest

from bpp.models import RodzajJednostki


@pytest.mark.django_db
def test_zwykla_jednostka_przyjmuje_afiliacje(jednostka):
    assert jednostka.rodzaj is None
    assert jednostka.skupia_pracownikow is True
    assert jednostka.przyjmuje_afiliacje() is True


@pytest.mark.django_db
def test_jednostka_rodzaju_wydzial_nie_przyjmuje_afiliacji(jednostka):
    rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    assert rodzaj.autor_moze_afiliowac is False
    jednostka.rodzaj = rodzaj
    jednostka.save()
    assert jednostka.przyjmuje_afiliacje() is False


@pytest.mark.django_db
def test_obca_jednostka_nie_przyjmuje_afiliacji(jednostka):
    jednostka.skupia_pracownikow = False
    jednostka.save()
    assert jednostka.przyjmuje_afiliacje() is False


@pytest.mark.django_db
def test_jednostka_rodzaju_dopuszczajacego_przyjmuje_afiliacje(jednostka):
    rodzaj = RodzajJednostki.objects.create(
        nazwa="Instytut przykładowy", autor_moze_afiliowac=True
    )
    jednostka.rodzaj = rodzaj
    jednostka.save()
    assert jednostka.przyjmuje_afiliacje() is True
