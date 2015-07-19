# -*- encoding: utf-8 -*-
from datetime import datetime, date

from django.core.exceptions import ValidationError
from django.test import TestCase
from model_mommy import mommy

from bpp.models import NazwaISkrot, Wydzial, Uczelnia, Jednostka, \
    Tytul, Autor, Punktacja_Zrodla, Zrodlo, Redakcja_Zrodla, Plec, Typ_Odpowiedzialnosci, \
    Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle, Jezyk, Rekord, Praca_Doktorska, Praca_Habilitacyjna
from bpp.models.autor import Funkcja_Autora, Autor_Jednostka
from bpp.models.system import Charakter_Formalny
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.tests.util import any_uczelnia, any_autor, CURRENT_YEAR, any_ciagle, any_wydzial, any_doktorat, any_habilitacja, any_zwarte
from bpp.tests.util import any_jednostka


class TestNazwaISkrot(TestCase):
    def test_skrot(self):
        a = NazwaISkrot(nazwa="foo", skrot="bar")
        self.assertEquals("foo", unicode(a))


class TestTytul(TestCase):
    def test_tytul(self):
        t = mommy.make(Tytul)
        unicode(t)


class TestWydzial(TestCase):
    def test_wydzial(self):
        u = any_uczelnia()
        w = any_wydzial(nazwa="Lekarski", uczelnia=u)
        self.assertEquals(unicode(w), u"Lekarski")


class TestJednostka(TestCase):
    def test_jednostka(self):
        w = any_wydzial(skrot="BAR")
        j = any_jednostka(nazwa="foo", wydzial_skrot="BAR")
        self.assertEquals(unicode(j), u"foo (BAR)")

    def test_obecni_autorzy(self):
        j1 = any_jednostka()

        a1 = mommy.make(Autor)
        a2 = mommy.make(Autor)
        a3 = mommy.make(Autor)

        j1.dodaj_autora(a1, rozpoczal_prace=date(2012, 1, 1))
        j1.dodaj_autora(a2, zakonczyl_prace=date(2012, 12, 31))
        j1.dodaj_autora(a3)

        obecni = j1.obecni_autorzy()

        self.assertIn(a1, obecni)
        self.assertNotIn(a2, obecni)
        self.assertIn(a3, obecni)

    def test_kierownik(self):
        j1 = any_jednostka()
        self.assertEquals(j1.kierownik(), None)

        a1 = mommy.make(Autor)
        j1.dodaj_autora(a1, funkcja=Funkcja_Autora.objects.create(
            nazwa='kierownik'))

        self.assertEquals(j1.kierownik(), a1)

    def test_prace_w_latach(self):
        j1 = any_jednostka()
        a1 = mommy.make(Autor)

        wc = any_ciagle(rok=2012)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wc, autor=a1, jednostka=j1,
            typ_odpowiedzialnosci=mommy.make(Typ_Odpowiedzialnosci))

        wc = any_ciagle(rok=2013)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wc, autor=a1, jednostka=j1,
            typ_odpowiedzialnosci=mommy.make(Typ_Odpowiedzialnosci))

        self.assertEquals(list(j1.prace_w_latach()), [2012, 2013])


