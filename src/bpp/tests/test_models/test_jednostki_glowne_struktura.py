"""#438: predykaty struktury drzewa jednostek dla filtra „Jednostka nadrzędna".

Uczelnia bez wydziałów, ale ze strukturą (jednostka-korzeń + podjednostki),
dostaje w multiseeku odpowiednik filtra „Wydział" pod neutralną etykietą
„Jednostka nadrzędna". Te dwa predykaty decydują, czy taka struktura istnieje:
``Jednostka.ma_poddrzewo`` (czy TEN korzeń ma poddrzewo) oraz
``Uczelnia.ma_jednostki_glowne_z_podjednostkami`` (czy ISTNIEJE jakikolwiek
korzeń z podjednostkami w tej uczelni).
"""

import pytest

from bpp.tests.util import any_jednostka


@pytest.mark.django_db
def test_jednostka_ma_poddrzewo_korzen_z_podjednostka(uczelnia):
    korzen = any_jednostka(
        nazwa="Korzeń A", uczelnia=uczelnia, wydzial=None, parent=None
    )
    any_jednostka(
        nazwa="Podjednostka A", uczelnia=uczelnia, wydzial=None, parent=korzen
    )
    assert korzen.ma_poddrzewo() is True


@pytest.mark.django_db
def test_jednostka_ma_poddrzewo_korzen_bez_podjednostek(uczelnia):
    korzen = any_jednostka(
        nazwa="Korzeń-liść", uczelnia=uczelnia, wydzial=None, parent=None
    )
    assert korzen.ma_poddrzewo() is False


@pytest.mark.django_db
def test_uczelnia_ma_jednostki_glowne_z_podjednostkami_prawda(uczelnia):
    korzen = any_jednostka(
        nazwa="Korzeń U", uczelnia=uczelnia, wydzial=None, parent=None
    )
    any_jednostka(
        nazwa="Podjednostka U", uczelnia=uczelnia, wydzial=None, parent=korzen
    )
    assert uczelnia.ma_jednostki_glowne_z_podjednostkami() is True


@pytest.mark.django_db
def test_uczelnia_ma_jednostki_glowne_z_podjednostkami_plaska_struktura(uczelnia):
    # Sama płaska lista korzeni (bez podjednostek) → brak poddrzewa,
    # filtr „Jednostka nadrzędna" byłby bezużyteczny.
    any_jednostka(nazwa="Korzeń 1", uczelnia=uczelnia, wydzial=None, parent=None)
    any_jednostka(nazwa="Korzeń 2", uczelnia=uczelnia, wydzial=None, parent=None)
    assert uczelnia.ma_jednostki_glowne_z_podjednostkami() is False
