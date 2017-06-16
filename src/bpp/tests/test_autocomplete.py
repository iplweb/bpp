# -*- encoding: utf-8 -*-
from model_mommy import mommy
from autocomplete_light.registry import registry

from bpp.models import Autor, Jednostka, Zrodlo, Tytul, Autor_Jednostka
from bpp.tests.util import any_jednostka
from .testutil import WebTestCase


class TestAutocomplete(WebTestCase):

    def test_autocompletes(self):
        req = self.factory.get('/', {'q':'Foobarowski'})

        autocompletes = [('AutorAutocompleteAutor', Autor, 'nazwisko'),
                         ('ZrodloAutocompleteZrodlo', Zrodlo, 'nazwa')]

        for name, object, attribute in autocompletes:
            o1 = mommy.make(object)
            setattr(o1, attribute, 'Foobarowski')
            o1.save()

            o2 = mommy.make(object)
            setattr(o2, attribute, 'Niebarowski')
            o2.save()

            ret = registry[name](request=req).choices_for_request()

            self.assertIn(o1, ret)
            self.assertNotIn(o2, ret)

    def test_autocomplete_jednostka(self):
        a = mommy.make(Autor)
        jednostki = [mommy.make(Jednostka, nazwa='Ala'),
                     mommy.make(Jednostka, nazwa="jeszczeinna"),
                     mommy.make(Jednostka, nazwa="kolejnaInna")]

        map(lambda j: Autor_Jednostka.objects.create(autor=a, jednostka=j), jednostki)

        def request(q=''):
            return self.factory.get('/', {'autor_id': a.pk, 'q':q})

        def choices(req):
            return registry['JednostkaAutocompleteJednostka'](req).choices_for_request()

        ret = choices(request())
        map(lambda j: self.assertIn(j, ret), jednostki)

        ret = choices(request('Ala'))
        self.assertIn(jednostki[0], ret)
        self.assertNotIn(jednostki[1], ret)
        self.assertNotIn(jednostki[2], ret)


    def test_autocomplete_zapisane_nazwiska(self):
        t = mommy.make(Tytul, nazwa='dr')
        a = mommy.make(Autor, nazwisko='Baz', imiona='Quux', tytul=t)
        a.save()

        req = self.factory.get('/', {'autor_id':a.pk})
        ret = registry['AutocompleteZapisaneNazwiska'](request=req).choices_for_request()
        self.assertIn('Q[uux] Baz', ret)

