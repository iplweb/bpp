# -*- encoding: utf-8 -*-
import time

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.system import Status_Korekty
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_ciagle, any_autor, any_jednostka
from bpp.tests.helpers import SeleniumLoggedInAdminTestCase
from bpp.tests.util import any_zrodlo, CURRENT_YEAR, any_zwarte, any_patent


ID = "id_tytul_oryginalny"


class ProperClickMixin:
    def scrollIntoView(self, arg):
        return self.page.execute_script("document.getElementById('id_" + arg + "').scrollIntoView()")

    def byId(self, arg):
        return self.page.find_element_by_id("id_" + arg)

    def proper_click(self, arg):
        self.page.execute_script("document.getElementById('id_" + arg + "').scrollIntoView()")
        self.page.execute_script("document.getElementById('id_" + arg + "').click()")

class SeleniumAdminTestTozTamze(SeleniumLoggedInAdminTestCase):
    url = "/admin/"

    def setUp(self):
        Status_Korekty.objects.create(pk=1, nazwa='ok')
        SeleniumLoggedInAdminTestCase.setUp(self)

    def test_admin_wydawnictwo_ciagle_toz(self):
        self.c = any_ciagle(informacje='TO INFORMACJE')
        self.open(reverse("admin:bpp_wydawnictwo_ciagle_change", args=(self.c.pk,)))

        wcc = Wydawnictwo_Ciagle.objects.count
        self.assertEquals(wcc(), 1)
        toz = self.page.find_element_by_id('toz')
        toz.click()
        self.page.assertPopupContains(u"Utworzysz kopię tego rekordu")
        self.page.wait_for_id('navigation-menu')
        self.assertEquals(wcc(), 2)

    def test_admin_wydawnictwo_ciagle_tamze(self):
        self.c = any_ciagle(informacje='TO INFORMACJE')
        self.open(reverse("admin:bpp_wydawnictwo_ciagle_change", args=(self.c.pk,)))
        
        tamze = self.page.find_element_by_id('tamze')
        tamze.click()
        time.sleep(1)
        self.assertIn('Dodaj wydawnictwo', self.page.page_source)
        self.assertIn('TO INFORMACJE', self.page.page_source)


    def test_admin_wydawnictwo_zwarte_toz(self):
        self.c = any_zwarte(informacje="TO INFOMRACJE")
        self.open(reverse("admin:bpp_wydawnictwo_zwarte_change", args=(self.c.pk,)))

        wcc = Wydawnictwo_Zwarte.objects.count
        self.assertEquals(wcc(), 1)
        toz = self.page.find_element_by_id('toz')
        toz.click()
        self.page.assertPopupContains(u"Utworzysz kopię tego rekordu")
        self.page.wait_for_id('navigation-menu')
        self.assertEquals(wcc(), 2)

    def test_admin_wydawnictwo_zwarte_tamze(self):
        self.c = any_zwarte(informacje="TO INFORMACJE")
        self.open(reverse("admin:bpp_wydawnictwo_zwarte_change", args=(self.c.pk,)))

        tamze = self.page.find_element_by_id('tamze')
        tamze.click()
        time.sleep(1)
        self.assertIn('Dodaj wydawnictwo', self.page.page_source)
        self.assertIn('TO INFORMACJE', self.page.page_source)



    def test_admin_patent_toz(self):
        self.c = any_patent(informacje="TO INFORMACJE")
        self.open(reverse("admin:bpp_patent_change", args=(self.c.pk,)))

        wcc = Patent.objects.count
        self.assertEquals(wcc(), 1)
        toz = self.page.find_element_by_id('toz')
        toz.click()
        self.page.assertPopupContains(u"Utworzysz kopię tego rekordu")
        self.page.wait_for_id('navigation-menu')
        self.assertEquals(wcc(), 2)

    def test_admin_patent_tamze(self):
        self.c = any_patent(informacje="TO INFORMACJE")
        self.open(reverse("admin:bpp_patent_change", args=(self.c.pk,)))

        tamze = self.page.find_element_by_id('tamze')
        tamze.click()
        time.sleep(1)
        self.assertIn('Dodaj patent', self.page.page_source)
        self.assertIn('TO INFORMACJE', self.page.page_source)


class SeleniumAdminTestAutomatycznieUzupelnijPunktyNowyRekord(
    SeleniumLoggedInAdminTestCase):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    available_apps = settings.INSTALLED_APPS # dla sqlflush

    def test_admin_button_clicks(self):
        z = any_zrodlo(nazwa="FOO BAR")
        jq = self.page.find_element_by_jquery

        self.page.execute_script("$('#id_wypelnij_pola_punktacji_button').click()")
        # bo jenkins
        self.page.assertPopupContains(u"Najpierw wybierz jakie")
        time.sleep(1)
        jq("#id_zrodlo-autocomplete").send_keys("FOO BAR")
        time.sleep(2)
        jq("#id_zrodlo-autocomplete").send_keys(Keys.TAB)
        time.sleep(2)

        self.page.execute_script("$('#id_wypelnij_pola_punktacji_button').click()")
        self.page.assertPopupContains(u"Uzupełnij pole")

