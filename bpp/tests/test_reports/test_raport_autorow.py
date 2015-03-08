# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse

from django.test import TestCase
from django.test.client import Client


class Test(TestCase):
    def setUp(self):
        pass

    def test_raport_autorow(self):
        c = Client()
        res = c.get(reverse("bpp:raport_autorow_formularz"))
        self.assertContains(res, 'raport autorów', status_code=200)
