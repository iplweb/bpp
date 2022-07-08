from django.test import TestCase
from model_bakery import baker

from bpp.models import POLA_PUNKTACJI, Wydawnictwo_Ciagle
from bpp.models.abstract import ILOSC_ZNAKOW_NA_ARKUSZ


class AbstractModelsTestCase(TestCase):
    def test_pola(self):
        self.assertIn("impact_factor", POLA_PUNKTACJI)
        self.assertNotIn("weryfikacja_punktacji", POLA_PUNKTACJI)

    def test_model_punktowany(self):
        mp = baker.make(Wydawnictwo_Ciagle, impact_factor=0)
        self.assertEqual(mp.ma_punktacje(), False)

        mp.impact_factor = 0
        self.assertEqual(mp.ma_punktacje(), False)

        mp.impact_factor = 1
        self.assertEqual(mp.ma_punktacje(), True)

    def test_ModelZeZnakamiWydawniczymi(self):
        x = baker.make(Wydawnictwo_Ciagle, liczba_znakow_wydawniczych=None)

        # x.liczba_znakow_wydawniczych = None
        self.assertTrue(not x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = 5
        self.assertTrue(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = None
        self.assertFalse(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = 5
        self.assertTrue(x.ma_wymiar_wydawniczy())

        x.liczba_znakow_wydawniczych = ILOSC_ZNAKOW_NA_ARKUSZ
        self.assertEqual(x.wymiar_wydawniczy_w_arkuszach(), "1.00")

        x.liczba_znakow_wydawniczych = ILOSC_ZNAKOW_NA_ARKUSZ * 2.5
        self.assertEqual(x.wymiar_wydawniczy_w_arkuszach(), "2.50")
