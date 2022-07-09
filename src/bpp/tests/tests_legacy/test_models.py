from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from model_bakery import baker

from bpp.models import (
    Autor,
    Jezyk,
    Patent,
    Plec,
    Punktacja_Zrodla,
    Redakcja_Zrodla,
    Typ_Odpowiedzialnosci,
    Tytul,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)
from bpp.models.autor import Autor_Jednostka, Funkcja_Autora
from bpp.models.system import Charakter_Formalny
from bpp.tests.util import (
    any_autor,
    any_ciagle,
    any_jednostka,
    any_uczelnia,
    any_wydzial,
    any_zwarte,
)


class TestNazwaISkrot(TestCase):
    def test_skrot(self):
        a = Charakter_Formalny(nazwa="foo", skrot="bar")
        self.assertEqual("foo", str(a))


class TestTytul(TestCase):
    def test_tytul(self):
        t = baker.make(Tytul)
        str(t)


class TestWydzial(TestCase):
    def test_wydzial(self):
        u = any_uczelnia()
        w = any_wydzial(nazwa="Lekarski", uczelnia=u)
        self.assertEqual(str(w), "Lekarski")


class TestJednostka(TestCase):
    def setUp(self):
        Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
        Funkcja_Autora.objects.get_or_create(nazwa="kierownik", skrot="kier.")

    def test_jednostka(self):
        any_wydzial(skrot="BAR")
        j = any_jednostka(nazwa="foo", wydzial_skrot="BAR")
        self.assertEqual(str(j), "foo (BAR)")

    def test_obecni_autorzy(self):
        j1 = any_jednostka()

        a1 = baker.make(Autor)
        a2 = baker.make(Autor)
        a3 = baker.make(Autor)

        j1.dodaj_autora(a1, rozpoczal_prace=date(2012, 1, 1))
        j1.dodaj_autora(a2, zakonczyl_prace=date(2012, 12, 31))
        j1.dodaj_autora(a3)

        obecni = j1.obecni_autorzy()

        self.assertIn(a1, obecni)
        self.assertNotIn(a2, obecni)
        self.assertIn(a3, obecni)

    def test_kierownik(self):
        j1 = any_jednostka()
        self.assertEqual(j1.kierownik(), None)

        a1 = baker.make(Autor)
        j1.dodaj_autora(a1, funkcja=Funkcja_Autora.objects.get(nazwa="kierownik"))

        self.assertEqual(j1.kierownik(), a1)

    def test_prace_w_latach(self):
        j1 = any_jednostka()

        a1 = baker.make(Autor)

        wc = any_ciagle(rok=2012)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wc,
            autor=a1,
            jednostka=j1,
            typ_odpowiedzialnosci=baker.make(Typ_Odpowiedzialnosci),
        )

        wc = any_ciagle(rok=2013)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wc,
            autor=a1,
            jednostka=j1,
            typ_odpowiedzialnosci=baker.make(Typ_Odpowiedzialnosci),
        )

        self.assertEqual(list(j1.prace_w_latach()), [2012, 2013])


