# -*- encoding: utf-8 -*-

from django.test import TestCase
from django.test.client import Client
from django.urls.base import reverse
from django.utils.http import urlencode
from bpp.models.autor import Autor
from bpp.tests.util import any_autor


class TestFulltextSearch(TestCase):
    
    def setUp(self):
        self.kowalski = any_autor('Kowalski', 'Jan')
        self.nowak = any_autor('Nowak', 'Jan')

    def test_search_field(self):
        self.assertNotEqual(
            Autor.objects.all()[0].search, None)

    def test_fulltext_search_mixin(self):
        res = Autor.objects.fulltext_filter('kowalski jan')
        self.assertTrue(self.kowalski in res)

    def test_global_nav_search(self):
        client = Client()

        for s in ["śmierć", "śmierć",
                  "pas ternak'", "paste rnak''", "past ernak\\", "pastern ak\\'",
                  "past ernak\'", "past ernak &", "pa sternak (", "!paster nak",
                  "paste rnak)", "&", "& &", "()", "!!", "!", ")()()(\\\\!@!!@@!#!@",
                  "   ()(*(*$(*#  oiad  9*(*903498985398)()(||| aosid  p p    ",
                  ]:
            url = reverse('bpp:navigation-autocomplete')
            url += '?'+ urlencode({'q':s})
            res = client.get(url)
            self.assertEqual(res.status_code, 200)