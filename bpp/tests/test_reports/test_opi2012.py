# -*- encoding: utf-8 -*-

import os
from datetime import date
from model_mommy import mommy
from django.test import TestCase

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Wydzial, Autor, Wydawnictwo_Ciagle_Autor, \
    Jednostka, Zrodlo, Rodzaj_Zrodla, Typ_Odpowiedzialnosci, Autor_Jednostka, Wydawnictwo_Zwarte_Autor, Opi_2012_Afiliacja_Do_Wydzialu, Tytul, Typ_KBN, Opi_2012_Tytul_Cache, Charakter_Formalny

from bpp.reports.opi_2012 import publikacje_z_impactem_wykaz_A, charakter, publikacje_erih, publikacje_wykaz_B, \
    publikacje_wos, jezyk, monografie_w_jezykach, monografie_po_polsku, \
    monografie_w_innym_jezyku, rozdzialy_w_monografiach_w_jezykach, rozdzialy_w_monografiach_po_polsku, \
    rozdzialy_w_monografiach_w_innym_jezyku, wiersze_publikacji, chce_jeden_wydzial, wiersze_monografii, \
    wiersze_rozdzialu, wiersze_wos, wez_funkcje_tabelki, wytnij_numery_stron, wytnij_tom, dopisz_autorow, \
    znaki_wydawnicze, autorzy_z_wydzialu, monografie_wieloautorskie, wiersze_wieloautorskie, \
    formatuj_autorow, wytnij_zbedne_informacje_ze_zrodla, zlokalizuj_publikacje_nadrzedna
from bpp.tests.util import any_zwarte, any_wydzial, any_jednostka, any_ciagle

from bpp.tests.test_reports.util import USUAL_FIXTURES, autor, ciagle, zwarte
from bpp.util import zrob_cache
from bpp.tests.util import any_jednostka


rok = 2012