class TestAutor(TestCase):
    # fixtures = ['charakter_formalny.json', 'tytul.json',
    #             'typ_odpowiedzialnosci.json']

    def test_autor(self):
        j = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)
        self.assertEqual(str(j), "Lol Omg")

        t = Tytul.objects.create(nazwa="daktur", skrot="dar")
        j = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=t)
        self.assertEqual(str(j), "Lol Omg, dar")

        j.poprzednie_nazwiska = "Kowalski"
        self.assertEqual(str(j), "Lol Omg (Kowalski), dar")

        self.assertEqual(j.get_full_name(), "Omg Lol (Kowalski)")
        self.assertEqual(j.get_full_name_surname_first(), "Lol (Kowalski) Omg")

    def test_afiliacja_na_rok(self):
        w = any_wydzial()
        n = any_wydzial(skrot="w2", nazwa="w2")
        j = any_jednostka(wydzial=w)
        a = baker.make(Autor)

        aj = Autor_Jednostka.objects.create(
            autor=a, jednostka=j, funkcja=baker.make(Funkcja_Autora)
        )

        self.assertEqual(a.afiliacja_na_rok(2030, w), None)
        self.assertEqual(a.afiliacja_na_rok(2030, n), None)

        aj.rozpoczal_prace = date(2012, 1, 1)
        aj.save()

        self.assertEqual(a.afiliacja_na_rok(2030, w), True)
        self.assertEqual(a.afiliacja_na_rok(2011, w), None)
        self.assertEqual(a.afiliacja_na_rok(2030, n), None)

        aj.zakonczyl_prace = date(2013, 12, 31)
        aj.save()

        self.assertEqual(a.afiliacja_na_rok(2030, w), None)
        self.assertEqual(a.afiliacja_na_rok(2011, w), None)
        self.assertEqual(a.afiliacja_na_rok(2012, w), True)
        self.assertEqual(a.afiliacja_na_rok(2030, n), None)

    def test_dodaj_jednostke(self):
        f = baker.make(Funkcja_Autora)
        a = baker.make(Autor, imiona="Foo", nazwisko="Bar", tytul=None)
        w = any_wydzial(nazwa="WL", skrot="WL")
        w2 = any_wydzial(nazwa="XX", skrot="YY")
        j = any_jednostka(wydzial=w)
        j2 = any_jednostka(wydzial=w2)

        def ma_byc(ile=1):
            self.assertEqual(Autor_Jednostka.objects.count(), ile)

        a.dodaj_jednostke(j, 1912, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 1913, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 1914, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 1913, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 1920, f)
        ma_byc(2)

        a.dodaj_jednostke(j, 1921, f)
        ma_byc(2)

        a.dodaj_jednostke(j, 1960, f)
        ma_byc(3)

        lx = Autor_Jednostka.objects.all().order_by("rozpoczal_prace")
        self.assertEqual(lx[0].rozpoczal_prace, date(1912, 1, 1))
        self.assertEqual(lx[1].rozpoczal_prace, date(1920, 1, 1))

        self.assertEqual(lx[0].zakonczyl_prace, date(1914, 12, 31))
        self.assertEqual(lx[1].zakonczyl_prace, date(1921, 12, 31))

        self.assertEqual(a.afiliacja_na_rok(1912, w), True)
        self.assertEqual(a.afiliacja_na_rok(1913, w), True)
        self.assertEqual(a.afiliacja_na_rok(1914, w), True)
        self.assertEqual(a.afiliacja_na_rok(1914, w2), None)

        self.assertEqual(a.afiliacja_na_rok(1920, w), True)
        self.assertEqual(a.afiliacja_na_rok(1921, w), True)

        self.assertEqual(a.afiliacja_na_rok(1922, w), None)
        self.assertEqual(a.afiliacja_na_rok(1916, w), None)

        # Gdy jest wpisany tylko początek czasu pracy, traktujemy pracę
        # jako NIE zakończoną i każda data w przyszłości ma zwracać to miejsce
        Autor_Jednostka.objects.create(
            autor=a, jednostka=j2, rozpoczal_prace=date(2100, 1, 1)
        )
        self.assertEqual(a.afiliacja_na_rok(2200, w2), True)

        Autor_Jednostka.objects.all().delete()
        # Gdy nie ma dat początku i końca pracy, to funkcja ma zwracać NONE
        Autor_Jednostka.objects.create(autor=a, jednostka=j2)
        self.assertEqual(a.afiliacja_na_rok(2100, w2), None)
        self.assertEqual(a.afiliacja_na_rok(1100, w2), None)

    def test_autor_save(self):
        a = Autor.objects.create(nazwisko="von Foo", imiona="Bar")
        self.assertEqual(a.sort, "foobar")

    def test_autor_prace_w_latach(self):
        ROK = 2000

        a = baker.make(Autor)
        j = any_jednostka()
        w = baker.make(Wydawnictwo_Ciagle, rok=ROK)
        baker.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=j, rekord=w)

        self.assertEqual(a.prace_w_latach()[0], ROK)


