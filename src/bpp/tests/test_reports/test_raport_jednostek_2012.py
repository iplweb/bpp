# -*- encoding: utf-8 -*-
from django.db import transaction

from django.test import TestCase
from bpp.models import cache
from bpp.models.cache import with_cache
from bpp.models.system import Charakter_Formalny, Jezyk, Typ_KBN
from bpp.tests.util import any_jednostka, any_autor, any_ciagle, CURRENT_YEAR, any_zwarte
from bpp.views.raporty import get_base_query_jednostka, raport_jednostek_tabela


def _query(model, atrybut, wartosc):
    return model.objects.get(**{atrybut:wartosc})

def charakter(skrot):
    # Pobieramy charaktery w ten sposób, za pomocą funkcji GET, a nie za
    # pomocą zapytań typu charakter_formalny__skrot__in [...] ponieważ
    # pobierając pojedynczo charakter dla każdego skrótu dostaniemy błąd
    # jeżeli dany skrót nie odzwierciedla charakteru w bazie danych
    return _query(Charakter_Formalny, 'skrot', skrot)


def jezyk(skrot):
    return _query(Jezyk, 'skrot', skrot)

class TestRaportJednostek2012(TestCase):
    # fixtures = ["charakter_formalny.json",
    #             "jezyk.json",
    #             "typ_odpowiedzialnosci.json",
    #             "typ_kbn.json",
    #             "status_korekty.json"]

    def setUp(self):
        self.j = any_jednostka()
        self.j2 = any_jednostka()
        self.a = any_autor()

    def sprawdz(self, klucz, rezultat, cnt=1, not_found=None):
        base_query = get_base_query_jednostka(self.j, CURRENT_YEAR, CURRENT_YEAR)
        q = raport_jednostek_tabela(klucz, base_query, self.j)
        q = list(q)
        self.assertEquals(len(q), cnt)
        self.assertEquals(q[0].original, rezultat)

        if not_found is not None:
            for elem in not_found:
                self.assertNotIn(elem, q)

    @with_cache
    def test_1_1(self):
        c = any_ciagle(
            impact_factor=5,
            punktacja_wewnetrzna=0)
        c.dodaj_autora(self.a, self.j)

        tego_ma_nie_byc = any_ciagle(
            impact_factor=5,
            punktacja_wewnetrzna=0,
            typ_kbn=Typ_KBN.objects.get(skrot="PW"))
        tego_ma_nie_byc.dodaj_autora(self.a, self.j)

        self.sprawdz("1_1", c, not_found=[tego_ma_nie_byc])

    @with_cache
    def test_1_1_zakres_lat(self):
        c = any_ciagle(impact_factor=5, punktacja_wewnetrzna=0)
        d = any_ciagle(impact_factor=5, punktacja_wewnetrzna=0, rok=CURRENT_YEAR+5)
        e = any_ciagle(impact_factor=5, punktacja_wewnetrzna=0, rok=CURRENT_YEAR+6)
        for elem in [c,d,e]:
            elem.dodaj_autora(self.a, self.j)
        base_query = get_base_query_jednostka(self.j, CURRENT_YEAR, CURRENT_YEAR + 5)
        q = raport_jednostek_tabela("1_1", base_query, self.j).order_by('rok')
        self.assertEquals(q.count(), 2)
        self.assertEquals([x.original for x in list(q)], [c, d])

    @with_cache
    def test_1_2(self):
        common = dict(charakter_formalny=charakter("AC"),
            jezyk=jezyk("pol."),
            impact_factor=0,
            punkty_kbn=5)
        c = any_ciagle(adnotacje="", **common)

        tego_ma_nie_byc = any_ciagle(typ_kbn=Typ_KBN.objects.get(skrot="PW"), **common)
        tego_tez_ma_nie_byc = any_ciagle(adnotacje="wos", **common)
        i_jeszcze_tego_tez = any_ciagle(adnotacje="erih", **common)

        for elem in [c, tego_ma_nie_byc, tego_tez_ma_nie_byc, i_jeszcze_tego_tez]:
            elem.dodaj_autora(self.a, self.j)

        self.sprawdz("1_2", c)

    @with_cache
    def test_1_3(self):
        c = any_ciagle(
            adnotacje="erih",
            punkty_kbn=1)
        c.dodaj_autora(self.a, self.j)

        tego_ma_nie_byc = any_ciagle(
            uwagi="erih",
            punkty_kbn=1)
        tego_ma_nie_byc.dodaj_autora(self.a, self.j)

        self.sprawdz("1_3", c)

    @with_cache
    def test_1_4(self):
        c = any_ciagle(
            adnotacje="WOS",
            punkty_kbn=1)
        c.dodaj_autora(self.a, self.j)

        self.sprawdz("1_4", c)

    @with_cache
    def test_2_1(self):
        c = any_ciagle(
            charakter_formalny=charakter("KSZ"),
            jezyk=jezyk("ang."),
            punkty_kbn=5)
        c.dodaj_autora(self.a, self.j)

        d = any_ciagle(
            charakter_formalny=charakter("KSZ"),
            jezyk=jezyk("ang."),
            punkty_kbn=5)

        d.dodaj_autora(self.a, self.j2)

        self.sprawdz("2_1", c)

    @with_cache
    def test_2_2(self):
        c = any_ciagle(
            charakter_formalny=charakter("KSP"),
            punkty_kbn=50
        )
        c.dodaj_autora(self.a, self.j)
        self.sprawdz("2_2", c)

    @with_cache
    def test_2_3(self):
        c = any_zwarte(
            charakter_formalny=charakter("ROZ"),
            jezyk=jezyk("ang."),
            punkty_kbn=20
        )
        c.dodaj_autora(self.a, self.j)
        self.sprawdz("2_3", c)

    @with_cache
    def test_2_4(self):
        c = any_zwarte(
            charakter_formalny=charakter("ROZ"),
            jezyk=jezyk("pol."),
            punkty_kbn=20
        )
        c.dodaj_autora(self.a, self.j)
        self.sprawdz("2_4", c)

    @with_cache
    def test_2_5(self):
        d = any_zwarte(
            charakter_formalny=charakter("KSZ"),
            jezyk=jezyk('ang.'),
            punkty_kbn=50
        )
        d.dodaj_autora(self.a, self.j)

        c = any_zwarte(
            charakter_formalny=charakter("KSZ"),
            jezyk=jezyk('ang.'),
            punkty_kbn=50
        )
        c.dodaj_autora(self.a, self.j, typ_odpowiedzialnosci_skrot="red.")

        self.sprawdz("2_5", c)

    @with_cache
    def test_2_6(self):
        d = any_zwarte(
            charakter_formalny=charakter("KSP"),
            jezyk=jezyk('pol.'),
            punkty_kbn=50
        )
        d.dodaj_autora(self.a, self.j)

        c = any_zwarte(
            charakter_formalny=charakter("KSP"),
            jezyk=jezyk('pol.'),
            punkty_kbn=50
        )
        c.dodaj_autora(self.a, self.j, typ_odpowiedzialnosci_skrot="red.")
        self.sprawdz("2_6", c)