class TestOpi2012(TestCase):
    fixtures = USUAL_FIXTURES

    def test_formatuj_autorow(self):
        a = mommy.make(Autor, nazwisko='Foo', imiona='Bar $Baz Quux',
                      tytul=Tytul.objects.get(skrot='dr'))
        b = mommy.make(Autor, nazwisko='Foo', imiona='Bar #Baz Quux',
                      tytul=Tytul.objects.get(skrot='dr'))
        ret = formatuj_autorow([a, b], 'tak')
        self.assertEquals(
            ret, u'dr$Foo$Bar$_Baz Quux$tak#dr$Foo$Bar$_Baz Quux$tak'
        )

    def test_chce_jeden_wydzial(self):
        # Cel tego testu to stworzyć DWIE prace autorowane przez autorów
        # z dwóch różnych wydziałów i sprawdzić, czy funkcja filtrująca tylko
        # jeden wydział da jakiekolwiek efekty:

        not_pw = charakter('WYN')

        w1 = any_wydzial()
        w2 = any_wydzial()

        j1 = any_jednostka(wydzial=w1)
        j2 = any_jednostka(wydzial=w2)

        a1 = autor(j1, rozpoczal_prace=date(rok, 1, 1),
                   zakonczyl_prace=date(rok, 12, 31))
        a2 = autor(j2, rozpoczal_prace=date(rok, 1, 1))
        a3 = autor(j2, rozpoczal_prace=date(rok - 5, 1, 1),
                   zakonczyl_prace=date(rok - 1, 12, 31))

        wc1 = ciagle(a1, j1, rok=rok, charakter_formalny=not_pw,
                     impact_factor=1.0, punkty_kbn=1.0)
        wc2 = ciagle(a2, j2, rok=rok, charakter_formalny=not_pw,
                     impact_factor=1.0, punkty_kbn=1.0)
        wc3 = ciagle(a3, j2, rok=rok, charakter_formalny=not_pw,
                     impact_factor=1.0, punkty_kbn=1.0)

        l = chce_jeden_wydzial(publikacje_z_impactem_wykaz_A, w1, rok)
        self.assertEquals(list(l), [wc1])

        l = list(chce_jeden_wydzial(publikacje_z_impactem_wykaz_A, w2, rok))
        self.assertIn(wc2, l)
        self.assertNotIn(wc3, l)

    def test_publikacje_z_impactem_wykaz_A(self):
        not_pw = charakter('WYN')

        wydzial = any_wydzial()
        jed = any_jednostka(wydzial=wydzial)
        a1 = mommy.make(Autor)
        aj = mommy.make(Autor_Jednostka, autor=a1, jednostka=jed,
                       rozpoczal_prace=date(rok - 1, 1, 1),
                       zakonczyl_prace=date(rok + 5, 1, 1))

        wc2 = mommy.make(
            Wydawnictwo_Ciagle, rok=rok, charakter_formalny=not_pw,
            impact_factor=0.0)

        wc3 = mommy.make(
            Wydawnictwo_Ciagle, rok=rok, charakter_formalny=not_pw,
            impact_factor=1.0,
            punkty_kbn=1.0)
        Wydawnictwo_Ciagle_Autor.objects.create(
            autor=a1, rekord=wc3, jednostka=jed,
            typ_odpowiedzialnosci=mommy.make(Typ_Odpowiedzialnosci))

        self.assertEquals(
            list(publikacje_z_impactem_wykaz_A()), [wc3])

    def test_publikacje_erih(self):
        ac = charakter('AC')

        wc1 = any_ciagle(
            rok=rok,
            charakter_formalny=ac,
            uwagi='foo ERIH bar',
            punkty_kbn=10
        )

        wc2 = mommy.make(
            Wydawnictwo_Ciagle,
            rok=rok,
            uwagi='foo ERIH bar',
            punkty_kbn=10
        )

        self.assertEquals(list(publikacje_erih().order_by("pk")), [wc1, wc2])

    def test_publikacje_wykaz_B(self):
        ac = charakter('AC')

        wc1 = mommy.make(
            Wydawnictwo_Ciagle, rok=rok, charakter_formalny=ac,
            punkty_kbn=0, jezyk=jezyk('pol.')
        )

        wc2 = mommy.make(
            Wydawnictwo_Ciagle, rok=rok, charakter_formalny=ac,
            punkty_kbn=15, impact_factor=0, jezyk=jezyk('ang.')
        )

        wc3 = mommy.make(
            Wydawnictwo_Ciagle, rok=rok, charakter_formalny=ac,
            punkty_kbn=15, impact_factor=0, jezyk=jezyk('b/d')
        )

        self.assertEquals(list(publikacje_wykaz_B()), [wc2])

    def test_publikacje_wos(self):
        zrz = charakter('ZRZ')
        wc = any_zwarte(rok=rok, charakter_formalny=zrz,
                        uwagi='Test fafa WoS xxx')
        self.assertEquals(list(publikacje_wos()), [wc])


    def test_rozdzialy_w_monografiach_w_jezykach(self):
        wc = mommy.make(
            Wydawnictwo_Zwarte, rok=rok, charakter_formalny=charakter('ROZ'),
            liczba_znakow_wydawniczych=5, jezyk=jezyk('wł.')
        )
        self.assertEquals(list(rozdzialy_w_monografiach_w_jezykach()), [wc])

    def test_rozdzialy_w_monografiach_po_polsku(self):
        wc = mommy.make(
            Wydawnictwo_Zwarte, rok=rok, charakter_formalny=charakter('ROZ'),
            liczba_znakow_wydawniczych=5, jezyk=jezyk('pol.')
        )
        self.assertEquals(list(rozdzialy_w_monografiach_po_polsku()), [wc])

    def test_rozdzialy_w_monografiach_w_innym_jezyku(self):
        wc = mommy.make(
            Wydawnictwo_Zwarte, rok=rok, charakter_formalny=charakter('ROZ'),
            liczba_znakow_wydawniczych=5, jezyk=jezyk('in.'),
        )
        self.assertEquals(list(rozdzialy_w_monografiach_w_innym_jezyku()), [wc])


def inne_zwarte(autor, jednostka, typ, _charakter, typ_kbn, _jezyk, **kw):
    args = autor, jednostka, Typ_Odpowiedzialnosci.objects.get(skrot=typ)
    _kw = dict(
        rok=rok,
        charakter_formalny=charakter(_charakter),
        liczba_znakow_wydawniczych=40000,
        jezyk=jezyk(_jezyk),
        tytul_oryginalny='A',
        tytul='B',
        typ_kbn=Typ_KBN.objects.get(skrot=typ_kbn))
    _kw.update(kw)

    return zwarte(*args, **_kw)


