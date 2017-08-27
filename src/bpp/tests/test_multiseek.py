# -*- encoding: utf-8 -*-
from unittest.case import TestCase

from django.core.urlresolvers import reverse

from bpp.multiseek_registry import ZrodloQueryObject
from .testutil import WebTestCase, UserTestCase


class TestMultiseekAnonymous(WebTestCase):
    def test_multiseek(self):
        res = self.client.get(reverse("multiseek:index"))
        self.assertNotContains(res, 'Adnotacje', status_code=200)


class TestMultiseekLoggedIn(UserTestCase):
    def test_multiseek(self):
        res = self.client.get(reverse("multiseek:index"))
        self.assertContains(res, 'Adnotacje', status_code=200)


class TestMultiseekZrodlo(TestCase):
    def test_get_autocomplete_query(self):
        z = ZrodloQueryObject()
        res = z.get_autocomplete_query(b'foobar')
        assert res != None
        assert list(res) != None
