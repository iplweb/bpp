# -*- encoding: utf-8 -*-
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from selenium.webdriver.common import desired_capabilities
from selenium_helpers import SeleniumTestCase, MyWebDriver
from bpp.tests.test_selenium import wait

DEFAULT_USERNAME = "foo"
DEFAULT_EMAIL = "x"
DEFAULT_PASSWORD = "bar"


class Mixin:
    def create_admin_user(self):
        User = get_user_model()
        User.objects.create_superuser(
            username=DEFAULT_USERNAME,
            email=DEFAULT_EMAIL,
            password=DEFAULT_PASSWORD)

class SeleniumLoggedInTestCase(Mixin, SeleniumTestCase):
    """Tworzy użytkownika z zadanymi parametrami, następnie loguje się
    na niego. """

    def setUp(self):
        SeleniumTestCase.setUp(self)

        self.create_admin_user()

        self.open(reverse("login_form"))
        self.page.find_element_by_id("id_username").send_keys(DEFAULT_USERNAME)
        self.page.find_element_by_id("id_password").send_keys(DEFAULT_PASSWORD)
        self.page.find_element_by_id("id_submit").click()

        self.page.wait_for_id("password-change-link")

        self.open(self.url)


class SeleniumLoggedInAdminTestCase(Mixin, SeleniumTestCase):
    """Klasa testów test_selenium dla użytkownika administracyjnego, logującego
    się bezpośrednio do admina."""

    available_apps = settings.INSTALLED_APPS # dla sqlflush

    def setUp(self):
        if not self.url.startswith("/admin/"):
            raise Exception("Hej, ta klasa jest *tylko* do testow admina")

        SeleniumTestCase.setUp(self)
        self.create_admin_user()

        self.page.find_element_by_id("id_username").send_keys(DEFAULT_USERNAME)
        self.page.find_element_by_id("id_password").send_keys(DEFAULT_PASSWORD)
        self.page.find_element_by_class_name("grp-button").click()
        self.page.wait_for_id("navigation-menu")
