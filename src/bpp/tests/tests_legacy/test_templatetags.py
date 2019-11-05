# -*- encoding: utf-8 -*-
from django.template import Template, Context
from django.template.loader import get_template
from model_mommy import mommy
from django.test import TestCase

from bpp.models import Jednostka, Wydawnictwo_Ciagle, Autor, Praca_Doktorska, Typ_Odpowiedzialnosci
from bpp.models.system import Jezyk
from bpp.templatetags.prace import strip_at_end, znak_na_koncu
from bpp.tests.util import any_jednostka
from bpp.tests.tests_legacy.test_reports.util import autor_ciaglego
from bpp.tests.util import any_doktorat


class TestTemplateTags(TestCase):

    # fixtures = ['typ_odpowiedzialnosci.json', 'charakter_formalny.json',
    #             'tytul.json']

    def setUp(self):
        j = any_jednostka()

        a1 = mommy.make(Autor, nazwisko='Kowalski', imiona='Jan', tytul=None, slug='A')
        a2 = mommy.make(Autor, nazwisko='Nowak', imiona='Jan', tytul=None, slug='B')
        a3 = mommy.make(Autor, nazwisko='Nowak', imiona='Jan', tytul=None, slug='C')

        self.a1 = a1
        self.a2 = a2
        self.a3 = a3

        jezyk = mommy.make(Jezyk)
        c = mommy.make(Wydawnictwo_Ciagle, tytul="foo", tytul_oryginalny="bar", uwagi='fo', jezyk=jezyk)
        t, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(skrot='aut.', nazwa='autor')
        _ign, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(skrot='red.', nazwa='redaktor')
        autor_ciaglego(a1, j, c, zapisany_jako='Jan Budnik', typ_odpowiedzialnosci=t, kolejnosc=1)
        autor_ciaglego(a2, j, c, zapisany_jako='Stefan Kolbe', typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='red.'), kolejnosc=2)
        autor_ciaglego(a3, j, c, zapisany_jako='Testowy Autor', kolejnosc=-1, typ_odpowiedzialnosci=t)

        self.ciagle = c

        self.doktorat = any_doktorat(tytul_oryginalny='wtf', tytul='lol', autor=a1, jezyk=jezyk)

    def test_autorzy(self):
        t = get_template("opis_bibliograficzny/autorzy.html")
        c = {"praca": self.ciagle, "autorzy": self.ciagle.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret, "[aut.] Testowy Autor, Jan Budnik, [red.] Stefan Kolbe.".upper())

    def test_autorzy_doktorat(self):
        t = get_template("opis_bibliograficzny/autorzy.html")
        c = {"praca": self.doktorat, "autorzy": self.doktorat.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret, "[AUT.] KOWALSKI JAN.")

    def test_autorzy_z_linkami_tekst_przed_po(self):
        t = get_template("opis_bibliograficzny/autorzy.html")
        self.ciagle.tekst_przed_pierwszym_autorem = "PRZED"
        self.ciagle.tekst_po_ostatnim_autorze = "PO"

        c = {"praca": self.ciagle, "links": "normal", "autorzy": self.ciagle.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret,  'PRZED[AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, <a href="/bpp/autor/A/">Jan Budnik</a>, [RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>PO.')


    def test_autorzy_z_linkami(self):
        t = get_template("opis_bibliograficzny/autorzy.html")

        c = {"praca": self.ciagle, "links": "normal", "autorzy": self.ciagle.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret,  '[AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, <a href="/bpp/autor/A/">Jan Budnik</a>, [RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>.')

        c = {"praca": self.ciagle, "links": "admin", "autorzy": self.ciagle.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret,  '[AUT.] <a href="/admin/bpp/autor/%i/change/">Testowy Autor</a>, <a href="/admin/bpp/autor/%i/change/">Jan Budnik</a>, [RED.] <a href="/admin/bpp/autor/%i/change/">Stefan Kolbe</a>.' % (
            self.a3.pk, self.a1.pk, self.a2.pk
        ))

        c = {"praca": self.doktorat, "links": "normal", "autorzy": self.doktorat.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret,  '[AUT.] <a href="/bpp/autor/A/">Kowalski Jan</a>.')

        c = {"praca": self.doktorat, "links": "admin", "autorzy": self.doktorat.autorzy_dla_opisu()}
        ret = t.render(c).strip()
        self.assertEqual(ret,  '[AUT.] <a href="/admin/bpp/autor/%i/change/">Kowalski Jan</a>.' % self.doktorat.autor.pk)

    def test_strip_at_end(self):
        self.assertEqual(
            "foo",
            strip_at_end("foo.,.,.,"))

    def test_znak_na_koncu(self):
        self.assertEqual(
            "foo.",
            znak_na_koncu("foo.,.,", "."))

        self.assertEqual(
            "",
            znak_na_koncu(".,.,", "."))

        self.assertEqual(None, znak_na_koncu(None, ",."))


    def test_znak_na_koncu(self):
        template = '''
        {% load prace %}
        {{ ciag_znakow|znak_na_koncu:", " }}
        '''

        t = Template(template)
        c = Context({"ciag_znakow": "loll..."})
        ret = t.render(c).strip()
        self.assertEqual(ret, "loll,")

    def test_znak_na_poczatku(self):
        template = '''
        {% load prace %}
        {{ ciag_znakow|znak_na_poczatku:"," }}
        '''

        t = Template(template)
        c = Context({"ciag_znakow": "loll"})
        ret = t.render(c).strip()
        self.assertEqual(ret, ", loll")

    def test_ladne_numery_prac(self):
        template = '''
        {% load prace %}
        {{ arr|ladne_numery_prac }}
        '''

        t = Template(template)
        c = Context({"arr": set([1, 2, 3, 4, 5, 10, 11, 12, 15, 16, 20, 25,
                                 30, 31, 32, 33])})
        ret = t.render(c).strip()
        self.assertEqual(ret, "1-5, 10-12, 15-16, 20, 25, 30-33")

        c = Context({"arr": set([1, 3, 4, 5])})
        ret = t.render(c).strip()
        self.assertEqual(ret, "1, 3-5")
