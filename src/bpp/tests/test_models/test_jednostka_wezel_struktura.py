"""Faza B (#438), III-2: metody węzła strukturalnego browse na ``Jednostka``.

Zastępują dawne ``Wydzial.jednostki/aktualne_jednostki/kola_naukowe/
historyczne_jednostki`` (patrz ``test_wydzial.py``) -- ale działają na
WĘŹLE (bezpośrednie dzieci przez ``get_children()``/``Jednostka_Rodzic``
z ``parent=self``), a nie przez denorm ``legacy_wydzial_id`` obejmujący
całe poddrzewo wydziału.
"""

from datetime import timedelta

import pytest

from bpp.models import Jednostka_Rodzic, RodzajJednostki
from bpp.tests.util import any_jednostka


@pytest.fixture
def wezel(uczelnia, db):
    """Węzeł-korzeń w stylu strukturalnym (rodzaj "Wydział")."""
    rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    return any_jednostka(
        nazwa="Węzeł strukturalny",
        skrot="WZS",
        uczelnia=uczelnia,
        wydzial=None,
        parent=None,
        rodzaj=rodzaj,
    )


def _dziecko(wezel, uczelnia, **kw):
    return any_jednostka(uczelnia=uczelnia, wydzial=None, parent=wezel, **kw)


@pytest.mark.django_db
def test_Jednostka_aktualne_podjednostki(wezel, uczelnia):
    dziecko = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True)
    assert dziecko in wezel.aktualne_podjednostki()
    assert dziecko not in wezel.historyczne_podjednostki()
    assert dziecko not in wezel.kola_naukowe()


@pytest.mark.django_db
def test_Jednostka_aktualne_podjednostki_wyklucza_niewidoczne(wezel, uczelnia):
    dziecko = _dziecko(wezel, uczelnia, aktualna=True, widoczna=False)
    assert dziecko not in wezel.aktualne_podjednostki()


@pytest.mark.django_db
def test_Jednostka_aktualne_podjednostki_wyklucza_kola(wezel, uczelnia):
    kolo_rodzaj = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    kolo = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True, rodzaj=kolo_rodzaj)
    assert kolo not in wezel.aktualne_podjednostki()


@pytest.mark.django_db
def test_Jednostka_historyczne_podjednostki(wezel, uczelnia, yesterday):
    dziecko = _dziecko(wezel, uczelnia, aktualna=False, widoczna=True)
    Jednostka_Rodzic.objects.create(
        parent=wezel,
        jednostka=dziecko,
        od=yesterday - timedelta(days=50),
        do=yesterday - timedelta(days=5),
    )
    assert dziecko not in wezel.aktualne_podjednostki()
    assert dziecko in wezel.historyczne_podjednostki()
    assert dziecko not in wezel.kola_naukowe()


@pytest.mark.django_db
def test_Jednostka_kola_naukowe(wezel, uczelnia):
    kolo_rodzaj = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    kolo = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True, rodzaj=kolo_rodzaj)
    assert kolo in wezel.kola_naukowe()
    assert kolo not in wezel.aktualne_podjednostki()
    assert kolo not in wezel.historyczne_podjednostki()


@pytest.mark.django_db
def test_Jednostka_kola_naukowe_wyklucza_niewidoczne(wezel, uczelnia):
    kolo_rodzaj = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    kolo = _dziecko(wezel, uczelnia, aktualna=True, widoczna=False, rodzaj=kolo_rodzaj)
    assert kolo not in wezel.kola_naukowe()


@pytest.mark.django_db
def test_Jednostka_wymaga_nawigacji_falszywe_gdy_pusto(wezel):
    assert wezel.wymaga_nawigacji() is False


@pytest.mark.django_db
def test_Jednostka_wymaga_nawigacji_prawdziwe_gdy_dwie_kategorie(wezel, uczelnia):
    _dziecko(wezel, uczelnia, aktualna=True, widoczna=True)
    kolo_rodzaj = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    _dziecko(wezel, uczelnia, aktualna=True, widoczna=True, rodzaj=kolo_rodzaj)

    assert wezel.wymaga_nawigacji() is True


@pytest.mark.django_db
def test_Jednostka_historyczne_podjednostki_nie_liczy_wnukow(
    wezel, uczelnia, yesterday
):
    """Historyczne podjednostki to WYŁĄCZNIE bezpośrednie dzieci węzła --
    metryczka wnuka (dziecko dziecka) nie powinna być tu widoczna."""
    dziecko = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True)
    wnuk = any_jednostka(
        uczelnia=uczelnia, wydzial=None, parent=dziecko, aktualna=False, widoczna=True
    )
    Jednostka_Rodzic.objects.create(
        parent=dziecko,
        jednostka=wnuk,
        od=yesterday - timedelta(days=50),
        do=yesterday - timedelta(days=5),
    )

    assert wnuk not in wezel.historyczne_podjednostki()
