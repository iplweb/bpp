# -*- encoding: utf-8 -*-

import pytest
from lxml.etree import Element
from model_mommy import mommy

from bpp.models import Wydawnictwo_Zwarte_Autor
from bpp.models.autor import Autor
from bpp.models.struktura import Wydzial, Jednostka, Uczelnia
from bpp.models.system import Typ_Odpowiedzialnosci, Charakter_Formalny
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

@pytest.mark.django_db
def test_serializuj_pbn_zwarte(wydawnictwo_zwarte_z_autorem, wydzial):
    wydawnictwo_zwarte_z_autorem.eksport_pbn_serializuj(wydzial)


@pytest.mark.django_db
def test_liczba_arkuszy_wydawniczych(wydawnictwo_zwarte_z_autorem):
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 41000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "1.02"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 39000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "0.97"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 60000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "1.50"

    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 20000
    assert wydawnictwo_zwarte_z_autorem.wymiar_wydawniczy_w_arkuszach() == "0.50"


@pytest.mark.django_db
def test_eksport_pbn_size(wydawnictwo_zwarte_z_autorem):
    """
    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    """
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 20000
    toplevel = Element("fa")
    wydawnictwo_zwarte_z_autorem.eksport_pbn_size(toplevel)
    assert toplevel.getchildren()[0].text == "0.50"


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_autorow(
        charaktery_formalne, typy_odpowiedzialnosci):
    """

    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    :return:
    """

    u = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u)
    w2 = mommy.make(Wydzial, uczelnia=u)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2 = mommy.make(Autor, imiona="Stefan", nazwisko="Nowak")

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=u)

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")

    wz_root = mommy.make(Wydawnictwo_Zwarte, charakter_formalny=chf_ksp, szczegoly="s. 123",
                         calkowita_liczba_autorow=50)
    wz_child1 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wz_root, charakter_formalny=chf_roz,
                           szczegoly="s. 10-15")
    wz_child2 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wz_root, charakter_formalny=chf_roz,
                           szczegoly="s. 16-25")

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    wz_child1.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    wz_child2.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    ret = wz_root.eksport_pbn_serializuj(w1)

    assert len(ret.findall("editor")) == 1
    assert ret.find("other-editors").text == "1"

    assert len(ret.findall("author")) == 1
    assert ret.find("other-contributors").text == "49"


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_redaktorow(
        charaktery_formalne, typy_odpowiedzialnosci):
    """

    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    :return:
    """

    u = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u)
    w2 = mommy.make(Wydzial, uczelnia=u)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2 = mommy.make(Autor, imiona="Stefan", nazwisko="Nowak")

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=u)

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")

    wz_root = mommy.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=chf_ksp,
        szczegoly="s. 123",
        calkowita_liczba_redaktorow=50)

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    ret = wz_root.eksport_pbn_serializuj(w1)

    assert len(ret.findall("editor")) == 1
    assert ret.find("other-editors").text == "49"


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_autorow_trzech(
        standard_data):
    """

    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    :return:
    """

    u = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u)
    w2 = mommy.make(Wydzial, uczelnia=u)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2 = mommy.make(Autor, imiona="Stefan", nazwisko="Nowak")
    a3 = mommy.make(Autor, imiona="Joe", nazwisko="Moore")

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=u)

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")

    wz_root = mommy.make(Wydawnictwo_Zwarte, charakter_formalny=chf_ksp, szczegoly="s. 123",
                         calkowita_liczba_autorow=50)
    wz_child1 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wz_root, charakter_formalny=chf_roz,
                           szczegoly="s. 10-15")
    wz_child2 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wz_root, charakter_formalny=chf_roz,
                           szczegoly="s. 16-25")

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    wz_child1.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a3, j1, typ_odpowiedzialnosci_skrot="aut.")

    wz_child2.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    ret = wz_root.eksport_pbn_serializuj(w1)

    assert len(ret.findall("editor")) == 1
    assert ret.find("other-editors").text == "1"

    assert len(ret.findall("author")) == 2
    assert ret.find("other-contributors").text == "48"

