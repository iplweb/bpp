# -*- encoding: utf-8 -*-
import time

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test.testcases import LiveServerTestCase
from selenium.webdriver.common.keys import Keys
from splinter.browser import Browser
from celeryui.models import Report
from django.conf import settings

from bpp.tests.util import any_autor, CURRENT_YEAR, any_ciagle, any_jednostka


DEFAULT_LOGIN = 'foo'
DEFAULT_PASSWORD = 'bar'


class RaportyPage(LiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super(RaportyPage, cls).setUpClass()

    def go(self, url):
        final_url = self.live_server_url + url
        self.browser.visit(final_url)

    def login(self, username=DEFAULT_LOGIN, password=DEFAULT_PASSWORD):
        self.go(reverse("login_form"))
        self.browser.fill("username", DEFAULT_LOGIN)
        self.browser.fill("password", DEFAULT_PASSWORD)
        self.browser.find_by_id("id_submit").click()

        if self.browser.is_element_present_by_id("password-change-link"):
            return True
        raise Exception("Nie moge zalogowac")

    def setUp(self):
        self.browser = Browser(driver_name=getattr(settings, 'SELENIUM_DRIVER', 'Firefox').lower())
        self.user = get_user_model().objects.create_user(
            username=DEFAULT_LOGIN, password=DEFAULT_PASSWORD)
        self.login()
        self.go(self.url)

    def wybrany(self):
        return self.browser.execute_script(
            "$('section.active div[data-slug]').attr('data-slug')")

    def submit_page(self):
        self.browser.execute_script("$('input[name=submit]:visible').click()")


class TestRaportyPage(RaportyPage):
    url = reverse("bpp:raporty")

    available_apps = settings.INSTALLED_APPS

    fixtures = ['typ_odpowiedzialnosci.json',
                'charakter_formalny.json',
                'jezyk.json',
                'typ_kbn.json',
                'status_korekty.json']

    def setUp(self):
        j = any_jednostka(nazwa="Jednostka")
        a = any_autor()

        c = any_ciagle(rok=CURRENT_YEAR)
        c.dodaj_autora(a, j)

        d = any_ciagle(rok=CURRENT_YEAR - 1)
        d.dodaj_autora(a, j)

        e = any_ciagle(rok=CURRENT_YEAR - 2)
        e.dodaj_autora(a, j)

        self.jednostka = j
        super(TestRaportyPage, self).setUp()

    def tearDown(self):
        self.go(reverse("logout"))
        self.browser.quit()

    def test_submit(self):
        self.go(reverse("bpp:raport_jednostek_formularz"))
        self.submit_page()
        time.sleep(3)
        self.assertIn("To pole jest wymagane", self.browser.html)

    def test_ranking_autorow(self):
        self.go(reverse("bpp:ranking_autorow_formularz"))
        self.assertIn(
            'value="%s"' % (CURRENT_YEAR - 1),
            self.browser.html)

    def test_raport_jednostek(self):
        self.go(reverse("bpp:raport_jednostek_formularz"))

        elem = self.browser.find_by_id("id_jednostka-autocomplete")[0]
        elem.type("Jedn")
        time.sleep(2)
        elem.type(Keys.TAB)
        time.sleep(1)

        self.browser.execute_script('$("input[name=od_roku]:visible").val("' + str(CURRENT_YEAR) + '")')
        self.browser.execute_script('$("input[name=do_roku]:visible").val("' + str(CURRENT_YEAR) + '")')

        self.submit_page()
        time.sleep(0.5)

        self.assertIn(
            '/bpp/raporty/raport-jednostek-2012/%s/%s/' % (
                self.jednostka.pk, CURRENT_YEAR),
            self.browser.url)

    def test_submit_kronika_uczelni(self):
        c = Report.objects.all().count
        self.assertEquals(c(), 0)

        self.go(reverse("bpp:raport_kronika_uczelni"))
        self.browser.execute_script('$("input[name=rok]").val("' + str(CURRENT_YEAR) + '")')
        self.submit_page()
        time.sleep(2)

        self.assertEquals(c(), 1)

        self.assertEquals(
            Report.objects.all()[0].function,
            'kronika-uczelni')
