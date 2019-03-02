# -*- encoding: utf-8 -*-
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from bpp.models.cache import Rekord
from bpp.tests.util import any_ciagle
from bpp.tests.tests_legacy.testutil import WebTestCase


class TestOAI(WebTestCase):

    def setUp(self):
        any_ciagle()
        self.assertEqual(Rekord.objects.all().count(), 1)
    
    def test_identify(self):
        identify = reverse("bpp:oai") + "?verb=Identify"
        res = self.client.get(identify)
        self.assertEqual(res.status_code, 200)