class TestAutor_Jednostka(TestCase):
    def setUp(self):
        Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
        Funkcja_Autora.objects.get_or_create(skrot="kier.", nazwa="kierownik")

    def test_autor_jednostka(self):
        f = Funkcja_Autora.objects.get(skrot="kier.")
        a = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)
        j = any_jednostka(nazwa="Lol", skrot="L.")
        aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=f)
        self.assertEqual(str(aj), "Lol Omg ↔ kierownik, L.")

        aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=None)
        self.assertEqual(str(aj), "Lol Omg ↔ L.")

        aj.rozpoczal_prace = datetime(2012, 1, 1)
        aj.zakonczyl_prace = datetime(2012, 1, 2)
        aj.full_clean()

        aj.rozpoczal_prace = datetime(2013, 1, 1)
        aj.zakonczyl_prace = datetime(2011, 1, 1)
        self.assertRaises(ValidationError, aj.full_clean)

    def test_defragmentuj(self):
        w = any_wydzial()
        a = baker.make(Autor)

        j1 = any_jednostka(nazwa="X", wydzial=w)
        any_jednostka(nazwa="Y", wydzial=w)
        any_jednostka(nazwa="Z", wydzial=w)

        # Taka sytuacja ma miejsce przy imporcie danych - w "starym" systemie są dane
        # na temat jednostek BEZ czasu pracy, zaś nowy dodaje informacje o czasie pracy
        Autor_Jednostka.objects.create(autor=a, jednostka=j1)
        Autor_Jednostka.objects.create(
            autor=a,
            jednostka=j1,
            rozpoczal_prace=date(2012, 1, 1),
            zakonczyl_prace=date(2012, 12, 31),
        )
        Autor_Jednostka.objects.create(
            autor=a,
            jednostka=j1,
            rozpoczal_prace=date(2013, 1, 1),
            zakonczyl_prace=date(2014, 12, 31),
        )
        Autor_Jednostka.objects.create(
            autor=a, jednostka=j1, rozpoczal_prace=date(2016, 1, 1)
        )

        Autor_Jednostka.objects.defragmentuj(a, j1)

        self.assertEqual(Autor_Jednostka.objects.all().count(), 2)

        Autor_Jednostka.objects.all().delete()

        # Ta sytuacja ma miejsce przy powtórnym imporcie XLSa do nowego systemu
        # autor ma pole rozpoczal_prace, ale zakoncyzl_prace jest NONE z powodu takiego, ze dalej
        # tam pracuje...
        Autor_Jednostka.objects.create(autor=a, jednostka=j1)
        Autor_Jednostka.objects.create(
            autor=a,
            jednostka=j1,
            rozpoczal_prace=date(2012, 1, 1),
            zakonczyl_prace=None,
        )
        Autor_Jednostka.objects.create(
            autor=a,
            jednostka=j1,
            rozpoczal_prace=date(2014, 1, 1),
            zakonczyl_prace=date(2015, 12, 31),
        )

        Autor_Jednostka.objects.defragmentuj(a, j1)
        aj = Autor_Jednostka.objects.all()[0]
        self.assertEqual(aj.rozpoczal_prace, date(2012, 1, 1))
        self.assertEqual(aj.zakonczyl_prace, date(2015, 12, 31))


class TestPunktacjaZrodla(TestCase):
    def test_punktacja_zrodla(self):
        z = baker.make(Zrodlo, nazwa="123 test")
        j = baker.make(Punktacja_Zrodla, rok="2012", impact_factor="0.5", zrodlo=z)
        self.assertEqual(str(j), 'Punktacja źródła "123 test" za rok 2012')


class TestZrodlo(TestCase):
    def test_zrodlo(self):
        z = baker.make(Zrodlo, nazwa="foo")
        self.assertEqual(str(z), "foo")

        z = baker.make(Zrodlo, nazwa="foo", nazwa_alternatywna="bar")
        self.assertEqual(str(z), "foo")

        z = baker.make(
            Zrodlo, nazwa="foo", poprzednia_nazwa="bar", nazwa_alternatywna="quux"
        )
        self.assertEqual(str(z), "foo (d. bar)")

        z = baker.make(Zrodlo, nazwa="foo", poprzednia_nazwa="quux")
        self.assertEqual(str(z), "foo (d. quux)")

    def test_zrodlo_prace_w_latach(self):
        z = baker.make(Zrodlo)
        any_ciagle(rok=2012, zrodlo=z)

        self.assertEqual(list(z.prace_w_latach()), [2012])

    def test_unicode(self):
        z = Zrodlo(nazwa="foo", poprzednia_nazwa="bar")
        self.assertEqual(str(z), "foo (d. bar)")