@pytest.mark.django_db
def test_eksport_pbn_publication_place(wydawnictwo_zwarte):
    wydawnictwo_zwarte.miejsce_i_rok = "Lublin 1993"
    toplevel = Element("a")
    wydawnictwo_zwarte.eksport_pbn_publication_place(toplevel)
    assert toplevel.getchildren()[0].text == "Lublin"

    wydawnictwo_zwarte.miejsce_i_rok = "   Lublin 1993   "
    toplevel = Element("a")
    wydawnictwo_zwarte.eksport_pbn_publication_place(toplevel)
    assert toplevel.getchildren()[0].text == "Lublin"

    wydawnictwo_zwarte.miejsce_i_rok = "Berlin Heidelberg 2015"
    toplevel = Element("a")
    wydawnictwo_zwarte.eksport_pbn_publication_place(toplevel)
    assert toplevel.getchildren()[0].text == "Berlin Heidelberg"


@pytest.mark.django_db
def test_eksport_pbn_book_bug(wydawnictwo_zwarte, wydzial):
    wydawnictwo_zwarte.informacje = "Tu nie będzie wu i dwukropka"
    wydawnictwo_zwarte.save()

    toplevel = Element("foo")
    wydawnictwo_zwarte.eksport_pbn_book(toplevel, wydzial)
    # przeszło

    wydawnictwo_zwarte.informacje = "W: foobar"
    wydawnictwo_zwarte.save()

    toplevel = Element("foo")
    wydawnictwo_zwarte.eksport_pbn_book(toplevel, wydzial)
    assert toplevel.getchildren()[0].getchildren()[0].text == "foobar"


@pytest.mark.django_db
def test_generowanie_opisu_bibliograficznego_informacje_wydawnictwo_nadrzedne():
    wz1 = mommy.make(Wydawnictwo_Zwarte,
                     tytul_oryginalny="Pięćset")
    wz2 = mommy.make(Wydawnictwo_Zwarte,
                     tytul_oryginalny="Plus")

    wz1.informacje = "To sie ma pojawic"
    wz1.wydawnictwo_nadrzedne = wz2
    wz1.save()
    wz1.zaktualizuj_cache()
    assert "To sie ma pojawic" in wz1.opis_bibliograficzny_cache

    wz1.informacje = ""
    wz1.wydawnictwo_nadrzedne = wz2
    wz1.save()
    wz1.zaktualizuj_cache()
    assert "Pięćset" in wz1.opis_bibliograficzny_cache
    assert "W: Plus" in wz1.opis_bibliograficzny_cache

    wz1.informacje = ""
    wz1.wydawnictwo_nadrzedne = None
    wz1.save()
    wz1.zaktualizuj_cache()
    assert "Pięćset" in wz1.opis_bibliograficzny_cache
    assert "Plus" not in wz1.opis_bibliograficzny_cache


@pytest.mark.djagno_db
def test_eksport_pbn_get_wszyscy_autorzy_iter(wydzial, jednostka, typ_odpowiedzialnosci_autor):
    nadrzedne = mommy.make(
        Wydawnictwo_Zwarte,
        charakter_formalny__ksiazka_pbn=True
    )

    podrzedne1 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne1.dodaj_autora(
        mommy.make(Autor),
        jednostka=jednostka,
        zapisany_jako="Foo Bar"
    )

    podrzedne2 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne2.dodaj_autora(
        mommy.make(Autor),
        jednostka=jednostka,
        zapisany_jako="Foo Bar 2"
    )

    podrzedne3 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne3.dodaj_autora(
        mommy.make(Autor),
        jednostka=jednostka,
        zapisany_jako="Foo Bar 3"
    )

    res = list(
        nadrzedne.eksport_pbn_get_wszyscy_autorzy_iter(
            wydzial, Wydawnictwo_Zwarte_Autor)
    )
    assert len(res) == 3



