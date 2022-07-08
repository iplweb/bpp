from datetime import date

from django.test import TestCase
from model_bakery import baker

from bpp.imports.egeria_2012 import (
    dopasuj_autora,
    dopasuj_jednostke,
    importuj_wiersz,
    mangle_labels,
    znajdz_lub_zrob_stanowisko,
)
from bpp.imports.uml import UML_Egeria_2012_Mangle
from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora
from bpp.tests.util import any_jednostka


class _x:
    def __init__(self, value):
        self.value = value


class TestImports(TestCase):
    def test_mangle_labels(self):
        a = [
            "foo",
            "bar",
            "baz",
            "quux",
            "Stanowisko",
            "foo",
            "bar",
            "quux",
            "Stanowisko",
            "Wydzial ",
            "Stanowisko",
            "Wydzial ",
            "Stanowisko",
            "Wydzial",
        ]

        b = [
            "foo",
            "bar",
            "baz",
            "quux",
            "Stanowisko",
            "foo",
            "bar",
            "quux",
            "Stanowisko_2009",
            "Wydzial_2009",
            "Stanowisko_2010",
            "Wydzial_2010",
            "Stanowisko_2011",
            "Wydzial_2011",
        ]

        self.assertEqual(mangle_labels(a), b)

    def test_znajdz_lub_zrob_stanowisko(self):
        f = znajdz_lub_zrob_stanowisko("Kucharz")
        self.assertEqual(f.nazwa, "Kucharz")
        f1 = znajdz_lub_zrob_stanowisko("Kucharz")
        self.assertEqual(f1, f)

    def test_dopasuj_jednostke(self):
        mangle = UML_Egeria_2012_Mangle
        j1 = any_jednostka(nazwa="Foo")
        j2 = any_jednostka(  # noqa
            nazwa="Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz"
        )
        j3 = any_jednostka(
            nazwa="Katedra i Klinika Ginekologii i Endokrynologii Ginekologicznej"
        )
        j4 = any_jednostka(nazwa="I Katedra i Klinika Ginekologii")
        j5 = any_jednostka(nazwa="II Katedra i Klinika Ginekologii")  # noqa

        self.assertEqual(
            dopasuj_jednostke(
                "Katedra i Klinika Ginekologii i Endokrynologii Ginekolog.", mangle
            ),
            j3,
        )

        self.assertEqual(dopasuj_jednostke("Foo", mangle), j1)

        self.assertEqual(
            dopasuj_jednostke(
                "Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz", mangle
            ),
            None,
        )

        self.assertEqual(
            dopasuj_jednostke("I Katedra i Klinika Ginekologii", mangle), j4
        )

    def test_dopasuj_autora(self):
        a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
        a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
        a3 = baker.make(Autor, imiona="Jan", nazwisko="Unikalny")

        j1 = any_jednostka()
        j2 = any_jednostka()
        f1 = baker.make(Funkcja_Autora, nazwa="Kucharz")

        Autor_Jednostka.objects.create(autor=a1, jednostka=j1, funkcja=f1)

        Autor_Jednostka.objects.create(autor=a2, jednostka=j2, funkcja=f1)

        self.assertEqual(dopasuj_autora("Jan", "Unikalny", None, None), a3)

        self.assertEqual(dopasuj_autora("Jan", "Kowalski", j1.nazwa, f1), a1)

        self.assertEqual(dopasuj_autora("Jan", "Kowalski", j2.nazwa, f1), a2)

    def test_importuj_wiersz(self):
        a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
        j1 = any_jednostka(nazwa="Foo")

        importuj_wiersz(
            "Jan", "Kowalski", "Foo", "Kucharz", 2012, UML_Egeria_2012_Mangle
        )
        self.assertEqual(
            Autor_Jednostka.objects.get(autor=a1, jednostka=j1).zakonczyl_prace,
            date(2012, 12, 31),
        )

    # def test_importuj_sheet_roczny(self):
    #     a1 = baker.make(Autor, imiona='Jan', nazwisko='Kowalski')
    #     j1 = any_jednostka(nazwa='Foo')
    #
    #     with Mock() as sheet:
    #         sheet.row(0) >> [_x('Stanowisko'), _x('PRC IMIE'), _x('PRC NAZWISKO'), _x('OB_NAZWA')]
    #         sheet.nrows >> 1
    #         sheet.row(1) >> [_x('Kucharz'), _x('Jan'), _x('Kowalski'), _x(u'Zakład')]
    #
    #     importuj_sheet_roczny(sheet, 2012, UML_Egeria_2012_Mangle)
    #
    # def test_importuj_sheet_osoby_nie_ujete(self):
    #     w1 = any_wydzial(nazwa='Wydział Kucharski')
    #     a1 = any_autor(imiona='Jan', nazwisko='Kowalski')
    #     j1 = any_jednostka(nazwa=u'Zakład', wydzial=w1)
    #
    #     with Mock() as sheet:
    #         sheet.row(2) >> [_x("NUMER"), _x("PRC IMIE"), _x("PRC NAZWISKO"), _x("OB_NAZWA"),
    #                          _x("Stanowisko"), _x("WYMIAR ETATU"),
    #                          _x('stanowisko'), _x(u'stopień'), _x(u'Wydział'),
    #                          _x('stanowisko'), _x(u'stopień'), _x(u'Wydział'),
    #                          _x('stanowisko'), _x(u'stopień'), _x(u'Wydział'),
    #                          _x('stanowisko'), _x(u'stopień'), _x(u'Wydział')]
    #         sheet.nrows >> 4
    #         sheet.row(3) >> [_x('123'), _x('Jan'), _x('Kowalski'), _x(u'Zakład'),
    #                          _x('Kucharz'), _x('Pełny'),
    #                          _x('#N/D!'), _x('#N/D!'), _x('#N/D!'),
    #                          _x('Sternik'), _x(u'Młodzszy'), _x(u'Tego wydziału nie ma'),
    #                          _x("Kucharz"), _x('Starszy'), _x(u'Wydział Kucharski'),
    #                          _x("Kucharz"), _x('Starszy'), _x(u'Wydział Kucharski'),
    #                          ]
    #
    #     importuj_sheet_osoby_nie_ujete(sheet, UML_Egeria_2012_Mangle)
    #
    #     l = list(Opi_2012_Afiliacja_Do_Wydzialu.objects.all().order_by('rok'))
    #     self.assertEquals(len(l), 2)
    #     self.assertEquals(l[0].autor, a1)
    #     self.assertEquals(l[0].wydzial, w1)
    #     self.assertEquals(l[0].rok, 2011)
    #


