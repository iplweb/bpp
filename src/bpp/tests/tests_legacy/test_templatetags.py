from django.template import Context, Template
from django.test import TestCase
from model_bakery import baker

from bpp.models import Autor, Typ_Odpowiedzialnosci, Wydawnictwo_Ciagle
from bpp.models.system import Jezyk
from bpp.templatetags.prace import strip_at_end, znak_na_koncu
from bpp.tests.tests_legacy.test_reports.util import autor_ciaglego
from bpp.tests.util import any_doktorat, any_jednostka


class TestTemplateTags(TestCase):

    # fixtures = ['typ_odpowiedzialnosci.json', 'charakter_formalny.json',
    #             'tytul.json']

    def setUp(self):
        j = any_jednostka()

        a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", tytul=None, slug="A")
        a2 = baker.make(Autor, nazwisko="Nowak", imiona="Jan", tytul=None, slug="B")
        a3 = baker.make(Autor, nazwisko="Nowak", imiona="Jan", tytul=None, slug="C")

        self.a1 = a1
        self.a2 = a2
        self.a3 = a3

        jezyk = baker.make(Jezyk)
        c = baker.make(
            Wydawnictwo_Ciagle,
            tytul="foo",
            tytul_oryginalny="bar",
            uwagi="fo",
            jezyk=jezyk,
        )
        t, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(
            skrot="aut.", nazwa="autor"
        )
        _ign, _ign = Typ_Odpowiedzialnosci.objects.get_or_create(
            skrot="red.", nazwa="redaktor"
        )
        autor_ciaglego(
            a1, j, c, zapisany_jako="Jan Budnik", typ_odpowiedzialnosci=t, kolejnosc=1
        )
        autor_ciaglego(
            a2,
            j,
            c,
            zapisany_jako="Stefan Kolbe",
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="red."),
            kolejnosc=2,
        )
        autor_ciaglego(
            a3,
            j,
            c,
            zapisany_jako="Testowy Autor",
            kolejnosc=-1,
            typ_odpowiedzialnosci=t,
        )

        self.ciagle = c

        self.doktorat = any_doktorat(
            tytul_oryginalny="wtf", tytul="lol", autor=a1, jezyk=jezyk
        )

    def test_autorzy(self):
        self.assertIn(
            "[aut.] Testowy Autor, Jan Budnik, [red.] Stefan Kolbe.".upper(),
            self.ciagle.opis_bibliograficzny(),
        )

    def test_autorzy_doktorat(self):
        self.assertIn("[AUT.] KOWALSKI JAN.", self.doktorat.opis_bibliograficzny())

    def test_autorzy_z_linkami_tekst_przed_po(self):
        self.ciagle.tekst_przed_pierwszym_autorem = "PRZED"
        self.ciagle.tekst_po_ostatnim_autorze = "PO"

        self.assertIn(
            'PRZED [AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, <a href="/bpp/autor/A/">Jan Budnik</a>, '
            '[RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>PO.',
            self.ciagle.opis_bibliograficzny(links="normal"),
        )

    def test_autorzy_z_linkami(self):
        self.assertIn(
            '[AUT.] <a href="/bpp/autor/C/">Testowy Autor</a>, <a href="/bpp/autor/A/">Jan Budnik</a>, '
            '[RED.] <a href="/bpp/autor/B/">Stefan Kolbe</a>.',
            self.ciagle.opis_bibliograficzny(links="normal"),
        )

        self.assertIn(
            '[AUT.] <a href="/admin/bpp/autor/%i/change/">Testowy Autor</a>, '
            '<a href="/admin/bpp/autor/%i/change/">Jan Budnik</a>, '
            '[RED.] <a href="/admin/bpp/autor/%i/change/">Stefan Kolbe</a>.'
            % (self.a3.pk, self.a1.pk, self.a2.pk),
            self.ciagle.opis_bibliograficzny(links="admin"),
        )

        self.assertIn(
            '[AUT.] <a href="/bpp/autor/A/">Kowalski Jan</a>.',
            self.doktorat.opis_bibliograficzny(links="normal"),
        )

        self.assertIn(
            '[AUT.] <a href="/admin/bpp/autor/%i/change/">Kowalski Jan</a>.'
            % self.doktorat.autor.pk,
            self.doktorat.opis_bibliograficzny(links="admin"),
        )

    def test_strip_at_end(self):
        self.assertEqual("foo", strip_at_end("foo.,.,.,"))

    def test_znak_na_koncu_alt(self):
        self.assertEqual("foo.", znak_na_koncu("foo.,.,", "."))

        self.assertEqual("", znak_na_koncu(".,.,", "."))

        self.assertEqual(None, znak_na_koncu(None, ",."))

    def test_znak_na_koncu(self):
        template = """
        {% load prace %}
        {{ ciag_znakow|znak_na_koncu:", " }}
        """

        t = Template(template)
        c = Context({"ciag_znakow": "loll..."})
        ret = t.render(c).strip()
        self.assertEqual(ret, "loll,")

    def test_znak_na_poczatku(self):
        template = """
        {% load prace %}
        {{ ciag_znakow|znak_na_poczatku:"," }}
        """

        t = Template(template)
        c = Context({"ciag_znakow": "loll"})
        ret = t.render(c).strip()
        self.assertEqual(ret, ", loll")

    def test_ladne_numery_prac(self):
        template = """
        {% load prace %}
        {{ arr|ladne_numery_prac }}
        """

        t = Template(template)
        c = Context(
            {"arr": {1, 2, 3, 4, 5, 10, 11, 12, 15, 16, 20, 25, 30, 31, 32, 33}}
        )
        ret = t.render(c).strip()
        self.assertEqual(ret, "1-5, 10-12, 15-16, 20, 25, 30-33")

        c = Context({"arr": {1, 3, 4, 5}})
        ret = t.render(c).strip()
        self.assertEqual(ret, "1, 3-5")
