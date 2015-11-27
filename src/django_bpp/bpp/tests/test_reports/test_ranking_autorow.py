# -*- encoding: utf-8 -*-

from django.core.urlresolvers import reverse
from django.test import TestCase, Client
from bpp.models.profile import BppUser
from bpp.models.system import Typ_Odpowiedzialnosci, Charakter_Formalny, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import any_wydzial, any_autor, any_ciagle, any_jednostka, \
    CURRENT_YEAR
from bpp.views.raporty.ranking_autorow import RankingAutorow


class TestRankingAutorow(TestCase):

    # fixtures = ['typ_odpowiedzialnosci.json',
    #             'charakter_formalny.json',
    #             'typ_kbn.json']

    def setUp(self):
        w1 = any_wydzial()
        j1 = any_jednostka(wydzial=w1)

        w2 = any_wydzial()
        j2 = any_jednostka(wydzial=w2)

        self.w2 = w2
        
        a1 = any_autor()
        
        wejdzie1 = any_ciagle(impact_factor=33.333)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wejdzie1,
            autor=a1,
            jednostka=j1,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
        )
        
        wejdzie2 = any_ciagle(impact_factor=44.444)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=wejdzie2,
            autor=a1,
            jednostka=j2,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
        )

        nie_wejdzie = any_ciagle(
            typ_kbn=Typ_KBN.objects.get(skrot='PW'),
            impact_factor=55.555)
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=nie_wejdzie,
            autor=a1,
            jednostka=j1,
            kolejnosc=1,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
        )

        BppUser.objects.create_user(username='foo', email='foo@bar.pl', password='bar')

        self.client = Client()
        response = self.client.post(
            reverse("login_form"),
            {"username":"foo", "password": "bar"},
            follow=True)
        self.assertEquals(response.status_code, 200)

    def test_bez_argumentow(self):
        "Zsumuje punktacje ze wszystkich prac, ze wszystkich wydziałów dla danego roku"
        response = self.client.get(
            reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), )),
            follow=True
        )
        self.assertIn("44,444", response.content) # wydział 2
        self.assertIn("33,333", response.content) # wydział 1 - praca 'nie-wejdzie'

    def test_z_wydzialem(self):
        "Zsumuje punktacje ze wszystkich prac, ze wszystkich wydziałów dla danego roku"
        response = self.client.get(
            reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), )) + "?wydzialy[]=" + str(self.w2.pk),
            follow=True
        )
        self.assertIn("44,444", response.content) # wydział 2
        self.assertNotIn("33,333", response.content) # wydział 1 - praca 'nie-wejdzie'