class TestAutor(TestCase):
    fixtures = ['charakter_formalny.json', 'tytul.json',
                'typ_odpowiedzialnosci.json']

    def test_autor(self):
        j = mommy.make(Autor, imiona='Omg', nazwisko='Lol', tytul=None)
        self.assertEquals(unicode(j), u"Lol Omg")

        t = Tytul.objects.create(nazwa="daktur", skrot="dar")
        j = mommy.make(Autor, imiona='Omg', nazwisko='Lol', tytul=t)
        self.assertEquals(unicode(j), u"Lol Omg, dar")

        j.poprzednie_nazwiska = "Kowalski"
        self.assertEquals(unicode(j), u"Lol Omg (Kowalski), dar")

        self.assertEquals(j.get_full_name(), u"Omg Lol (Kowalski)")
        self.assertEquals(j.get_full_name_surname_first(), u"Lol (Kowalski) Omg")

    def test_afiliacja_na_rok(self):
        w = any_wydzial()
        n = any_wydzial(skrot='w2', nazwa='w2')
        j = any_jednostka(wydzial=w)
        a = mommy.make(Autor)

        aj = Autor_Jednostka.objects.create(autor=a, jednostka=j,
                                            funkcja=mommy.make(Funkcja_Autora))

        self.assertEquals(a.afiliacja_na_rok(2030, w), None)
        self.assertEquals(a.afiliacja_na_rok(2030, n), None)

        aj.rozpoczal_prace = date(2012, 1, 1)
        aj.save()

        self.assertEquals(a.afiliacja_na_rok(2030, w), True)
        self.assertEquals(a.afiliacja_na_rok(2011, w), None)
        self.assertEquals(a.afiliacja_na_rok(2030, n), None)

        aj.zakonczyl_prace = date(2013, 12, 31)
        aj.save()

        self.assertEquals(a.afiliacja_na_rok(2030, w), None)
        self.assertEquals(a.afiliacja_na_rok(2011, w), None)
        self.assertEquals(a.afiliacja_na_rok(2012, w), True)
        self.assertEquals(a.afiliacja_na_rok(2030, n), None)

    def test_dodaj_jednostke(self):
        f = mommy.make(Funkcja_Autora)
        a = mommy.make(Autor, imiona='Foo', nazwisko='Bar', tytul=None)
        w = any_wydzial(nazwa='WL', skrot='WL')
        w2 = any_wydzial(nazwa='XX', skrot='YY')
        j = any_jednostka(wydzial=w)
        j2 = any_jednostka(wydzial=w2)


        def ma_byc(ile=1):
            self.assertEquals(Autor_Jednostka.objects.count(), ile)

        a.dodaj_jednostke(j, 2012, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 2013, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 2014, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 2013, f)
        ma_byc(1)

        a.dodaj_jednostke(j, 2020, f)
        ma_byc(2)

        a.dodaj_jednostke(j, 2021, f)
        ma_byc(2)

        a.dodaj_jednostke(j, 2060, f)
        ma_byc(3)

        l = Autor_Jednostka.objects.all().order_by('rozpoczal_prace')
        self.assertEquals(l[0].rozpoczal_prace, date(2012, 1, 1))
        self.assertEquals(l[1].rozpoczal_prace, date(2020, 1, 1))

        self.assertEquals(l[0].zakonczyl_prace, date(2014, 12, 31))
        self.assertEquals(l[1].zakonczyl_prace, date(2021, 12, 31))

        self.assertEquals(a.afiliacja_na_rok(2012, w), True)
        self.assertEquals(a.afiliacja_na_rok(2013, w), True)
        self.assertEquals(a.afiliacja_na_rok(2014, w), True)
        self.assertEquals(a.afiliacja_na_rok(2014, w2), None)

        self.assertEquals(a.afiliacja_na_rok(2020, w), True)
        self.assertEquals(a.afiliacja_na_rok(2021, w), True)

        self.assertEquals(a.afiliacja_na_rok(2022, w), None)
        self.assertEquals(a.afiliacja_na_rok(2016, w), None)

        # Gdy jest wpisany tylko początek czasu pracy, traktujemy pracę
        # jako NIE zakończoną i każda data w przyszłości ma zwracać to miejsce
        Autor_Jednostka.objects.create(autor=a, jednostka=j2,
                                       rozpoczal_prace=date(2100, 1, 1))
        self.assertEquals(a.afiliacja_na_rok(2200, w2), True)

        Autor_Jednostka.objects.all().delete()
        # Gdy nie ma dat początku i końca pracy, to funkcja ma zwracać NONE
        Autor_Jednostka.objects.create(autor=a, jednostka=j2)
        self.assertEquals(a.afiliacja_na_rok(2100, w2), None)
        self.assertEquals(a.afiliacja_na_rok(1100, w2), None)

    def test_autor_save(self):
        a = Autor.objects.create(nazwisko='von Foo', imiona='Bar')
        self.assertEquals(a.sort, 'foobar')

    def test_autor_prace_w_latach(self):
        ROK = 2000

        a = mommy.make(Autor)
        j = any_jednostka()
        w = mommy.make(Wydawnictwo_Ciagle, rok=ROK)
        wa = mommy.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=j, rekord=w)

        self.assertEquals(
            a.prace_w_latach()[0],
            ROK)

    def test_praca_doktorska_test_praca_habilitacyjna(self):
        a = mommy.make(Autor, imiona='foo', nazwisko='bar', tytul=Tytul.objects.get(skrot='dr'))
        for klass, r1, r2, fn in [
            (Praca_Doktorska, False, True, any_doktorat),
            (Praca_Habilitacyjna, True, False, any_habilitacja)]:
            k = fn(autor=a)

            s1 = a.praca_doktorska() is None
            self.assertEquals(s1, r1)

            s2 = a.praca_habilitacyjna() is None
            self.assertEquals(s2, r2)

            k.delete()

    def test_ostatnia_jednostka_1(self):
        a = any_autor()
        j1 = any_jednostka()
        j1.dodaj_autora(a)

        j2 = any_jednostka()
        j2.dodaj_autora(a)

        self.assertEquals(a.ostatnia_jednostka(), j2)

    def test_ostatnia_jednostka_2(self):
        a = any_autor()

        j2 = any_jednostka()
        j2.dodaj_autora(a, rozpoczal_prace=date(CURRENT_YEAR, 1, 1))

        j1 = any_jednostka()
        j1.dodaj_autora(a)

        self.assertEquals(a.ostatnia_jednostka(), j2)


