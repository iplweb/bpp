# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
import time
from django.conf import settings
from django.db import transaction
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from bpp.models import Wydawnictwo_Ciagle
from bpp.models.system import Status_Korekty
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_ciagle, any_autor, any_jednostka

from bpp.tests.helpers import SeleniumLoggedInAdminTestCase
from bpp.tests.util import any_zrodlo, CURRENT_YEAR


ID = "id_tytul_oryginalny"
CHARMAP = ID + "_charmap"
WINDOW = CHARMAP + "_window"


class ProperClickMixin:
    def scrollIntoView(self, arg):
        return self.page.execute_script("document.getElementById('id_" + arg + "').scrollIntoView()")

    def byId(self, arg):
        return self.page.find_element_by_id("id_" + arg)

    def proper_click(self, arg):
        self.page.execute_script("document.getElementById('id_" + arg + "').click()")
        return self.byId(arg)

class SeleniumAdminTestCaseCharmapTest(ProperClickMixin, SeleniumLoggedInAdminTestCase):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    def test_admin_charmap(self):
        """Ten test dodaje pracę ze "specjalnym" tytułem, za pomocą clicków
        w charmapę, następnie sprawdza, czy została istotnie dodana."""

        main_window = self.page.current_window_handle
        self.proper_click(CHARMAP[3:])

        self.page.switch_to_window(WINDOW)
        self.page.wait_for_selector(".char")
        elem = self.page.find_elements_by_class_name("char")[0]
        elem.click()

        self.page.switch_to_window(main_window)
        value = self.page.find_element_by_id(ID)
        self.assertEquals(value.get_attribute('value'), u'\u0391') # Pierwszy znak z greki


class SeleniumAdminTestTozTamze(SeleniumLoggedInAdminTestCase):
    def setUp(self):
        Status_Korekty.objects.create(pk=1, nazwa='ok')
        self.c = any_ciagle(informacje='TO INFORMACJE')
        SeleniumLoggedInAdminTestCase.setUp(self)

    def _get_url(self):
        return reverse("admin:bpp_wydawnictwo_ciagle_change", args=(self.c.pk,))

    url = property(_get_url)

    def test_admin_wydawnictwo_ciagle_toz(self):
        wcc = Wydawnictwo_Ciagle.objects.count
        self.assertEquals(wcc(), 1)
        toz = self.page.find_element_by_id('toz')
        toz.click()
        self.page.assertPopupContains(u"Utworzysz kopię tego rekordu")
        self.page.wait_for_id('navigation-menu')
        self.assertEquals(wcc(), 2)

    def test_admin_wydawnictwo_ciagle_tamze(self):
        tamze = self.page.find_element_by_id('tamze')
        tamze.click()
        time.sleep(1)
        self.assertIn('Dodaj wydawnictwo', self.page.page_source)
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
        jq("#id_zrodlo_text").send_keys("FOO BAR")
        time.sleep(2)
        jq("#id_zrodlo_text").send_keys(Keys.TAB)
        time.sleep(2)

        self.page.execute_script("$('#id_wypelnij_pola_punktacji_button').click()")
        self.page.assertPopupContains(u"Uzupełnij pole")

from django.conf import settings

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

        button = proper_click("wypelnij_pola_punktacji_button")
        time.sleep(1)

        self.assertEquals(punkty_kbn.val(), "10.20")
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
        self.page.execute_script('$("span.remove.div").click()')
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
        proper_click = self.proper_click

        z = self.z

        byId("zrodlo_text").send_keys("WTF LOL")
        time.sleep(2)
        byId("zrodlo_text").send_keys(Keys.TAB)
        byId("rok").send_keys(str(CURRENT_YEAR))
        byId("impact_factor").val("50")

        proper_click("dodaj_punktacje_do_zrodla_button")
        time.sleep(2)

        self.assertEquals(Punktacja_Zrodla.objects.count(), 1)
        self.assertEquals(Punktacja_Zrodla.objects.all()[0].impact_factor, 50)

        byId("impact_factor").val("60")
        proper_click("dodaj_punktacje_do_zrodla_button")
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
        aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-autor_text")
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

        aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-autor_text")
        aut.send_keys("KOWALSKI")
        time.sleep(2)
        aut.send_keys(Keys.TAB)
        time.sleep(2)

        jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-jednostka"))
        self.assertEquals(
            jed.first_selected_option.text(),
            "WTF LOL")

