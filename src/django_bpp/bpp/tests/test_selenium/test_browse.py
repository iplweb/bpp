# -*- encoding: utf-8 -*-
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from model_mommy import mommy
from selenium_helpers import SeleniumTestCase, wd
import time
from bpp.models import Autor, Zrodlo
from selenium.webdriver.common.keys import Keys


class AutorzyPage(wd()):
    def get_search_box(self):
        return self.find_element_by_name('search')


class TestAutorzyPage(SeleniumTestCase):
    url = reverse('bpp:browse_autorzy')
    pageClass = AutorzyPage

    available_apps = settings.INSTALLED_APPS

    def setUp(self):
        a = mommy.make(Autor, nazwisko='Atest', imiona='foo')
        SeleniumTestCase.setUp(self)

    def test_autorzy_index(self):
        self.assert_('Atest' in self.page.page_source)

    def test_autorzy_literki(self):
        literka = self.page.find_element_by_id("literka_A")
        literka.click()
        time.sleep(1)
        self.assert_('Atest' in self.page.page_source)

        literka = self.page.find_element_by_id("literka_B")
        literka.click()
        time.sleep(1)
        self.assert_('Atest' not in self.page.page_source)

    def test_autorzy_search_form(self):
        input = self.page.get_search_box()
        input.send_keys('Atest', Keys.RETURN)
        time.sleep(1)
        self.assert_('Atest' in self.page.page_source)

        input = self.page.get_search_box()
        input.send_keys(Keys.CONTROL, 'a')
        input.send_keys('Btest', Keys.RETURN)
        time.sleep(1)
        self.assert_('Atest' not in self.page.page_source)


class ZrodlaPage(wd()):
    def get_zrodlo_box(self):
        return self.find_element_by_name("search")


class TestZrodlaPage(SeleniumTestCase):
    url = reverse('bpp:browse_zrodla')
    pageClass = ZrodlaPage

    available_apps = settings.INSTALLED_APPS

    def setUp(self):
        mommy.make(Zrodlo, nazwa='Atest')
        SeleniumTestCase.setUp(self)

    def test_zrodla_index(self):
        self.assert_('Atest' in self.page.page_source)

    def test_zrodla_literki(self):
        literka = self.page.find_element_by_id("literka_A")
        literka.click()
        time.sleep(1)
        self.assert_('Atest' in self.page.page_source)

        literka = self.page.find_element_by_id("literka_B")
        literka.click()
        time.sleep(1)
        self.assert_('Atest' not in self.page.page_source)

    def test_zrodla_search_form(self):
        input = self.page.get_zrodlo_box()
        input.send_keys('Atest', Keys.RETURN)
        time.sleep(1)
        self.assert_('Atest' in self.page.page_source)

        input = self.page.get_zrodlo_box()
        input.send_keys(Keys.CONTROL, 'a')
        input.send_keys('Btest', Keys.RETURN)
        time.sleep(1)
        self.assert_('Atest' not in self.page.page_source)