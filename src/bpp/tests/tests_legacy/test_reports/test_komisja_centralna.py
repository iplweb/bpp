# -*- encoding: utf-8 -*-
import os
import sys
import tempfile
from zipfile import ZipFile

from django.test import TestCase
from model_mommy import mommy

from bpp.models import (
    Typ_KBN,
    Charakter_Formalny,
    Zasieg_Zrodla,
    Zrodlo,
    Redakcja_Zrodla,
    Tytul,
    Rekord,
)
from bpp.models.autor import Autor
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from bpp.models.system import Jezyk
from bpp.reports.komisja_centralna import (
    RaportKomisjiCentralnej,
    get_queries,
    RokHabilitacjiNiePodany,
    make_report_zipfile,
    Raport_Dla_Komisji_Centralnej,
)
from bpp.tests.tests_legacy.test_reports.util import stworz_obiekty_dla_raportow
from bpp.tests.util import (
    any_jednostka,
    any_autor,
    CURRENT_YEAR,
    any_ciagle,
    any_patent,
    any_zwarte,
    any_habilitacja,
)
from bpp.util import Getter
from celeryui.models import Report


class TestRKCMixin:
    def odpal_browser(self, res):
        handle, fn = tempfile.mkstemp(".html")
        os.write(handle, res.encode("utf-8"))
        os.close(handle)

        if sys.platform == "win32":
            os.system("start %s" % fn)
        if sys.platform == "darwin":
            os.system('open "%s"' % fn)


