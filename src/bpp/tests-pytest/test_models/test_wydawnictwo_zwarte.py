# -*- encoding: utf-8 -*-

from lxml.etree import Element


def test_serializuj_pbn_zwarte(wydawnictwo_zwarte_z_autorem, wydzial):
    wydawnictwo_zwarte_z_autorem.eksport_pbn_serializuj(wydzial)


def test_liczba_arkuszy_wydawniczych(wydawnictwo_zwarte_z_autorem):
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 41000
    assert wydawnictwo_zwarte_z_autorem.liczba_arkuszy_wydawniczych() == "1.02"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 39000
    assert wydawnictwo_zwarte_z_autorem.liczba_arkuszy_wydawniczych() == "0.97"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 60000
    assert wydawnictwo_zwarte_z_autorem.liczba_arkuszy_wydawniczych() == "1.50"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 20000
    assert wydawnictwo_zwarte_z_autorem.liczba_arkuszy_wydawniczych() == "0.50"


def test_eksport_pbn_size(wydawnictwo_zwarte_z_autorem):
    """
    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    """
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 20000
    toplevel = Element("fa")
    wydawnictwo_zwarte_z_autorem.eksport_pbn_size(toplevel)
    assert toplevel.getchildren()[0].text == "0.50"