class ZwarteMixin:
    def setUp(self):
        # Cel tych testów to stworzyć DWIE prace jednego człowieka, w stosunku
        # do jednej będzie on AUTOREM, w stosunku do drugiej - redaktorem,
        # a następnie zweryfikowanie, czy poszczególne funkcje zwracają
        # prawidłowe dane
        self.wydzial = any_wydzial()
        self.jednostka = any_jednostka(wydzial=self.wydzial)
        self.autor = Autor.objects.create(
            nazwisko='Kowalski',
            imiona='Jan Test',
            tytul=Tytul.objects.get(skrot='dr'))
        Autor_Jednostka.objects.create(autor=self.autor,
                                       jednostka=self.jednostka,
                                       rozpoczal_prace=date(rok, 1, 1),
                                       zakonczyl_prace=date(rok, 12, 31))

    def moje_zwarte(self, typ, _charakter, typ_kbn, _jezyk, **kw):
        return inne_zwarte(self.autor, self.jednostka, typ, _charakter, typ_kbn,
                           _jezyk, **kw)


class TestOpi2012Monografie(ZwarteMixin, TestCase):
    fixtures = USUAL_FIXTURES


    def test_monografie_w_jezykach(self):
        # Ta ma wejsć do raportu
        wc1 = self.moje_zwarte('aut.', 'KSZ', 'PO', 'ang.')

        # Ta nie wejdzie, bo jest redaktora
        self.moje_zwarte('red.', 'KSZ', 'PO', 'niem.')

        # Ta nie wejdzie, bo nie ten język
        self.moje_zwarte('red.', 'KSZ', 'PO', 'b/d')

        # A ta nie wejdzie, bo ma typ KBN = PAK
        self.moje_zwarte('aut.', 'KSZ', 'PAK', 'ang.')

        # A ta ma 0 znaków
        self.moje_zwarte(
            'aut.', 'KSZ', 'PO', 'ang.', liczba_znakow_wydawniczych=0)

        l = list(monografie_w_jezykach())
        self.assertEquals(l, [wc1])

    def test_monografie_po_polsku(self):
        # Ta wejdzie, bo jest KSP, ma znaki wydawnicze i typ != PAK, autor
        wc1 = self.moje_zwarte('aut.', 'KSP', 'PO', 'pol.')
        # Ta nie wejdzie, bo redaktor
        self.moje_zwarte('red.', 'KSP', 'PO', 'pol.')
        # Ta nie wejdzie, bo typ PAK
        self.moje_zwarte('aut.', 'KSP', 'PAK', 'pol.')
        # Ta nie wejdzie, bo 0 znaków
        self.moje_zwarte('aut.', 'KSP', 'PO', 'pol.',
                         liczba_znakow_wydawniczych=0)

        self.assertEquals(list(monografie_po_polsku()), [wc1])


    def test_monografie_w_innym_jezyku(self):
        # Ta wejdzie, bo jest KSZKSP, ma znaki wydawnicze i typ != PAK, autor
        wc1 = self.moje_zwarte('aut.', 'KSZ', 'PO', 'in.')
        # Ta nie wejdzie, bo redaktor
        self.moje_zwarte('red.', 'KSZ', 'PO', 'in.')
        # Ta nie wejdzie, bo typ PAK
        self.moje_zwarte('aut.', 'KSZ', 'PAK', 'in.')
        # Ta nie wejdzie, bo 0 znaków
        self.moje_zwarte(
            'aut.', 'KSZ', 'PO', 'in.', liczba_znakow_wydawniczych=0)

        self.assertEquals(list(monografie_w_innym_jezyku()), [wc1])