class TestRaportKomisjiCentralnej(TestRKCMixin, TestCase):
    def setUp(self):
        stworz_obiekty_dla_raportow()

        typ_kbn = Getter(Typ_KBN)
        charakter = Getter(Charakter_Formalny)
        zasieg = Getter(Zasieg_Zrodla, "nazwa")
        tytul = Getter(Tytul)
        jezyk = Getter(Jezyk)

        self.jednostka = any_jednostka()

        self.autor = any_autor()

        self.prace = {}

        self.krajowe_zrodlo = mommy.make(Zrodlo, zasieg=zasieg.krajowy)
        Redakcja_Zrodla.objects.create(
            zrodlo=self.krajowe_zrodlo, redaktor=self.autor, od_roku=CURRENT_YEAR
        )

        self.miedzynarodowe_zrodlo = mommy.make(Zrodlo, zasieg=zasieg["międzynarodowy"])
        Redakcja_Zrodla.objects.create(
            zrodlo=self.miedzynarodowe_zrodlo, redaktor=self.autor, od_roku=CURRENT_YEAR
        )

        def dwie(idx, tytul_oryginalny, **kw):
            self.prace[idx] = any_ciagle(tytul_oryginalny=tytul_oryginalny, **kw)

            self.prace[idx + "-2"] = any_ciagle(
                tytul_oryginalny=tytul_oryginalny + "-2", **kw
            )

        args_1a = dict(
            typ_kbn=typ_kbn.PO,
            charakter_formalny=charakter.AC,
            impact_factor=10,
            punkty_kbn=5,
        )
        dwie("1a", "Praca-1", **args_1a)

        args_1b = dict(
            typ_kbn=typ_kbn.PO,
            charakter_formalny=charakter.AC,
            impact_factor=0,
            punkty_kbn=5,
        )
        dwie("1b", "Praca-2", **args_1b)

        args_2a = dict(
            impact_factor=5,
            typ_kbn=typ_kbn.CR,
            charakter_formalny=charakter.AC,
            punkty_kbn=5,
        )
        dwie("2a", "Praca-3", **args_2a)

        args_2b = dict(
            impact_factor=0,
            typ_kbn=typ_kbn.CR,
            charakter_formalny=charakter.AC,
            punkty_kbn=5,
        )
        dwie("2b", "Praca-4", **args_2b)

        args_3a = dict(
            impact_factor=5,
            typ_kbn=typ_kbn.PP,
            punkty_kbn=5,
            charakter_formalny=charakter.AC,
        )
        dwie("3a", "Praca-5", **args_3a)

        args_3b = dict(
            impact_factor=0,
            typ_kbn=typ_kbn.PP,
            charakter_formalny=charakter.AC,
            punkty_kbn=5,
        )
        dwie("3b", "Praca-6", **args_3b)

        # args_4
        dwie(
            "4c1", "Praca-6.5", charakter_formalny=charakter["KSZ"], jezyk=jezyk["ang."]
        )
        dwie(
            "4c2",
            "Praca-6.75",
            charakter_formalny=charakter["KSP"],
            jezyk=jezyk["pol."],
        )

        # args_5
        dwie("5", "Praca-7", typ_kbn=typ_kbn["000"], charakter_formalny=charakter.AC)
        dwie("5a", "Praca-7a", typ_kbn=typ_kbn["PNP"])
        any_habilitacja(tytul_oryginalny="NIE WEJDZIE")
        any_habilitacja(tytul_oryginalny="NIE WEJDZIE")
        any_habilitacja(tytul_oryginalny="NIE WEJDZIE")

        p = any_patent()
        h = any_habilitacja(tytul_oryginalny="WEJDZIE")
        Publikacja_Habilitacyjna.objects.create(praca_habilitacyjna=h, publikacja=p)

        # 7a
        args_7a = dict(jezyk=jezyk["ang."], charakter_formalny=charakter.KSZ)
        any_zwarte(tytul_oryginalny="PRACA 7a", **args_7a).dodaj_autora(
            self.autor, self.jednostka, typ_odpowiedzialnosci_skrot="red."
        )

        # Praca 7a nie wejdzie do punktu 7a, ale do 4c1 już tak :-)
        any_zwarte(tytul_oryginalny="PRACA 7a NIE MA", **args_7a).dodaj_autora(
            self.autor, self.jednostka, typ_odpowiedzialnosci_skrot="aut."
        )
        # 7b
        any_zwarte(
            tytul_oryginalny="PRACA 7b1",
            jezyk=jezyk["pol."],
            charakter_formalny=charakter.KSZ,
        ).dodaj_autora(self.autor, self.jednostka, typ_odpowiedzialnosci_skrot="red.")

        any_zwarte(
            tytul_oryginalny="PRACA 7b2",
            jezyk=jezyk["pol."],
            charakter_formalny=charakter.KSP,
        ).dodaj_autora(self.autor, self.jednostka, typ_odpowiedzialnosci_skrot="red.")

        # dodam autora o typie redaktor
        # stworze prace o takich samych argumentach ale bez redaktora

        args_8a = dict(charakter_formalny=charakter.ZSZ)
        dwie("8a", "Praca-8", **args_8a)

        args_8b = dict(charakter_formalny=charakter.PSZ)
        dwie("8b", "Praca-9", **args_8b)

        self.prace["9a"] = any_ciagle(
            charakter_formalny=charakter.Supl,
            impact_factor=0,
            punkty_kbn=111,
            kc_impact_factor=222,
            kc_punkty_kbn=None,
            tytul_oryginalny="Praca-10 ma mieć IMPACT 222 i KBN 111",
        )

        self.prace["9a-1"] = any_ciagle(
            charakter_formalny=charakter.Supl,
            impact_factor=5,
            punkty_kbn=111,
            kc_impact_factor=222,
            kc_punkty_kbn=444,
            tytul_oryginalny="Praca-10 ma mieć IMPACT 222 i KBN 444",
        )

        #
        self.prace["9b"] = any_ciagle(
            charakter_formalny=charakter.Supl,
            impact_factor=0,
            punkty_kbn=0,
            kc_impact_factor=None,
            kc_punkty_kbn=333,
            tytul_oryginalny="Praca-11 ma mieć KBN 333 i ZERO impactu",
        )

        self.prace["9b-1"] = any_ciagle(
            charakter_formalny=charakter.Supl,
            impact_factor=0,
            punkty_kbn=1,
            kc_impact_factor=None,
            kc_punkty_kbn=555,
            tytul_oryginalny="Praca-11 ma mieć KBN 555 i ZERO impactu",
        )

        args_10a = dict(charakter_formalny=charakter.L, impact_factor=5, punkty_kbn=5)
        dwie("10a", "Praca-12", **args_10a)

        args_10b = dict(charakter_formalny=charakter.L, impact_factor=0, punkty_kbn=5)
        dwie("10b", "Praca-13", **args_10b)

        args_11a = dict(typ_kbn=typ_kbn.PW, impact_factor=5, punkty_kbn=5)
        dwie("11a", "Praca-14", **args_11a)

        args_11b = dict(typ_kbn=typ_kbn.PW, impact_factor=0, punkty_kbn=5)
        dwie("11b", "Praca-15", **args_11b)

        self.prace["IIIpat"] = any_patent(tytul_oryginalny="Praca-16")

        # Przebuduj opisy bibliograficzne
        for c in Rekord.objects.all():
            c.original.zaktualizuj_cache(tylko_opis=True)

        for praca in list(self.prace.values()):
            praca.dodaj_autora(self.autor, self.jednostka)

        Rekord.objects.full_refresh()

        self._zrob()

    def _zrob(self):
        self.raport = RaportKomisjiCentralnej(self.autor)
        self.s = self.raport.make_prace()
        return self.s

    def _test_tabelka(self, key):
        # s = self._zrob()
        # self.odpal_browser(s)
        self.assertIn(self.prace[key].tytul_oryginalny, self.s)

    test_1a = lambda self: self._test_tabelka("1a")
    test_1b = lambda self: self._test_tabelka("1b")

    test_2a = lambda self: self._test_tabelka("2a")
    test_2b = lambda self: self._test_tabelka("2b")

    test_3a = lambda self: self._test_tabelka("3a")
    test_3b = lambda self: self._test_tabelka("3b")

    def test_4c(self):
        haystack = self._zrob().replace("\r\n", "").replace("\t", "")
        for a in range(10):
            haystack = haystack.replace("  ", " ")

        needles = [
            "C. Autorstwo monografii lub podręcznika:\n </td><td>liczba: 5",
            "C1. w języku angielskim\n </td><td>liczba: 3",
            "C2. w języku polskim lub innym niż angielski\n </td><td>liczba: 2",
        ]
        self.assertIn(needles[0], haystack)
        self.assertIn(needles[1], haystack)
        self.assertIn(needles[2], haystack)

    def test_5(self):
        s = self._zrob()
        self.assertIn("naukowe i inne, liczba prac: 5", s)

    def test_6(self):
        s = self._zrob()
        self.assertIn("A. międzynarodowym</td><td>liczba: 1", s)
        self.assertIn("B. krajowym</td><td>liczba: 1", s)

    def test_7(self):
        s = self._zrob()
        self.assertIn("A. w języku angielskim</td><td>liczba: 1", s)
        self.assertIn(
            "B. w języku polskim lub innym, niż angielski</td><td>liczba: 2", s
        )

    def test_8(self):
        s = self._zrob()
        self.assertIn("Liczba streszczeń: 4", s)
        self.assertIn("A. ze zjazd\xf3w mi\u0119dzynarodowych</td><td>liczba: 2", s)
        self.assertIn("B. ze zjazd\xf3w krajowych</td><td>liczba: 2", s)

    def test_9(self):
        for a in ["111", "222", "333", "444", "555", "888"]:  #  <-- to są sumy
            self.assertIn(a, self._zrob())

    def test_10a(self):
        self._test_tabelka("10a")

    def test_10b(self):
        self._test_tabelka("10b")

    def test_10_suma(self):
        s = self._zrob()
        self.assertIn("X. Liczba listów do redakcji czasopism: 4", s)

    test_11a = lambda self: self._test_tabelka("11a")
    test_11b = lambda self: self._test_tabelka("11b")

    def test_11_suma(self):
        s = self._zrob()
        self.assertIn("XI. Liczba publikacji z udzia", s)
        self.assertIn("wieloośrodkowych: 4", s)

    def test_punktacja_sumaryczna(self):
        self.s = self._zrob()
        dct = self.raport.policz_sumy()

        def sprawdz_sumy(no, oczekiwany_count, oczekiwany_if, oczekiwany_pk):
            key = "suma_%s" % no

            self.assertEqual(dct.get(key)["count"], oczekiwany_count, msg=key)
            self.assertEqual(dct.get(key)["impact_factor"], oczekiwany_if, msg=key)
            self.assertEqual(dct.get(key)["punkty_kbn"], oczekiwany_pk, msg=key)

        sprawdz_sumy(1, 4, 20, 20)
        sprawdz_sumy(2, 4, 10, 20)
        sprawdz_sumy(3, 4, 10, 20)
        sprawdz_sumy(9, 4, 444, 1443)
        sprawdz_sumy(10, 4, 10, 20)
        sprawdz_sumy(11, 4, 10, 20)
        self.assertEqual(dct["suma_5"]["count"], 5)
        self.assertEqual(dct["suma_8"]["count"], 4)

    def test_punktacja_sumaryczna_render(self):
        res = self.raport.punktacja_sumaryczna()
        self.assertIn("doktora habilitowanego", res)
        # self.odpal_browser(res)


