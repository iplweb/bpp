# -*- encoding: utf-8 -*-
import time

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test.testcases import LiveServerTestCase
from selenium.webdriver.common.keys import Keys
from splinter.browser import Browser
from celeryui.models import Report
from django.conf import settings
from bpp.models.system import Jezyk, Status_Korekty
from bpp.tests.util import any_autor, CURRENT_YEAR, any_ciagle, any_jednostka
import pytest

@pytest.fixture
def raporty_browser(preauth_browser, live_server):
    preauth_browser.visit(live_server + reverse("bpp:raporty"))
    return preauth_browser

def wybrany(browser):
    return browser.execute_script(
        "$('section.active div[data-slug]').attr('data-slug')")

def submit_page(browser):
    browser.execute_script("$('input[name=submit]:visible').click()")

pytestmark = [pytest.mark.slow, pytest.mark.selenium]

@pytest.mark.django_db
@pytest.fixture
def jednostka_raportow():
    Status_Korekty.objects.get_or_create(pk=1, nazwa="przed korektą")

    j = any_jednostka(nazwa="Jednostka")
    a = any_autor()

    c = any_ciagle(rok=CURRENT_YEAR)
    c.dodaj_autora(a, j)

    d = any_ciagle(rok=CURRENT_YEAR - 1)
    d.dodaj_autora(a, j)

    e = any_ciagle(rok=CURRENT_YEAR - 2)
    e.dodaj_autora(a, j)

    return j

@pytest.mark.django_db
def test_submit(raporty_browser, jednostka_raportow, live_server):
    raporty_browser.visit(live_server + reverse("bpp:raport_jednostek_formularz"))
    submit_page(raporty_browser)
    time.sleep(3)

    assert "To pole jest wymagane" in raporty_browser.html

@pytest.mark.django_db
def test_ranking_autorow(raporty_browser, jednostka_raportow, live_server):
    raporty_browser.visit(live_server + reverse("bpp:ranking_autorow_formularz"))
    assert 'value="%s"' % (CURRENT_YEAR - 1) in raporty_browser.html


@pytest.mark.django_db
def test_raport_jednostek(raporty_browser, jednostka_raportow, live_server):
    raporty_browser.visit(live_server + reverse("bpp:raport_jednostek_formularz"))

    elem = raporty_browser.find_by_id("id_jednostka-autocomplete")[0]
    elem.type("Jedn")
    time.sleep(2)
    elem.type(Keys.TAB)
    time.sleep(1)

    raporty_browser.execute_script('$("input[name=od_roku]:visible").val("' + str(CURRENT_YEAR) + '")')
    raporty_browser.execute_script('$("input[name=do_roku]:visible").val("' + str(CURRENT_YEAR) + '")')
    submit_page(raporty_browser)
    time.sleep(2)

    assert '/bpp/raporty/raport-jednostek-2012/%s/%s/' % (jednostka_raportow.pk, CURRENT_YEAR) in raporty_browser.url


@pytest.mark.django_db
def test_submit_kronika_uczelni(raporty_browser, jednostka_raportow, live_server):
    c = Report.objects.all().count
    assert c() == 0

    raporty_browser.visit(live_server + reverse("bpp:raport_kronika_uczelni"))
    raporty_browser.execute_script('$("input[name=rok]").val("' + str(CURRENT_YEAR) + '")')
    submit_page(raporty_browser)
    time.sleep(2)

    assert c() == 1

    assert Report.objects.all()[0].function == 'kronika-uczelni'