class TestAutor_Jednostka(TestCase):
    def test_autor_jednostka(self):
        f = Funkcja_Autora.objects.create(nazwa="kierownik", skrot="kier.")
        a = mommy.make(Autor, imiona='Omg', nazwisko='Lol', tytul=None)
        j = any_jednostka(nazwa='Lol', skrot="L.")
        aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=f)
        self.assertEquals(unicode(aj), u'Lol Omg ↔ kierownik, L.')

        aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=None)
        self.assertEquals(unicode(aj), u'Lol Omg ↔ L.')

        aj.rozpoczal_prace = datetime(2012, 1, 1)
        aj.zakonczyl_prace = datetime(2012, 1, 2)
        aj.full_clean()

        aj.rozpoczal_prace = datetime(2013, 1, 1)
        aj.zakonczyl_prace = datetime(2011, 1, 1)
        self.assertRaises(ValidationError, aj.full_clean)


    def test_defragmentuj(self):
        w = any_wydzial()
        a = mommy.make(Autor)

        j1 = any_jednostka(nazwa="X", wydzial=w)
        j2 = any_jednostka(nazwa="Y", wydzial=w)
        j3 = any_jednostka(nazwa="Z", wydzial=w)

        # Taka sytuacja ma miejsce przy imporcie danych - w "starym" systemie są dane
        # na temat jednostek BEZ czasu pracy, zaś nowy dodaje informacje o czasie pracy
        Autor_Jednostka.objects.create(autor=a, jednostka=j1)
        Autor_Jednostka.objects.create(autor=a, jednostka=j1,
                                       rozpoczal_prace=date(2012, 1, 1),
                                       zakonczyl_prace=date(2012, 12, 31))
        Autor_Jednostka.objects.create(autor=a, jednostka=j1,
                                       rozpoczal_prace=date(2013, 1, 1),
                                       zakonczyl_prace=date(2014, 12, 31))
        Autor_Jednostka.objects.create(autor=a, jednostka=j1,
                                       rozpoczal_prace=date(2018, 1, 1))

        Autor_Jednostka.objects.defragmentuj(a, j1)

        self.assertEquals(Autor_Jednostka.objects.all().count(), 2)

        Autor_Jednostka.objects.all().delete()

        # Ta sytuacja ma miejsce przy powtórnym imporcie XLSa do nowego systemu
        # autor ma pole rozpoczal_prace, ale zakoncyzl_prace jest NONE z powodu takiego, ze dalej
        # tam pracuje...
        Autor_Jednostka.objects.create(autor=a, jednostka=j1)
        Autor_Jednostka.objects.create(autor=a, jednostka=j1,
                                       rozpoczal_prace=date(2012, 1, 1),
                                       zakonczyl_prace=None)
        Autor_Jednostka.objects.create(autor=a, jednostka=j1,
                                       rozpoczal_prace=date(2018, 1, 1),
                                       zakonczyl_prace=date(2019, 12, 31))

        Autor_Jednostka.objects.defragmentuj(a, j1)
        aj = Autor_Jednostka.objects.all()[0]
        self.assertEquals(aj.rozpoczal_prace, date(2012, 1, 1))
        self.assertEquals(aj.zakonczyl_prace, date(2019, 12, 31))


class TestPunktacjaZrodla(TestCase):
    def test_punktacja_zrodla(self):
        j = mommy.make(Punktacja_Zrodla, rok='2012', impact_factor='0.5')
        self.assertEquals(unicode(j), u'Punktacja źródła za rok 2012')


