# -*- encoding: utf-8 -*-

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.test import TestCase, Client
from bpp.models.profile import BppUser
from bpp.models.struktura import Wydzial
from bpp.models.system import Typ_Odpowiedzialnosci, Charakter_Formalny, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle
from bpp.tests.tests_legacy.test_reports.util import stworz_obiekty_dla_raportow
from bpp.tests.util import (
    any_wydzial,
    any_autor,
    any_ciagle,
    any_jednostka,
    CURRENT_YEAR,
)
from bpp.views.raporty.ranking_autorow import RankingAutorow


class TestRankingAutorow(TestCase):

    # fixtures = ['typ_odpowiedzialnosci.json',
    #             'charakter_formalny.json',
    #             'typ_kbn.json']

    def setUp(self):
        stworz_obiekty_dla_raportow()

        w1 = any_wydzial(nazwa="Wydzial 1", skrot="W9")
        w1.zezwalaj_na_ranking_autorow = True
        w1.save()
        j1 = any_jednostka(wydzial=w1, uczelnia=w1.uczelnia)

        w2 = any_wydzial(nazwa="Wydzial 2", skrot="W8")
        w2.zezwalaj_na_ranking_autorow = True
        w2.save()
        j2 = any_jednostka(wydzial=w2, uczelnia=w2.uczelnia)

        self.w2 = w2

        a1 = any_autor()

        wejdzie1 = any_ciagle(impact_factor=33.333)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wejdzie1,
            autor=a1,
            jednostka=j1,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        )

        wejdzie2 = any_ciagle(impact_factor=44.444)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wejdzie2,
            autor=a1,
            jednostka=j2,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        )

        nie_wejdzie = any_ciagle(
            typ_kbn=Typ_KBN.objects.get(skrot="PW"), impact_factor=55.555
        )
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=nie_wejdzie,
            autor=a1,
            jednostka=j1,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        )

        BppUser.objects.create_user(username="foo", email="foo@bar.pl", password="bar")

        self.client = Client()
        response = self.client.post(
            reverse("login_form"), {"username": "foo", "password": "bar"}, follow=True
        )
        self.assertEqual(response.status_code, 200)

    def test_bez_argumentow(self):
        "Zsumuje punktacje ze wszystkich prac, ze wszystkich wydziałów dla danego roku"
        response = self.client.get(
            reverse(
                "bpp:ranking-autorow", args=(str(CURRENT_YEAR), str(CURRENT_YEAR),)
            ),
            follow=True,
        )
        # wydział 2
        self.assertIn("44,444", response.rendered_content)
        # wydział 1
        self.assertIn("33,333", response.rendered_content)

    def test_z_wydzialem(self):
        "Zsumuje punktacje ze wszystkich prac, ze wszystkich wydziałów dla danego roku"
        response = self.client.get(
            reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), str(CURRENT_YEAR),))
            + "?wydzialy[]="
            + str(self.w2.pk),
            follow=True,
        )
        # wydział 2
        self.assertIn("44,444", response.rendered_content)
        # wydział 1 - praca nie wejdzie do rankingu
        self.assertNotIn("33,333", response.rendered_content)

    def test_bez_rozbicia(self):
        "Zsumuje punktacje ze wszystkich prac bez rozbicia na jednostki"
        response = self.client.get(
            reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), str(CURRENT_YEAR),))
            + "?rozbij_na_jednostki=False",
            follow=True,
        )
        # suma punktacji
        self.assertIn("77,777", response.rendered_content)

    def test_eksport_csv(self):
        "XLS"
        response = self.client.get(
            reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), str(CURRENT_YEAR),))
            + "?_export=csv",
            follow=True,
        )
        # suma punktacji
        self.assertIn(b",44.444,", response.content)