#
# class TestImportujImiona(TestCase):
#
#
#     def test_importuj_imiona(self):
#
#         with Mock() as sheet:
#             sheet.nrows >> 3
#             sheet.row(0) >> [_x(a) for a in ['0', 'dr', 'Jan Maria', 'Kowalski', 'nie']]
#             sheet.row(1) >> [_x(a) for a in ['0', 'dr', 'Jan Maria', 'Nowak', 'nie']]
#             sheet.row(2) >> [_x(a) for a in ['0', 'dr', 'Jan Maria', 'Strzelec', 'nie']]
#
#         wydzial = any_wydzial()
#         wydzial2 = any_wydzial()
#
#         jednostka = any_jednostka(wydzial=wydzial)
#         jednostka2 = any_jednostka(wydzial=wydzial2)
#
#         autor = baker.make(Autor, nazwisko='Kowalski', imiona='Jan')
#         Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor)
#
#         autor2 = baker.make(Autor, nazwisko='Nowak', imiona='Jan')
#         Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor2)
#
#         autor3 = baker.make(Autor, nazwisko='Nowak', imiona='Jan')
#         Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor3)
#
#         autor4 = baker.make(Autor, nazwisko='Strzelec', imiona='Jan')
#         Autor_Jednostka.objects.create(jednostka=jednostka, autor=autor4)
#
#         autor5 = baker.make(Autor, nazwisko='Strzelec', imiona='Jan')
#         Autor_Jednostka.objects.create(jednostka=jednostka2, autor=autor5)
#
#         importuj_imiona_sheet(sheet, wydzial)
#
#         autor = Autor.objects.get(pk=autor.pk)
#         self.assertEquals(autor.imiona, 'Jan Maria')
#
#         # A u tych dwóch nic się nie zmieni...
#         autor = Autor.objects.get(pk=autor2.pk)
#         self.assertEquals(autor.imiona, 'Jan')
#         autor = Autor.objects.get(pk=autor3.pk)
#         self.assertEquals(autor.imiona, 'Jan')
#
#         # A u tego się zmieni tylko ten który jest w Wydziale Lekarskim
#         autor = Autor.objects.get(pk=autor4.pk)
#         self.assertEquals(autor.imiona, 'Jan Maria')
#         autor = Autor.objects.get(pk=autor5.pk)
#         self.assertEquals(autor.imiona, 'Jan')
