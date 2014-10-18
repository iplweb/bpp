# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
from bpp.models.cache import Rekord
from bpp.tests.util import any_ciagle
from .testutil import WebTestCase


class TestOAI(WebTestCase):

    def setUp(self):
        any_ciagle()
        Rekord.objects.refresh()
        self.assertEquals(Rekord.objects.all().count(), 1)
    
    def test_identify(self):
        identify = reverse("bpp:oai") + "?verb=Identify"
        res = self.client.get(identify)
        self.assertEquals(res.status_code, 200)