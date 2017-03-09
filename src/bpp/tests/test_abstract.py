# -*- encoding: utf-8 -*-

from django.test import TestCase
from bpp.models import POLA_PUNKTACJI, ModelPunktowany


class AbstractModelsTestCase(TestCase):

    def test_pola(self):
        self.assertIn('impact_factor', POLA_PUNKTACJI)
        self.assertNotIn('weryfikacja_punktacji', POLA_PUNKTACJI)

    def test_model_punktowany(self):
        mp = ModelPunktowany()
        self.assertEquals(mp.ma_punktacje(), False)

        mp.impact_factor = 0
        self.assertEquals(mp.ma_punktacje(), False)

        mp.impact_factor = 1
        self.assertEquals(mp.ma_punktacje(), True)
        pass
