import json
from collections import namedtuple

from django.test import TestCase

from bpp.models import Typ_Odpowiedzialnosci
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests.util import CURRENT_YEAR, any_autor, any_habilitacja, any_zrodlo
from bpp.views.api import (
    PunktacjaZrodlaView,
    RokHabilitacjiView,
    UploadPunktacjaZrodlaView,
)

FakeRequest = namedtuple("FakeRequest", ["POST"])


class TestRokHabilitacjiView(TestCase):
    # fixtures = ['charakter_formalny.json', 'typ_odpowiedzialnosci.json']

    def test_rokhabilitacjiview(self):
        Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")

        a = any_autor()
        h = any_habilitacja(tytul_oryginalny="Testowa habilitacja", rok=CURRENT_YEAR)
        h.autor = a
        h.save()

        request = FakeRequest({"autor_pk": a.pk})

        rhv = RokHabilitacjiView()

        res = rhv.post(request)
        self.assertContains(res, str(CURRENT_YEAR), status_code=200)
        self.assertEqual(json.loads(res.content)["rok"], CURRENT_YEAR)

        h.delete()
        res = rhv.post(request)
        self.assertContains(res, "Habilitacja", status_code=404)

        a.delete()
        res = rhv.post(request)
        self.assertContains(res, "Autor", status_code=404)


class TestPunktacjaZrodlaView(TestCase):
    def test_punktacjazrodlaview(self):
        z = any_zrodlo()
        Punktacja_Zrodla.objects.create(zrodlo=z, rok=CURRENT_YEAR, impact_factor=50)

        res = PunktacjaZrodlaView().post(None, z.pk, CURRENT_YEAR)
        analyze = json.loads(res.content.decode(res.charset))
        self.assertEqual(analyze["impact_factor"], "50.000")

        res = PunktacjaZrodlaView().post(None, z.pk, CURRENT_YEAR + 100)
        self.assertContains(res, "Rok", status_code=404)

    def test_punktacjazrodlaview_404(self):
        res = PunktacjaZrodlaView().post(None, 1, CURRENT_YEAR)
        self.assertContains(res, "Zrodlo", status_code=404)


class TestUploadPunktacjaZrodlaView(TestCase):
    def test_upload_punktacja_zrodla_404(self):
        res = UploadPunktacjaZrodlaView().post(None, 1, CURRENT_YEAR)
        self.assertContains(res, "Zrodlo", status_code=404)

    def test_upload_punktacja_zrodla_simple(self):
        z = any_zrodlo()
        fr = FakeRequest(dict(impact_factor="50.00"))
        UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
        self.assertEqual(Punktacja_Zrodla.objects.count(), 1)
        self.assertEqual(Punktacja_Zrodla.objects.all()[0].impact_factor, 50)

    def test_upload_punktacja_zrodla_overwrite(self):
        z = any_zrodlo()
        Punktacja_Zrodla.objects.create(rok=CURRENT_YEAR, zrodlo=z, impact_factor=50)
        fr = FakeRequest(dict(impact_factor="60.00", punkty_kbn="60"))
        res = UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
        self.assertContains(res, "exists", status_code=200)

        fr = FakeRequest(dict(impact_factor="60.00", overwrite="1"))
        UploadPunktacjaZrodlaView().post(fr, z.pk, CURRENT_YEAR)
        self.assertEqual(Punktacja_Zrodla.objects.count(), 1)
        self.assertEqual(Punktacja_Zrodla.objects.all()[0].impact_factor, 60)
