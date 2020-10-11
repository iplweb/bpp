# -*- encoding: utf-8 -*-

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from bpp.tests.tests_legacy.testutil import WebTestCase, UserTestCase


class TestMultiseekAnonymous(WebTestCase):
    def test_multiseek(self):
        res = self.client.get(reverse("multiseek:index"))
        self.assertNotContains(res, "Adnotacje", status_code=200)


class TestMultiseekLoggedIn(UserTestCase):
    def test_multiseek(self):
        res = self.client.get(reverse("multiseek:index"))
        self.assertContains(res, "Adnotacje", status_code=200)
