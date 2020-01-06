import pytest
from model_mommy import mommy
from django.core.management import call_command

from bpp.management.commands.import_bpp import afiliacja

from django.test import TestCase

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle


class TestImportBpp(TestCase):
    def test_afiliacja(self):
        kw = {}

        d1 = dict(recenzowana=True, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw['recenzowana'], True)


        d1 = dict(recenzowana=None, id=0)
        afiliacja(d1, kw)
        self.assertEqual(kw['recenzowana'], False)

    @pytest.mark.serial
    def test_rebuild_cache(self):
        mommy.make(Wydawnictwo_Ciagle)
        call_command("rebuild_cache")
