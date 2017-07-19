# -*- encoding: utf-8 -*-
from model_mommy import mommy
from bpp.views import autocomplete

from bpp.models import Autor, Jednostka, Zrodlo, Tytul, Autor_Jednostka
from bpp.tests.util import any_jednostka
from ..testutil import WebTestCase


class TestAutocomplete(WebTestCase):
    def test_Wydawnictwo_NadrzedneAutocomplete(self):
        x = autocomplete.Wydawnictwo_NadrzedneAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_JednostkaAutocomplete(self):
        x = autocomplete.JednostkaAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_KonferencjaAutocomplete(self):
        x = autocomplete.KonferencjaAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_Seria_WydawniczaAutocomplete(self):
        x = autocomplete.Seria_WydawniczaAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_ZrodloAutocomplete(self):
        x = autocomplete.ZrodloAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_AutorAutocomplete(self):
        x = autocomplete.AutorAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_GlobalNavigationAutocomplete(self):
        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = None
        x.get_result_label("foo", "bar")
        x.get(None)
        x.q = "foobar"
        self.assertTrue(x.get_results() != None)

    def test_ZapisanyJakoAutocomplete(self):
        x = autocomplete.ZapisanyJakoAutocomplete()
        a = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski",
                       poprzednie_nazwiska="")
        x.forwarded = dict(autor=str(a.id))
        self.assertTrue(len(x.get_list()), 3)

    def test_PodrzednaPublikacjaHabilitacyjnaAutocomplete(self):
        x = autocomplete.PodrzednaPublikacjaHabilitacyjnaAutocomplete()
        a = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski",
                       poprzednie_nazwiska="")
        x.forwarded = dict(autor=str(a.id))

        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)

    def test_GlobalNavigationAutocomplete(self):
        x = autocomplete.GlobalNavigationAutocomplete()
        x.q = "foobar"
        self.assertTrue(x.get_queryset() != None)