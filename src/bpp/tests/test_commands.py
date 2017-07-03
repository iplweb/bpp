from bpp.management.commands.import_bpp import afiliacja

from django.test import TestCase

class TestImportBpp(TestCase):
    def test_afiliacja(self):
        kw = {}

        d1 = dict(afiliowana=True, recenzowana=True, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw['afiliowana'], True)


        d1 = dict(afiliowana=None, recenzowana=None, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw['afiliowana'], False)
        self.assertEqual(kw['recenzowana'], False)
