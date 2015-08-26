# -*- encoding: utf-8 -*-
from django.template import Template, Context
from model_mommy import mommy
from django.test import TestCase

from bpp.models import Jednostka, Wydawnictwo_Ciagle, Autor, Praca_Doktorska, Typ_Odpowiedzialnosci
from bpp.models.system import Jezyk
from bpp.templatetags.prace import strip_at_end, znak_na_koncu
from bpp.tests import any_jednostka
from bpp.tests.test_reports.util import autor_ciaglego
from bpp.tests.util import any_doktorat


class TestTemplateTags(TestCase):

    fixtures = ['typ_odpowiedzialnosci.json', 'charakter_formalny.json',
                'tytul.json']

    def setUp(self):
        j = any_jednostka()

        a1 = mommy.make(Autor, nazwisko='Kowalski', imiona='Jan', tytul=None, slug='A')
        a2 = mommy.make(Autor, nazwisko='Nowak', imiona='Jan', tytul=None, slug='B')
        a3 = mommy.make(Autor, nazwisko='Nowak', imiona='Jan', tytul=None, slug='C')

        c = mommy.make(Wydawnictwo_Ciagle, tytul="foo", tytul_oryginalny="bar", uwagi='fo', jezyk=Jezyk.objects.all()[0])
        t = Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
        autor_ciaglego(a1, j, c, zapisany_jako='Jan Budnik', typ_odpowiedzialnosci=t, kolejnosc=1)
        autor_ciaglego(a2, j, c, zapisany_jako='Stefan Kolbe', typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='red.'), kolejnosc=2)
        autor_ciaglego(a3, j, c, zapisany_jako='Testowy Autor', kolejnosc=-1, typ_odpowiedzialnosci=t)

        self.ciagle = c

        self.doktorat = any_doktorat(tytul_oryginalny='wtf', tytul='lol', autor=a1)

    def test_autorzy(self):
        template = '''
        {% load prace %}
        {% autorzy praca %}
        '''

        t = Template(template)
        c = Context({"praca": self.ciagle})
        ret = t.render(c).strip()
        self.assertEquals(ret, "[aut.] Testowy Autor, Jan Budnik, [red.] Stefan Kolbe.".upper())

        c = Context({"praca": self.doktorat})
        ret = t.render(c).strip()
        # unicode(self.doktorat.autor)
        self.assertEquals(ret, "[AUT.] KOWALSKI JAN.")

    def test_autorzy_z_linkami(self):
        template = '''
        {% load prace %}
        {% autorzy_z_linkami praca %}
        '''

        t = Template(template)
        c = Context({"praca": self.ciagle})
        ret = t.render(c).strip()
        self.assertEquals(ret,  u'[AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, <a href="/bpp/autor/A/">Jan Budnik</a>, [RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>.')

        c = Context({"praca": self.doktorat})
        ret = t.render(c).strip()
        self.assertEquals(ret,  u'[AUT.] <a href="/bpp/autor/A/">Kowalski Jan</a>.')

    def test_strip_at_end(self):
        self.assertEquals(
            "foo",
            strip_at_end("foo.,.,.,"))

    def test_znak_na_koncu(self):
        self.assertEquals(
            "foo.",
            znak_na_koncu("foo.,.,", "."))

        self.assertEquals(
            "",
            znak_na_koncu(".,.,", "."))

        self.assertEquals(None, znak_na_koncu(None, ",."))


    def test_znak_na_koncu(self):
        template = '''
        {% load prace %}
        {{ ciag_znakow|znak_na_koncu:", " }}
        '''

        t = Template(template)
        c = Context({"ciag_znakow": "loll..."})
        ret = t.render(c).strip()
        self.assertEquals(ret, "loll,")

    def test_znak_na_poczatku(self):
        template = '''
        {% load prace %}
        {{ ciag_znakow|znak_na_poczatku:"," }}
        '''

        t = Template(template)
        c = Context({"ciag_znakow": "loll"})
        ret = t.render(c).strip()
        self.assertEquals(ret, ", loll")

    def test_ladne_numery_prac(self):
        template = '''
        {% load prace %}
        {{ arr|ladne_numery_prac }}
        '''

        t = Template(template)
        c = Context({"arr": set([1, 2, 3, 4, 5, 10, 11, 12, 15, 16, 20, 25,
                                 30, 31, 32, 33])})
        ret = t.render(c).strip()
        self.assertEquals(ret, "1-5, 10-12, 15-16, 20, 25, 30-33")

        c = Context({"arr": set([1, 3, 4, 5])})
        ret = t.render(c).strip()
        self.assertEquals(ret, "1, 3-5")
