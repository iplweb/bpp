"""Faza B (#438): metody węzła strukturalnego browse na ``Jednostka``.

Zastępują dawne ``Wydzial.jednostki/aktualne_jednostki/kola_naukowe/
historyczne_jednostki`` (patrz ``test_wydzial.py``) i -- po naprawie regresji
III-2 -- odwzorowują ich SEMANTYKĘ PODDRZEWA: wierny port operuje na denorm
``wydzial`` (self-FK do KORZENIA drzewa) oraz na metryczce ``Jednostka_Rodzic``
z rodzicem w poddrzewie, więc obejmuje potomków GŁĘBSZYCH niż bezpośrednie
dzieci (wnuki, prawnuki itd.). III-2 zwężał to omyłkowo do ``get_children()``
(tylko bezpośrednie dzieci) -> pusta strona wydziału.
"""

from datetime import timedelta

import pytest

from bpp.models import Jednostka, Jednostka_Rodzic, RodzajJednostki
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
def test_Jednostka_historyczne_podjednostki_liczy_wnukow_z_poddrzewa(
    wezel, uczelnia, yesterday
):
    """SEMANTYKA PODDRZEWA (naprawa regresji III-2): historyczna metryczka
    WNUKA (dziecko dziecka) -- którego rodzic leży w poddrzewie węzła --
    JEST widoczna w ``historyczne_podjednostki`` węzła-korzenia. Dawniej
    (get_children) wnuk był tu pominięty -> strona wydziału gubiła historię
    z głębszych poziomów."""
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

    assert wnuk in wezel.historyczne_podjednostki()


@pytest.mark.django_db
def test_Jednostka_aktualne_podjednostki_liczy_cale_poddrzewo(wezel, uczelnia):
    """Głęboka struktura (wydział -> instytut -> katedra): strona wydziału
    (węzeł-korzeń) pokazuje WSZYSTKIE aktualne, widoczne jednostki potomne,
    nie tylko bezpośrednie dzieci. To sedno naprawy issue 1 (#438)."""
    instytut = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True)
    katedra = any_jednostka(
        uczelnia=uczelnia, wydzial=None, parent=instytut, aktualna=True, widoczna=True
    )

    aktualne = wezel.aktualne_podjednostki()
    assert instytut in aktualne
    assert katedra in aktualne


@pytest.mark.django_db
def test_Jednostka_podjednostki_dzialaja_dla_niekorzenia(wezel, uczelnia):
    """Regresja (#438): metody strukturalne muszą działać także dla węzła
    NIE-korzenia. Dotąd ``wydzial=self`` łapało tylko korzeń, więc „Instytut"
    z rodzajem ``pokazuj_strukture_podjednostek`` renderował PUSTĄ stronę mimo
    katedr. Teraz nie-korzeń używa MPTT ``get_descendants``."""
    instytut = _dziecko(wezel, uczelnia, aktualna=True, widoczna=True)
    katedra = any_jednostka(
        uczelnia=uczelnia,
        wydzial=None,
        parent=instytut,
        aktualna=True,
        widoczna=True,
    )

    # ``self`` musi być świeży (jak w widoku DetailView) -- lft/rght instytutu
    # zmieniły się w bazie po wstawieniu katedry.
    instytut = Jednostka.objects.get(pk=instytut.pk)

    assert katedra in instytut.aktualne_podjednostki()
    # a poddrzewo instytutu NIE zawiera samego instytutu ani rodzeństwa wyżej
    assert instytut not in instytut.aktualne_podjednostki()
