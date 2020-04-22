# -*- encoding: utf-8 -*-

import pytest
from lxml.etree import Element
from model_mommy import mommy

from bpp.models import Wydawnictwo_Zwarte_Autor, const
from bpp.models.autor import Autor
from bpp.models.struktura import Jednostka, Uczelnia, Wydzial
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_serializuj_pbn_zwarte(wydawnictwo_zwarte_z_autorem):
    wydawnictwo_zwarte_z_autorem.eksport_pbn_serializuj()


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
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_autorow(
    charaktery_formalne, typy_odpowiedzialnosci
):
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
        calkowita_liczba_autorow=50,
    )
    wz_child1 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 10-15",
    )
    wz_child2 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 16-25",
    )

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    wz_child1.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    wz_child2.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    ret = wz_root.eksport_pbn_serializuj()

    assert len(ret.findall("editor")) == 2

    assert (
        len(ret.findall("author")) == 0
    )  # nie eksportuj autorów dla książek redaktorskich


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_redaktorow(
    charaktery_formalne, typy_odpowiedzialnosci
):
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
        calkowita_liczba_redaktorow=50,
    )

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    ret = wz_root.eksport_pbn_serializuj()

    assert len(ret.findall("editor")) == 2


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_autorow_trzech(standard_data):
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

    wz_root = mommy.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=chf_ksp,
        szczegoly="s. 123",
        calkowita_liczba_autorow=50,
    )
    wz_child1 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 10-15",
    )
    wz_child2 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 16-25",
    )

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="red.")

    wz_child1.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a3, j1, typ_odpowiedzialnosci_skrot="aut.")

    wz_child2.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    ret = wz_root.eksport_pbn_serializuj()

    assert len(ret.findall("editor")) == 2

    assert len(ret.findall("author")) == 0


@pytest.mark.django_db
def test_eksport_pbn_wydawnictwo_nadrzedne_liczba_autorow_ksiazka_nie_redaktorska_trzech(
    standard_data,
):
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

    wz_root = mommy.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=chf_ksp,
        szczegoly="s. 123",
        calkowita_liczba_autorow=50,
    )
    wz_child1 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 10-15",
    )
    wz_child2 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 16-25",
    )

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_root.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    wz_child1.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")
    wz_child1.dodaj_autora(a3, j1, typ_odpowiedzialnosci_skrot="aut.")

    wz_child2.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")

    ret = wz_root.eksport_pbn_serializuj()

    assert len(ret.findall("author")) == 3


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
    wz1 = mommy.make(Wydawnictwo_Zwarte, tytul_oryginalny="Pięćset")
    wz2 = mommy.make(Wydawnictwo_Zwarte, tytul_oryginalny="Plus")

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
def test_eksport_pbn_get_wszyscy_autorzy_iter(
    wydzial, jednostka, typ_odpowiedzialnosci_autor
):
    nadrzedne = mommy.make(
        Wydawnictwo_Zwarte, charakter_formalny__rodzaj_pbn=const.RODZAJ_PBN_KSIAZKA
    )

    podrzedne1 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne1.dodaj_autora(
        mommy.make(Autor), jednostka=jednostka, zapisany_jako="Foo Bar"
    )

    podrzedne2 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne2.dodaj_autora(
        mommy.make(Autor), jednostka=jednostka, zapisany_jako="Foo Bar 2"
    )

    podrzedne3 = mommy.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=nadrzedne)
    podrzedne3.dodaj_autora(
        mommy.make(Autor), jednostka=jednostka, zapisany_jako="Foo Bar 3"
    )

    res = list(nadrzedne.eksport_pbn_get_wszyscy_autorzy_iter(Wydawnictwo_Zwarte_Autor))
    assert len(res) == 3


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_wydawnictwo_property(wydawnictwo_zwarte, wydawca):
    wydawnictwo_zwarte.wydawca = None
    wydawnictwo_zwarte.wydawca_opis = "123"
    assert wydawnictwo_zwarte.wydawnictwo == "123"

    wydawnictwo_zwarte.wydawca = wydawca
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy 123"

    wydawnictwo_zwarte.wydawca_opis = ". Lol"
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy. Lol"

    wydawnictwo_zwarte.wydawca_opis = None
    assert wydawnictwo_zwarte.wydawnictwo == "Wydawca Testowy"


@pytest.mark.django_db
def test_wydawnictwo_zwarte_is_pod_redakcja(
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
    jednostka,
):
    for elem in autor_jan_kowalski, autor_jan_nowak:
        wza = wydawnictwo_zwarte.dodaj_autora(
            elem, jednostka, typ_odpowiedzialnosci_skrot="red."
        )
    assert wydawnictwo_zwarte.is_pod_redakcja()

    wza.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")
    wza.save()

    assert not wydawnictwo_zwarte.is_pod_redakcja()


@pytest.mark.django_db
def test_wydawnictwo_zwarte_book_with_chapters_nie_redakcyjna(
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jednostka,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.charakter_formalny = charaktery_formalne["KSP"]
    wydawnictwo_zwarte.save()

    toplevel = Element("a")
    wydawnictwo_zwarte.eksport_pbn_book_with_chapters(toplevel)
    assert list(toplevel.getchildren())[0].text == "false"


@pytest.mark.django_db
def test_wydawnictwo_zwarte_book_with_chapters_redakcyjna(
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jednostka,
):
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red."
    )
    wydawnictwo_zwarte.charakter_formalny = charaktery_formalne["KSP"]
    wydawnictwo_zwarte.save()

    toplevel = Element("a")
    wydawnictwo_zwarte.eksport_pbn_book_with_chapters(toplevel)
    assert list(toplevel.getchildren())[0].text == "true"