class TestRaportKomisjiCentralnejPrzedPoHabilitacji(TestRKCMixin, TestCase):
    def setUp(self):
        stworz_obiekty_dla_raportow()

        typ_kbn = Getter(Typ_KBN)
        charakter = Getter(Charakter_Formalny)
        zasieg = Getter(Zasieg_Zrodla, "nazwa")
        tytul = Getter(Tytul)
        jezyk = Getter(Jezyk)

        self.jednostka = any_jednostka()
        self.habilitowany = any_autor()

        args_1a = dict(
            typ_kbn=typ_kbn.PO,
            charakter_formalny=charakter.AC,
            impact_factor=10,
            punkty_kbn=5,
        )

        self.praca_przed = any_ciagle(
            tytul_oryginalny="Praca-PRZED", rok=CURRENT_YEAR, **args_1a
        )
        self.praca_przed.dodaj_autora(self.habilitowany, self.jednostka)

        self.praca_po = any_ciagle(
            tytul_oryginalny="Praca-PO", rok=CURRENT_YEAR + 1, **args_1a
        )
        self.praca_po.dodaj_autora(self.habilitowany, self.jednostka)

        Rekord.objects.full_refresh()

        self.raport_przed = RaportKomisjiCentralnej(
            self.habilitowany, przed_habilitacja=True, rok_habilitacji=CURRENT_YEAR
        )

        self.raport_po = RaportKomisjiCentralnej(
            self.habilitowany, przed_habilitacja=False, rok_habilitacji=CURRENT_YEAR
        )

    def test_raport_przed(self):
        s = self.raport_przed.make_prace()
        res = self.raport_przed.dct
        self.assertEqual(res["tabela_1a"].counter, 1)
        self.assertEqual(res["tabela_1a"].columns["impact_factor"].footer, 10)
        self.assertIn("Praca-PRZED", s)
        self.assertIn("Dorobek przedhabilitacyjny", s)
        self.assertIn("profesora", s)

    def test_raport_po(self):
        s = self.raport_po.make_prace()
        res = self.raport_po.dct
        self.assertEqual(res["tabela_1a"].counter, 1)
        self.assertEqual(res["tabela_1a"].columns["impact_factor"].footer, 10)
        self.assertIn("Praca-PO", s)
        self.assertIn("Dorobek pohabilitacyjny", s)
        self.assertIn("profesora", s)

    def test_po_raises(self):
        self.assertRaises(
            RokHabilitacjiNiePodany,
            get_queries,
            self.habilitowany,
            przed_habilitacja=False,
            rok_habilitacji=None,
        )


