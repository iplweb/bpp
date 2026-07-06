import pytest


@pytest.mark.django_db
def test_struktura_menu_domyslne_etykiety():
    from django_bpp.menu import STRUKTURA_MENU

    assert str(STRUKTURA_MENU[0][0]) == "Uczelnia"
    assert str(STRUKTURA_MENU[1][0]) == "Wydziały"
    assert str(STRUKTURA_MENU[2][0]) == "Jednostki"


@pytest.mark.django_db
def test_struktura_menu_po_przemianowaniu():
    from bpp.models import Rzeczownik
    from django_bpp.menu import STRUKTURA_MENU

    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    assert str(STRUKTURA_MENU[2][0]) == "Działy"
