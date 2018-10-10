# -*- encoding: utf-8 -*-

from django.test import TestCase
from bpp.models import POLA_PUNKTACJI, ModelPunktowany
from bpp.models.abstract import ModelZeZnakamiWydawniczymi, \
    ILOSC_ZNAKOW_NA_ARKUSZ


class AbstractModelsTestCase(TestCase):

    def test_pola(self):
        self.assertIn('impact_factor', POLA_PUNKTACJI)
        self.assertNotIn('weryfikacja_punktacji', POLA_PUNKTACJI)

    def test_model_punktowany(self):
        mp = ModelPunktowany()
        self.assertEqual(mp.ma_punktacje(), False)

        mp.impact_factor = 0
        self.assertEqual(mp.ma_punktacje(), False)

        mp.impact_factor = 1
        self.assertEqual(mp.ma_punktacje(), True)
        pass

    def test_ModelZeZnakamiWydawniczymi(self):
        x = ModelZeZnakamiWydawniczymi()

        x.liczba_znakow_wydawniczych = None
        self.assert_(not x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = 5
        self.assertTrue(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = None
        self.assertFalse(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = 5
        self.assertTrue(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = ILOSC_ZNAKOW_NA_ARKUSZ
        self.assertEquals(x.wymiar_wydawniczy_w_arkuszach(), "1.00")

        x.liczba_znakow_wydawniczych = ILOSC_ZNAKOW_NA_ARKUSZ * 2.5
        self.assertEquals(x.wymiar_wydawniczy_w_arkuszach(), "2.50")