class TestRedakcjaZrodla(TestCase):
    # fixtures = ['plec.json']
    def setUp(self):
        Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
        Plec.objects.get_or_create(skrot="M", nazwa="mężczyzna")
        Plec.objects.get_or_create(skrot="K", nazwa="kobieta")
        Tytul.objects.get_or_create(skrot="dr")

    def test_redakcja_zrodla(self):
        a = baker.make(
            Autor,
            imiona="Jan",
            nazwisko="Kowalski",
            tytul=Tytul.objects.get(skrot="dr"),
            plec=Plec.objects.get(skrot="M"),
        )
        z = baker.make(Zrodlo, nazwa="LOL Zine")
        r = Redakcja_Zrodla.objects.create(
            zrodlo=z, redaktor=a, od_roku=2010, do_roku=None
        )

        self.assertEqual(str(r), "Redaktorem od 2010 jest Kowalski Jan, dr")

        r.do_roku = 2012
        self.assertEqual(str(r), "Redaktorem od 2010 do 2012 był Kowalski Jan, dr")

        a.plec = Plec.objects.get(skrot="K")
        self.assertEqual(str(r), "Redaktorem od 2010 do 2012 była Kowalski Jan, dr")

        a.plec = None
        self.assertEqual(str(r), "Redaktorem od 2010 do 2012 był(a) Kowalski Jan, dr")


class TestAbstract(TestCase):
    def test_abstract(self):
        a = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)

        j = any_jednostka(skrot="foo")
        t = baker.make(Typ_Odpowiedzialnosci, skrot="X", nazwa="Y")
        r = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="AAA")
        b = Wydawnictwo_Ciagle_Autor.objects.create(
            autor=a, jednostka=j, typ_odpowiedzialnosci=t, rekord=r
        )
        self.assertEqual(str(b), "Lol Omg - foo")
        self.assertEqual(str(r), "AAA")
        self.assertEqual(str(t), "Y")

    def test_ModelZNazwa(self):
        a = Jezyk.objects.create(nazwa="Foo", skrot="Bar")
        self.assertEqual(str(a), "Foo")


class TestTworzenieModeliAutorJednostka(TestCase):
    def setUp(self):
        Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")

    def test_tworzenie_modeli_autor_jednostka(self):
        a = any_autor()
        j = any_jednostka()
        c = any_ciagle()
        c.dodaj_autora(a, j)

        # Utworzenie modelu Wydawnictwo_Zwarte_Autor powinno utworzyć model
        # Autor_Jednostka, będący powiązaniem autora a z jednostką j
        self.assertEqual(Autor_Jednostka.objects.filter(autor=a).count(), 1)

    def test_tworzenie_modeli_autor_jednostka_zwarte(self):
        a = any_autor()
        j = any_jednostka()
        c = any_zwarte()
        c.dodaj_autora(a, j)

        # Utworzenie modelu Wydawnictwo_Zwarte_Autor powinno utworzyć model
        # Autor_Jednostka, będący powiązaniem autora a z jednostką j
        self.assertEqual(Autor_Jednostka.objects.filter(autor=a).count(), 1)


class TestWydawnictwoCiagleTestWydawnictwoZwarte(TestCase):
    # fixtures = ['charakter_formalny.json']

    def test_clean(self):
        for model in [any_ciagle, any_zwarte]:
            for skrot in ["PAT", "D", "H"]:
                try:
                    instance = model(
                        charakter_formalny=Charakter_Formalny.objects.get(skrot=skrot)
                    )
                except Charakter_Formalny.DoesNotExist:
                    continue

                self.assertRaises(ValidationError, instance.clean_fields)


def test_patent_kasowanie(autor_jan_kowalski, jednostka, typy_odpowiedzialnosci):
    p = baker.make(Patent)
    p.dodaj_autora(autor_jan_kowalski, jednostka)
    p.delete()