class TestRaportKomisjiCentralnejZipfile(TestRKCMixin, TestCase):
    def setUp(self):
        stworz_obiekty_dla_raportow()

        typ_kbn = Getter(Typ_KBN)
        charakter = Getter(Charakter_Formalny)
        zasieg = Getter(Zasieg_Zrodla, "nazwa")
        tytul = Getter(Tytul)
        jezyk = Getter(Jezyk)

        self.jednostka = any_jednostka()
        # Takie nazwisko, bo używamy potem autor.slug do wygnerowania nazwy pliku
        self.habilitowany = any_autor(
            nazwisko="Łącki 'al' \"Habib\" ", imiona="Jąń??\\/", tytul=tytul["dr"]
        )

        # Odbuduj sluga
        self.habilitowany.slug = None
        self.habilitowany.save()

        args_1a = dict(
            typ_kbn=typ_kbn.PO,
            charakter_formalny=charakter.AC,
            impact_factor=10,
            punkty_kbn=5,
        )

        self.praca_przed = any_ciagle(
            tytul_oryginalny="Praca-PRZED", rok=CURRENT_YEAR, **args_1a
        )
        self.praca_przed.dodaj_autora(self.habilitowany, self.jednostka)

        self.praca_po = any_ciagle(
            tytul_oryginalny="Praca-PO", rok=CURRENT_YEAR + 1, **args_1a
        )
        self.praca_po.dodaj_autora(self.habilitowany, self.jednostka)

    def test_make_zipfile(self):
        zn = make_report_zipfile(self.habilitowany.pk, CURRENT_YEAR)
        with ZipFile(zn, "r") as zip:
            self.assertEqual(len(zip.infolist()), 6)

    def test_make_zipfile_bez_habilitacji(self):
        zn = make_report_zipfile(self.habilitowany.pk, None)
        with ZipFile(zn, "r") as zip:
            self.assertEqual(len(zip.infolist()), 3)

    def test_raport_dla_komisji_centralnej(self):
        autor = mommy.make(Autor)
        r = mommy.make(Report, arguments={"rok_habilitacji": "2017", "autor": autor.pk})
        x = Raport_Dla_Komisji_Centralnej(r)
        x.perform()

        y = r.file.open()
        self.assert_(True)