class SeleniumAdminTestAutomatycznieUzupelnijPunkty(
    ProperClickMixin, SeleniumLoggedInAdminTestCase):

    available_apps = settings.INSTALLED_APPS # dla sqlflush

    def _get_url(self):
        return reverse(
            "admin:bpp_wydawnictwo_ciagle_change",
            args=(self.c.pk,))

    url = property(_get_url)

    def setUp(self):
        self.z = any_zrodlo(nazwa="WTF LOL")

        kw = dict(zrodlo=self.z)
        f = Punktacja_Zrodla.objects.create
        f(impact_factor=10.1, punkty_kbn=10.2, rok=CURRENT_YEAR, **kw)
        f(impact_factor=11.1, punkty_kbn=11.2, rok=CURRENT_YEAR + 1, **kw)

        Status_Korekty.objects.create(pk=1, nazwa="OK")

        self.c = any_ciagle(
            zrodlo=self.z, impact_factor=5, punkty_kbn=5)

        super(SeleniumAdminTestAutomatycznieUzupelnijPunkty, self).setUp()

    def test_admin_uzupelnij_punkty(self):

        byId = self.byId
        proper_click = self.proper_click

        rok = byId("rok")
        punkty_kbn = byId("punkty_kbn")
        time.sleep(1)

        self.assertEquals(rok.val(), str(CURRENT_YEAR))
        self.assertEquals(punkty_kbn.val(), "5.00")

        proper_click("wypelnij_pola_punktacji_button")
        time.sleep(1)

        self.assertEquals(punkty_kbn.val(), "10.20")
        button = byId("wypelnij_pola_punktacji_button")
        self.assertEquals(button.text(), u"Wypełniona!")

        rok.trigger("change")
        time.sleep(1)
        # Po zmianie roku LUB źródła przycisk ma się zmienić
        self.assertEquals(button.text(), u"Wypełnij pola punktacji")

        # Zwiększymy rok o 1 i sprawdzimy, czy zmieni się punktacja
        rok.val(str(CURRENT_YEAR + 1))

        proper_click("wypelnij_pola_punktacji_button")
        time.sleep(1)

        self.assertEquals(punkty_kbn.val(), "11.20")

        # Teraz usuniemy źródło i sprawdzimy, czy przycisk zmieni nazwę
        self.assertEquals(button.text(), u"Wypełniona!")
        self.page.execute_script('$("span.remove").first().click()')
        time.sleep(1)
        self.assertEquals(button.text(), u"Wypełnij pola punktacji")


class SeleniumAdminTestUploadujPunkty(
    ProperClickMixin, SeleniumLoggedInAdminTestCase):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    def setUp(self):
        self.z = any_zrodlo(nazwa="WTF LOL")
        SeleniumLoggedInAdminTestCase.setUp(self)

    def test_upload_punkty(self):

        byId = self.byId

        z = self.z

        byId("zrodlo-autocomplete").send_keys("WTF LOL")
        time.sleep(2)
        byId("zrodlo-autocomplete").send_keys(Keys.TAB)
        byId("rok").send_keys(str(CURRENT_YEAR))
        byId("impact_factor").val("50")

        self.proper_click("dodaj_punktacje_do_zrodla_button")
        time.sleep(2)

        self.assertEquals(Punktacja_Zrodla.objects.count(), 1)
        self.assertEquals(Punktacja_Zrodla.objects.all()[0].impact_factor, 50)

        byId("impact_factor").val("60")
        self.proper_click("dodaj_punktacje_do_zrodla_button")
        time.sleep(2)
        self.page.assertPopupContains(u"Punktacja dla tego roku już istnieje")
        time.sleep(2)

        self.assertEquals(Punktacja_Zrodla.objects.count(), 1)
        self.assertEquals(Punktacja_Zrodla.objects.all()[0].impact_factor, 60)


class SeleniumAdminTestAutorformJednostka(SeleniumLoggedInAdminTestCase):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    def setUp(self):
        with transaction.atomic():
            a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
            j = any_jednostka(nazwa="WTF LOL")
            j.dodaj_autora(a)
        SeleniumLoggedInAdminTestCase.setUp(self)

    def test_uzupelnianie_jednostki(self):
        aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-autor-autocomplete")
        aut.send_keys("KOWALSKI")
        time.sleep(2)
        aut.send_keys(Keys.TAB)
        time.sleep(2)

        jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka"))
        self.assertEquals(
            jed.first_selected_option.text(),
            "WTF LOL")

    def test_uzupelnianie_jednostki_drugi_wiersz(self):
        # bug polegający na tym, że druga jednostka się ŹLE wypełnia

        # najpierw kliknij "dodaj autora"
        self.page.execute_script('$(".grp-add-handler")[1].click()')
        time.sleep(2)

        # a potem wpisz dane i sprawdź, że jednostki NIE będzie

        aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-autor-autocomplete")
        aut.send_keys("KOWALSKI")
        time.sleep(2)
        aut.send_keys(Keys.TAB)
        time.sleep(2)

        jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-jednostka"))
        self.assertEquals(
            jed.first_selected_option.text(),
            "WTF LOL")


    def test_kasowanie_autora(self):
        # bug polegający na tym, że przy dodaniu autora i potem skasowaniu go,
        # pole jednostki i nazwisk się NIE czyści
        # ... ale zostawiam to w spokoju.
        # bo: 1) trudno zlapac event czyszczenia pola ( d-a-light zmienia chyba DOM)
        #     2) co to niby ma dać?
        #     3) ten test zostaje, bo sprawdza działanie przycisku 'remove' - był bug na to

        aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-autor-autocomplete")
        aut.send_keys("KOWALSKI")
        time.sleep(2)
        aut.send_keys(Keys.TAB)
        time.sleep(2)

        self.page.execute_script("""
        $("#id_wydawnictwo_ciagle_autor_set-0-autor-deck").find(".remove").click()
        """)

        jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka"))
        self.assertEquals(jed.first_selected_option.text(), "WTF LOL")