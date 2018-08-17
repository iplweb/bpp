# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from bpp.models import Rekord, Charakter_Formalny
from bpp.models.cache import with_cache
from bpp.tasks import zaktualizuj_opis
from bpp.tests.util import any_ciagle


class TestTasks(TestCase):
    def setUp(self):
        Charakter_Formalny.objects.get_or_create(skrot='ZSZ', nazwa="Streszczenie zjazdowe konferencji międzynarodowej")

    def test_zaktualizuj_opis(self):

        c = any_ciagle(
            charakter_formalny=Charakter_Formalny.objects.get(skrot='ZSZ'),
            szczegoly='wtf-lol')

        zaktualizuj_opis("bpp", "wydawnictwo_ciagle", c.pk)

        self.assertEqual(
            c.opis_bibliograficzny(),
            Rekord.objects.all()[0].opis_bibliograficzny_cache
        )