class TestMonografieWieloautorskie(ZwarteMixin, TestCase):
    fixtures = USUAL_FIXTURES

    def setUp(self):
        ZwarteMixin.setUp(self)

        self.w1 = self.moje_zwarte(
            'aut.', 'ROZ', 'PO', 'ang.',
            tytul_oryginalny='TestA', wydawnictwo='WYD',
            isbn='123', tytul="Tak", uwagi="Owszem",
            informacje="W: Istniejaca publikacja. Pod red. Stefana Kowalskiego")

        self.moje_zwarte(
            'aut.', 'ROZ', 'PO', 'ang.', tytul_oryginalny='Test',
            wydawnictwo='WYD', isbn='123',
            tytul="Tak", uwagi="Owszem",
            liczba_znakow_wydawniczych=0)

        self.w2 = self.moje_zwarte(
            'aut.', 'ROZ', 'PO', 'pol.',
            tytul_oryginalny='TestB', wydawnictwo='WYD',
            isbn='123', tytul="Tak", uwagi="Owszem",
            informacje="W: Jakas publikacja, ktora nie istnieje")

        self.moje_zwarte('aut.', 'ROZ', 'PO', 'pol.', tytul_oryginalny='Test',
                         wydawnictwo='WYD', isbn='123',
                         tytul="Tak", uwagi="Owszem",
                         liczba_znakow_wydawniczych=0)

        self.moje_zwarte('aut.', 'KSP', 'PAK', 'ang.',
                         tytul_oryginalny='Istniejaca publikacja',
                         tytul="Tak", uwagi="Owszem",
                         wydawnictwo='WYD',
                         isbn='123')


    def test_monografie_wieloautorskie(self):
        ret = monografie_wieloautorskie().order_by('tytul_oryginalny')
        self.assertEquals(list(ret), [self.w1, self.w2])

    def test_wiersze_wieloautorskie(self):
        ret = wiersze_wieloautorskie(
            monografie_wieloautorskie, self.wydzial, rok
        )

        ret = list(ret)
        ret.sort()

        self.assertEquals(
            ret,
            [[u'', u'Jakas publikacja, ktora nie istnieje', u'', u'', u'', u'',
              u''],
             [u'WYD', u'Istniejaca publikacja', u'dr$Kowalski$Jan$Test$tak',
              2012, u'123', u'1,00', u'angielski'],
            ])

###############################################################################
# Testy generowania raportów
###############################################################################

# tytuł$nazwisko$imie$drugie imie
KOWALSKI_EXPORT = u'dr$Kowalski$Jan$Test$tak'
NOWAK_STEFAN_EXPORT = u'$Nowak$Stefan$$tak'
NOWAK_ANNA_EXPORT = u'$Nowak$Anna$$nie'

# autor1#autor2#autor3
Z_JEDNOSTKI_EXPORT = KOWALSKI_EXPORT + u'#' + NOWAK_STEFAN_EXPORT
SPOZA_JEDNOSTKI_EXPORT = NOWAK_ANNA_EXPORT


