# -*- encoding: utf-8 -*-
from model_mommy import mommy

from bpp.models import Autor, Jednostka, Zrodlo, Charakter_Formalny, Uczelnia
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.views import autocomplete
from bpp.tests.tests_legacy.testutil import WebTestCase


class TestAutocomplete(WebTestCase):
    def test_Wydawnictwo_NadrzedneAutocomplete(self):
        Charakter_Formalny.objects.get_or_create(skrot="ROZ", nazwa="Rozdział książki")
        Charakter_Formalny.objects.get_or_create(skrot="ROZS", nazwa="Rozdział skryptu")

        x = autocomplete.Wydawnictwo_NadrzedneAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_JednostkaAutocomplete(self):
        x = autocomplete.JednostkaAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_KonferencjaAutocomplete(self):
        x = autocomplete.KonferencjaAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_Seria_WydawniczaAutocomplete(self):
        x = autocomplete.Seria_WydawniczaAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_ZrodloAutocomplete(self):
        x = autocomplete.ZrodloAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_AutorAutocomplete(self):
        x = autocomplete.AutorAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)
        x.q = ":"
        self.assertTrue(len(x.get_queryset()) != None)

        self.assertEquals(x.create_object("test").pk, -1)

        res = x.create_object("budnik jan")
        y = Autor.objects.get(pk=res.pk)
        assert y.imiona == "Jan"
        assert y.nazwisko == "Budnik"

        res = x.create_object("kotulowska-papis ilona joanna")
        y = Autor.objects.get(pk=res.pk)
        assert y.imiona == "Ilona Joanna"
        assert y.nazwisko == "Kotulowska-Papis"

    def test_GlobalNavigationAutocomplete(self):
        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = None
        x.get_result_label("foo", "bar")
        x.get(None)
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_GlobalNavigationAutocomplete_query_for_id(self):
        mommy.make(Wydawnictwo_Ciagle, pk=123)
        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = "123"
        self.assertTrue(len(x.get_queryset()) == 1)

    def test_GlobalNavigationAutocomplete_test_every_url(self):
        S = "Foobar 123"
        mommy.make(Autor, nazwisko=S)
        mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny=S)
        mommy.make(Zrodlo, nazwa=S)
        mommy.make(Jednostka, nazwa=S)

        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = "Foo"
        res = x.get_results({"object_list": list(x.get_queryset())})

        cnt = 0
        for elem in res:
            for child in elem["children"]:
                # Sprawdź, czy global-nav-redir wygeneruje poprawne przekierowanie
                # dla tego zapytania
                url = "/global-nav-redir/%s/" % child["id"]
                res = self.client.get(url)
                self.assertEquals(res.status_code, 302)
                cnt += 1

        self.assertEquals(cnt, 4)

    def test_ZapisanyJakoAutocomplete(self):
        x = autocomplete.ZapisanyJakoAutocomplete()
        a = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski", poprzednie_nazwiska="")
        x.forwarded = dict(autor=str(a.id))
        self.assertTrue(len(x.get_list()), 3)

    def test_PodrzednaPublikacjaHabilitacyjnaAutocomplete(self):
        x = autocomplete.PodrzednaPublikacjaHabilitacyjnaAutocomplete()
        a = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski", poprzednie_nazwiska="")
        x.forwarded = dict(autor=str(a.id))

        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)

    def test_GlobalNavigationAutocomplete(self):
        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = "foobar"
        self.assertTrue(len(x.get_queryset()) != None)