class TestZrodlo(TestCase):
    def test_zrodlo(self):
        z = mommy.make(Zrodlo, nazwa="foo")
        self.assertEquals(unicode(z), 'foo')

        z = mommy.make(Zrodlo, nazwa="foo", nazwa_alternatywna="bar")
        self.assertEquals(unicode(z), 'foo (bar)')

        z = mommy.make(Zrodlo, nazwa="foo", poprzednia_nazwa="bar", nazwa_alternatywna="quux")
        self.assertEquals(unicode(z), 'foo (quux) (d. bar)')

        z = mommy.make(Zrodlo, nazwa="foo", poprzednia_nazwa="quux")
        self.assertEquals(unicode(z), 'foo (d. quux)')

    def test_zrodlo_prace_w_latach(self):
        z = mommy.make(Zrodlo)
        wc = any_ciagle(rok=2012, zrodlo=z)

        self.assertEquals(list(z.prace_w_latach()), [2012])

    def test_unicode(self):
        z = Zrodlo(nazwa="foo", poprzednia_nazwa="bar")
        self.assertEquals(
            unicode(z),
            "foo (d. bar)"
        )


class TestRedakcjaZrodla(TestCase):
    fixtures = ['plec.json']

    def test_redakcja_zrodla(self):
        t = Tytul.objects.create(nazwa='daktor', skrot='dr')
        a = mommy.make(
            Autor, imiona="Jan", nazwisko="Kowalski", tytul=t,
            plec=Plec.objects.get(skrot='M'))
        z = mommy.make(Zrodlo, nazwa='LOL Zine')
        r = Redakcja_Zrodla.objects.create(
            zrodlo=z, redaktor=a, od_roku=2010, do_roku=None)

        self.assertEquals(
            unicode(r),
            u"Redaktorem od 2010 jest Kowalski Jan, dr")

        r.do_roku = 2012
        self.assertEquals(
            unicode(r),
            u"Redaktorem od 2010 do 2012 był Kowalski Jan, dr")

        a.plec = Plec.objects.get(skrot='K')
        self.assertEquals(
            unicode(r),
            u"Redaktorem od 2010 do 2012 była Kowalski Jan, dr")

        a.plec = None
        self.assertEquals(
            unicode(r),
            u'Redaktorem od 2010 do 2012 był(a) Kowalski Jan, dr'
        )


class TestAbstract(TestCase):
    def test_abstract(self):
        a = mommy.make(Autor, imiona='Omg', nazwisko='Lol', tytul=None)

        j = any_jednostka(skrot="foo")
        t = mommy.make(Typ_Odpowiedzialnosci, skrot='X', nazwa='Y')
        r = mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny='AAA')
        b = Wydawnictwo_Ciagle_Autor.objects.create(
            autor=a, jednostka=j, typ_odpowiedzialnosci=t,
            rekord=r)
        self.assertEquals(unicode(b), u"Lol Omg - foo")
        self.assertEquals(unicode(r), u'AAA')
        self.assertEquals(unicode(t), u'Y')

    def test_ModelZNazwa(self):
        a = Jezyk.objects.create(nazwa='Foo', skrot='Bar')
        self.assertEquals(unicode(a), 'Foo')


class TestTworzenieModeliAutorJednostka(TestCase):
    def test_tworzenie_modeli_autor_jednostka(self):
        a = any_autor()
        j = any_jednostka()
        c = any_ciagle()
        c.dodaj_autora(a, j)

        # Utworzenie modelu Wydawnictwo_Zwarte_Autor powinno utworzyć model
        # Autor_Jednostka, będący powiązaniem autora a z jednostką j
        self.assertEquals(Autor_Jednostka.objects.filter(autor=a).count(), 1)


class TestWydawnictwoCiagleTestWydawnictwoZwarte(TestCase):
    fixtures = ['charakter_formalny.json']

    def test_clean(self):
        for model in [any_ciagle, any_zwarte]:
            for skrot in ['PAT', 'D', 'H']:
                try:
                    instance = model(
                        charakter_formalny=Charakter_Formalny.objects.get(skrot=skrot))
                except Charakter_Formalny.DoesNotExist:
                    continue

                self.assertRaises(
                    ValidationError,
                    instance.clean_fields
                    )