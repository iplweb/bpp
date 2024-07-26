from django.contrib.auth.models import Group

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse


from bpp.models import Typ_Odpowiedzialnosci
from bpp.tests.tests_legacy.testutil import UserTestCase
from bpp.tests.util import any_autor, any_ciagle, any_jednostka
from bpp.util import rebuild_contenttypes


class TestRankingAutorow(UserTestCase):
    def setUp(self):
        UserTestCase.setUp(self)

        rebuild_contenttypes()

        Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")
        Group.objects.get_or_create(name="wprowadzanie danych")

        j = any_jednostka()
        a = any_autor(nazwisko="Kowalski")
        c = any_ciagle(impact_factor=200, rok=2000)
        c.dodaj_autora(a, j)

    def test_renderowanie(self):
        url = reverse("bpp:ranking-autorow", args=(2000, 2000))
        res = self.client.get(url)
        self.assertContains(res, "Ranking autorów", status_code=200)
        self.assertContains(res, "Kowalski")

    def test_renderowanie_csv(self):
        url = reverse("bpp:ranking-autorow", args=(2000, 2000))
        res = self.client.get(url, data={"_export": "csv"})
        self.assertContains(res, '"Kowalski Jan Maria, dr",Jednostka')
