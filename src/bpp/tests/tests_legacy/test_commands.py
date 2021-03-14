from django.test import TestCase

from bpp.management.commands.import_bpp import afiliacja


class TestImportBpp(TestCase):
    def test_afiliacja(self):
        kw = {}

        d1 = dict(recenzowana=True, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw["recenzowana"], True)

        d1 = dict(recenzowana=None, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw["recenzowana"], False)
