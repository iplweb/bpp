# -*- encoding: utf-8 -*-

from django.test import TestCase

from bpp.models.abstract import ILOSC_ZNAKOW_NA_ARKUSZ
from bpp.models.system import Charakter_Formalny, Jezyk, Typ_KBN
from bpp.tests.tests_legacy.test_reports.util import stworz_obiekty_dla_raportow
from bpp.tests.util import (
    CURRENT_YEAR,
    any_autor,
    any_ciagle,
    any_jednostka,
    any_zwarte,
)
from bpp.views.raporty import get_base_query_jednostka, raport_jednostek_tabela


def _query(model, atrybut, wartosc):
    return model.objects.get(**{atrybut: wartosc})


def charakter(skrot):
    # Pobieramy charaktery w ten sposób, za pomocą funkcji GET, a nie za
    # pomocą zapytań typu charakter_formalny__skrot__in [...] ponieważ
    # pobierając pojedynczo charakter dla każdego skrótu dostaniemy błąd
    # jeżeli dany skrót nie odzwierciedla charakteru w bazie danych
    return _query(Charakter_Formalny, "skrot", skrot)


def typ_kbn(skrot):
    return _query(Typ_KBN, "skrot", skrot)


def jezyk(skrot):
    return _query(Jezyk, "skrot", skrot)


class TestRaportJednostek2012(TestCase):
    # fixtures = ["charakter_formalny.json",
    #             "jezyk.json",
    #             "typ_odpowiedzialnosci.json",
    #             "typ_kbn.json",
    #             "status_korekty.json"]

    def setUp(self):
        stworz_obiekty_dla_raportow()
        Charakter_Formalny.objects.get_or_create(skrot="KS", nazwa="Książka")
        Charakter_Formalny.objects.get_or_create(skrot="ROZ", nazwa="Rozdział książki")

        self.j = any_jednostka()
        self.j.refresh_from_db()

        self.j2 = any_jednostka()
        self.j2.refresh_from_db()

        self.a = any_autor()

    def sprawdz(self, klucz, rezultat, cnt=1, not_found=None):
        base_query = get_base_query_jednostka(self.j, CURRENT_YEAR, CURRENT_YEAR)
        q = raport_jednostek_tabela(klucz, base_query, self.j)
        q = list(q)
        self.assertEqual(len(q), cnt)
        self.assertEqual(q[0].original, rezultat)

        if not_found is not None:
            for elem in not_found:
                self.assertNotIn(elem, q)

    def test_1_1(self):
        c = any_ciagle(
            impact_factor=5,
            punktacja_wewnetrzna=0,
            adnotacje="tei",
            typ_kbn=typ_kbn("PO"),
        )
        c.dodaj_autora(self.a, self.j)

        tego_ma_nie_byc = any_ciagle(
            impact_factor=5,
            punktacja_wewnetrzna=0,
            typ_kbn=Typ_KBN.objects.get(skrot="PW"),
        )
        tego_ma_nie_byc.dodaj_autora(self.a, self.j)

        self.sprawdz("1_1", c, not_found=[tego_ma_nie_byc])

    def test_1_1_zakres_lat(self):
        kwargs = dict(
            impact_factor=5,
            punktacja_wewnetrzna=0,
            adnotacje="foo",
            typ_kbn=typ_kbn("PO"),
        )

        c = any_ciagle(**kwargs)
        d = any_ciagle(rok=CURRENT_YEAR + 5, **kwargs)
        e = any_ciagle(rok=CURRENT_YEAR + 6, **kwargs)
        for elem in [c, d, e]:
            elem.dodaj_autora(self.a, self.j)
        base_query = get_base_query_jednostka(self.j, CURRENT_YEAR, CURRENT_YEAR + 5)
        q = raport_jednostek_tabela("1_1", base_query, self.j).order_by("rok")
        self.assertEqual(q.count(), 2)
        self.assertEqual([x.original for x in list(q)], [c, d])

    def test_1_2(self):
        # Ta praca ma WEJŚC
        common = dict(
            charakter_formalny=charakter("AC"),
            jezyk=jezyk("pol."),
            impact_factor=0,
            punkty_kbn=5,
            liczba_znakow_wydawniczych=500,
        )
        c = any_ciagle(adnotacje="", typ_kbn=typ_kbn("PO"), **common)

        tego_ma_nie_byc = any_ciagle(typ_kbn=Typ_KBN.objects.get(skrot="PW"), **common)
        tego_tez_ma_nie_byc = any_ciagle(adnotacje="wos", **common)
        i_jeszcze_tego_tez = any_ciagle(adnotacje="erih", **common)

        for elem in [c, tego_ma_nie_byc, tego_tez_ma_nie_byc, i_jeszcze_tego_tez]:
            elem.dodaj_autora(self.a, self.j)

        self.sprawdz("1_2", c)

    def test_1_3(self):
        c = any_ciagle(adnotacje="erih", punkty_kbn=1)
        c.dodaj_autora(self.a, self.j)

        tego_ma_nie_byc = any_ciagle(uwagi="erih", punkty_kbn=1)
        tego_ma_nie_byc.dodaj_autora(self.a, self.j)

        self.sprawdz("1_3", c)

    def test_1_4(self):
        c = any_ciagle(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="AC"),
            impact_factor=0,
            punkty_kbn=5,
            liczba_znakow_wydawniczych=1 + (ILOSC_ZNAKOW_NA_ARKUSZ / 2),
            jezyk=Jezyk.objects.get(skrot="ang."),
        )
        c.dodaj_autora(self.a, self.j)
        self.sprawdz("1_4", c)

    def test_1_5(self):
        c = any_ciagle(adnotacje="WOS", punkty_kbn=1)
        c.dodaj_autora(self.a, self.j)

        self.sprawdz("1_5", c)

    def test_2_1(self):
        c = any_ciagle(
            charakter_formalny=charakter("KSZ"), jezyk=jezyk("ang."), punkty_kbn=5
        )
        c.dodaj_autora(self.a, self.j)

        d = any_ciagle(
            charakter_formalny=charakter("KSZ"), jezyk=jezyk("ang."), punkty_kbn=5
        )

        d.dodaj_autora(self.a, self.j2)

        self.sprawdz("2_1", c)

    def test_2_2(self):
        c = any_zwarte(charakter_formalny=charakter("ROZ"), punkty_kbn=20)
        c.dodaj_autora(self.a, self.j)
        self.sprawdz("2_2", c)

    def test_2_3(self):
        d = any_zwarte(
            charakter_formalny=charakter("KSZ"), jezyk=jezyk("ang."), punkty_kbn=50
        )
        d.dodaj_autora(self.a, self.j)

        c = any_zwarte(
            charakter_formalny=charakter("KSZ"), jezyk=jezyk("ang."), punkty_kbn=50
        )
        c.dodaj_autora(self.a, self.j, typ_odpowiedzialnosci_skrot="red.")

        self.sprawdz("2_3", c)
