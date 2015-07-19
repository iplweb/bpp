# -*- encoding: utf-8 -*-

from django.test import TestCase
from bpp.models import Rekord, Charakter_Formalny
from bpp.models.cache import with_cache
from bpp.tasks import zaktualizuj_opis
from bpp.tests import any_ciagle


class TestTasks(TestCase):
    fixtures = ["charakter_formalny.json", ]

    def test_zaktualizuj_opis(self):
        c = any_ciagle(
            charakter_formalny=Charakter_Formalny.objects.get(skrot='ZSZ'),
            szczegoly='wtf-lol')
        zaktualizuj_opis(c.__class__, c.pk)

        self.assertEquals(
            c.opis_bibliograficzny(),
            Rekord.objects.all()[0].opis_bibliograficzny_cache
        )