class TestOpi2012Generowanie(TestCase):
    fixtures = USUAL_FIXTURES

    def setUp(self):
        self.wl = Wydzial.objects.get(skrot='1WL') # any_wydzial(skrot='1WL')
        self.jed = Jednostka.objects.create(wydzial=self.wl, nazwa='Foo')

        self.tytul = Tytul.objects.get(skrot='dr')
        self.autor_1 = Autor.objects.create(imiona='Jan Test',
                                            nazwisko='Kowalski',
                                            tytul=self.tytul)
        Autor_Jednostka.objects.create(autor=self.autor_1, jednostka=self.jed,
                                       rozpoczal_prace=date(rok - 10, 1, 1))

        self.autor_2 = Autor.objects.create(imiona='Stefan', nazwisko='Nowak',
                                            tytul=None)
        Autor_Jednostka.objects.create(autor=self.autor_2, jednostka=self.jed,
                                       rozpoczal_prace=date(rok, 1, 1),
                                       zakonczyl_prace=date(rok, 12, 31))
        self.autor_3 = Autor.objects.create(imiona='Anna', nazwisko='Nowak',
                                            tytul=None)
        Autor_Jednostka.objects.create(autor=self.autor_3, jednostka=self.jed,
                                       rozpoczal_prace=date(rok - 1, 1, 1),
                                       zakonczyl_prace=date(rok - 1, 12, 31))

        self.zrodlo = Zrodlo.objects.create(nazwa='Foobar',
                                            rodzaj=Rodzaj_Zrodla.objects.all()[
                                                0], issn='ZRODISSN')

    def test_wiersze_publikacji(self):
        wc = mommy.make(Wydawnictwo_Ciagle, zrodlo=self.zrodlo, rok=rok,
                       charakter_formalny=charakter('WYN'), impact_factor=1.0,
                       punkty_kbn=1.0,
                       issn='MODELISSN', tytul_oryginalny='PRACA',
                       szczegoly='s. 1-2', jezyk=jezyk('pol.'),
                       informacje="2009 t. 43 nr 1")
        self.zrob_autorow(wc, Wydawnictwo_Ciagle_Autor)

        self.assertEquals(list(
            chce_jeden_wydzial(publikacje_z_impactem_wykaz_A, self.wl, rok)),
                          [wc])

        exp = [
            [u'Foobar', u'PRACA', Z_JEDNOSTKI_EXPORT, 1, SPOZA_JEDNOSTKI_EXPORT,
             2012, u'43', u'1-2', u'polski']]
        self.assertEquals(exp, list(
            wiersze_publikacji(publikacje_z_impactem_wykaz_A, self.wl, rok)))

    def zrob_autorow(self, rekord, klasa, typ_odpowiedzialnosci=None):
        if typ_odpowiedzialnosci is None:
            typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(
                skrot='aut.')

        klasa.objects.filter(rekord=rekord).delete()

        mommy.make(klasa, rekord=rekord, autor=self.autor_1, jednostka=self.jed,
                  typ_odpowiedzialnosci=typ_odpowiedzialnosci, kolejnosc=1)

        mommy.make(klasa, rekord=rekord, autor=self.autor_2, jednostka=self.jed,
                  typ_odpowiedzialnosci=typ_odpowiedzialnosci, kolejnosc=2)

        mommy.make(klasa, rekord=rekord, autor=self.autor_3, jednostka=self.jed,
                  typ_odpowiedzialnosci=typ_odpowiedzialnosci, kolejnosc=3)

    def test_wiersze_monografii(self):
        wz = any_zwarte(wydawnictwo='WYDAWCA',
                        tytul_oryginalny='TYTUL',
                        charakter_formalny=charakter('KSZ'),
                        jezyk=jezyk('ang.'),
                        rok=2012,
                        punkty_kbn=2, isbn='ISBN',
                        liczba_znakow_wydawniczych=40000)
        self.zrob_autorow(wz, Wydawnictwo_Zwarte_Autor,
                          typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(
                              skrot='aut.'))

        self.assertEquals(
            list(chce_jeden_wydzial(monografie_w_jezykach, self.wl, rok)), [wz])

        exp = [[u'WYDAWCA', u'TYTUL', Z_JEDNOSTKI_EXPORT, 1,
                SPOZA_JEDNOSTKI_EXPORT, u'angielski', 2012, u'ISBN', u'1,00']]
        self.assertEquals(exp, list(
            wiersze_monografii(monografie_w_jezykach, self.wl, rok)))

    def test_wiersze_rozdzialu(self):
        r = mommy.make(Wydawnictwo_Zwarte,
                      informacje='W: MONOGRAFIA Pod red. Stefan Budnik',
                      tytul_oryginalny='TYTUL',
                      charakter_formalny=charakter('ROZ'), jezyk=jezyk('ang.'),
                      rok=2012,
                      punkty_kbn=2, liczba_znakow_wydawniczych=40000)
        self.zrob_autorow(r, Wydawnictwo_Zwarte_Autor)

        self.assertEquals(list(
            chce_jeden_wydzial(rozdzialy_w_monografiach_w_jezykach, self.wl,
                               rok)), [r])

        exp = [[u'MONOGRAFIA', u'TYTUL', Z_JEDNOSTKI_EXPORT, 1,
                SPOZA_JEDNOSTKI_EXPORT, u'angielski', u'1,00']]
        self.assertEquals(exp, list(
            wiersze_rozdzialu(rozdzialy_w_monografiach_w_jezykach, self.wl,
                              rok)))

    def test_wiersze_wos(self):
        r = mommy.make(Wydawnictwo_Zwarte, wydawnictwo='WYDAWNICTWO',
                      tytul_oryginalny='TYTUL',
                      charakter_formalny=charakter('ZRZ'), jezyk=jezyk('ang.'),
                      rok=2012,
                      uwagi='WoS', szczegoly='SZCZEGOLY s. 55-54',
                      liczba_znakow_wydawniczych=40000,
                      informacje="W: Jakaś konferencja")
        self.zrob_autorow(r, Wydawnictwo_Zwarte_Autor)

        self.assertEquals(
            list(chce_jeden_wydzial(publikacje_wos, self.wl, rok)), [r])

        exp = [[u'Jakaś konferencja', u'TYTUL', Z_JEDNOSTKI_EXPORT, 1,
                SPOZA_JEDNOSTKI_EXPORT, u'2012', u'', u'55-54', u'angielski',
                u'1,00']]
        self.assertEquals(exp, list(wiersze_wos(publikacje_wos, self.wl, rok)))

    def test_wez_funkcje_tabelki(self):
        self.assertEquals(
            wez_funkcje_tabelki('rozdzialy_w_monografiach_po_polsku'),
            wiersze_rozdzialu)

    def test_wytnij_numery_stron(self):
        self.assertEquals(
            wytnij_numery_stron("s. 44-55, bibliogr. 13-12- streszcz."),
            "44-55")

        self.assertEquals(
            wytnij_numery_stron("lol wtf s. 44-55, bibliogr. stres 66-99 zcz."),
            "44-55")

        self.assertEquals(
            wytnij_numery_stron("s. 44, bibliogr. zlee 55-55 streszcz."),
            "44")

        self.assertEquals(
            wytnij_numery_stron("zfassung s.44, bibliogr. streszcz."),
            "44")

        self.assertEquals(
            wytnij_numery_stron("zfassung s. 2Q1-2Q8, bibliogr. streszcz."),
            "2Q1-2Q8")

        self.assertEquals(
            wytnij_numery_stron("zfassung s. e15-e17, bibliogr. streszcz."),
            "e15-e17")

        self.assertEquals(wytnij_numery_stron(None), None)

    def test_wytnij_tom(self):
        self.assertEquals(wytnij_tom("2009 t. 43 nr 1"), "43")
        self.assertEquals(wytnij_tom("2009 vol. 43 nr 1"), "43")
        self.assertEquals(wytnij_tom(None), None)

    def test_dopisz_autorow(self):
        wc = mommy.make(Wydawnictwo_Ciagle, zrodlo=self.zrodlo, rok=rok,
                       charakter_formalny=charakter('WYN'), impact_factor=1.0,
                       punkty_kbn=1.0,
                       issn='MODELISSN', tytul_oryginalny='PRACA',
                       szczegoly='s. 1-2', jezyk=jezyk('pol.'),
                       informacje="2009 t. 43 nr 1",
                       tytul="pRACA", uwagi="foo")
        self.zrob_autorow(wc, Wydawnictwo_Ciagle_Autor)

        arr = []
        dopisz_autorow(wc, rok, arr, self.wl)
        self.assertEquals(
            [Z_JEDNOSTKI_EXPORT, 1, SPOZA_JEDNOSTKI_EXPORT],
            arr)

    def test_autorzy_z_wydzialu(self):
        wc = mommy.make(Wydawnictwo_Ciagle, zrodlo=self.zrodlo, rok=rok,
                       charakter_formalny=charakter('WYN'), impact_factor=1.0,
                       punkty_kbn=1.0,
                       issn='MODELISSN', tytul_oryginalny='PRACA',
                       tytul='PRACA', uwagi='foo',
                       szczegoly='s. 1-2', jezyk=jezyk('pol.'),
                       informacje="2009 t. 43 nr 1")
        self.zrob_autorow(wc, Wydawnictwo_Ciagle_Autor)

        arr = []

        Autor_Jednostka.objects.all().delete()

        Opi_2012_Afiliacja_Do_Wydzialu.objects.create(autor=self.autor_1,
                                                      rok=rok, wydzial=self.wl)
        Opi_2012_Afiliacja_Do_Wydzialu.objects.create(autor=self.autor_2,
                                                      rok=rok + 1,
                                                      wydzial=self.wl)

        z_wydzialu, spoza_wydzialu = autorzy_z_wydzialu(wc, rok, self.wl)

        self.assertEquals(
            z_wydzialu, [self.autor_1, ])


    def test_znaki_wydawnicze(self):
        self.assertEquals(znaki_wydawnicze(None), u'0,00')
        self.assertEquals(znaki_wydawnicze(40000), u'1,00')

    def test_wytnij_zbedne_informacje_ze_zrodla(self):
        s1 = 'W: Praca testowa. Pod red. Stefan Kowalski'
        s2 = 'Praca testowa.'

        self.assertEquals(wytnij_zbedne_informacje_ze_zrodla(s1), s2)

    def test_zrob_cache(self):
        s1 = 'To jest - praca. Taka jest praca. Tom: pierwszy,,'
        s2 = 'tojestpracatakajestpracatompierwszy'

        self.assertEquals(zrob_cache(s1), s2)

    def test_zlokalizuj_publikacje_nadrzedna(self):
        w1 = zwarte(
            self.autor_1, self.jed,
            Typ_Odpowiedzialnosci.objects.get(skrot='aut.'),
            tytul_oryginalny="Carotid artery : costam costam. Vol. 1.",
            rok=2013,
            charakter_formalny=Charakter_Formalny.objects.get(skrot='ROZ'))

        s = 'W: Carotid artery : costam costam. Vol. 1. Pod red. Stefan Kowalski'
        # Zwróci grzecznie pierwszą pasującą z tabeli
        self.assertEquals(
            zlokalizuj_publikacje_nadrzedna(s, 2013),
            w1)

        # Tutaj przy dwóch takich samych tytułach nie bierzemy pod uwagę rozdziału,
        # więc dostaniemy w2
        w2 = zwarte(
            self.autor_1, self.jed,
            Typ_Odpowiedzialnosci.objects.get(skrot='aut.'),
            tytul_oryginalny="Carotid artery : costam costam. Vol. 1.",
            rok=2013,
            charakter_formalny=Charakter_Formalny.objects.get(skrot='KSP'))
        self.assertEquals(zlokalizuj_publikacje_nadrzedna(s, 2013), w2)

        w2.delete()

        # Teraz, w sytuacji, gdy jest niedokładnie podany tytuł, dostaniemy
        # informacje, korzystając z tabeli cache:
        w2 = zwarte(
            self.autor_1, self.jed,
            Typ_Odpowiedzialnosci.objects.get(skrot='aut.'),
            tytul_oryginalny="Carotid artery : costam costam. Vol. 2",
            rok=2012
        )

        Opi_2012_Tytul_Cache.objects.rebuild()

        s1 = "W: carotid ArTERY   :  costam costam. vol 2 ; ()Pod red. Jan Matejko"

        self.assertEquals(zlokalizuj_publikacje_nadrzedna(s1, 2012), w2)

        # Tu testujemy też część algorytmu
        s1 = "W: Carotid artery: costam costam. Pod red. jan BUDNIK "

        w1.tytul_oryginalny = "Carotid artery : costam costam."
        w1.save()
        w2.tytul_oryginalny = "Carotid artery : costam costam. Jeszcze."
        w2.save()

        Opi_2012_Tytul_Cache.objects.rebuild()

        self.assertEquals(zlokalizuj_publikacje_nadrzedna(s1, 2012), w1)


class TestOpi2012MakeZipfile(TestCase):
    exempt_from_fixture_bundling = True

    fixtures = ['um_lublin_uczelnia.json',
                'um_lublin_wydzial.json',
                'um_lublin_charakter_formalny.json',
                'charakter_formalny.json',
                'tytul.json',
                'typ_odpowiedzialnosci.json',
                'typ_kbn.json',
                'jezyk.json',
                'funkcja_autora.json']

    def test_zipfile(self):
        from bpp.reports.opi_2012 import make_report_zipfile


        zipfile = None
        try:
            zipfile = make_report_zipfile(['1WL', '2WL', 'WP', 'WF'])
            self.assert_(zipfile.endswith('.zip'))
        finally:
            if zipfile is not None:
                os.unlink(zipfile)
            else:
                raise Exception("zipfile is None")