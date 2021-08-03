# -*- encoding: utf-8 -*-

from selenium.webdriver.support.wait import WebDriverWait

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.tests import any_ciagle
from bpp.tests.util import any_patent, any_zwarte, assertPopupContains

from django_bpp.selenium_util import SHORT_WAIT_TIME, wait_for, wait_for_page_load

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def test_admin_wydawnictwo_ciagle_toz(admin_browser, asgi_live_server):
    Wydawnictwo_Ciagle.objects.all().delete()
    c = any_ciagle(informacje="TO INFORMACJE")

    admin_browser.visit(
        asgi_live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )

    wcc = Wydawnictwo_Ciagle.objects.count
    assert wcc() == 1

    toz = admin_browser.find_by_id("toz")

    toz.click()
    assertPopupContains(admin_browser, "Utworzysz kopię tego rekordu")
    wait_for(lambda: wcc() == 2)


def test_admin_wydawnictwo_zwarte_toz(admin_browser, asgi_live_server):
    c = any_zwarte(informacje="TO INFOMRACJE")

    admin_browser.visit(
        asgi_live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )

    wcc = Wydawnictwo_Zwarte.objects.count
    assert wcc() == 1

    toz = admin_browser.find_by_id("toz")
    toz.click()
    assertPopupContains(admin_browser, "Utworzysz kopię tego rekordu")
    wait_for(lambda: wcc() == 2)


def test_admin_wydawnictwo_ciagle_tamze(admin_browser, asgi_live_server):
    c = any_ciagle(informacje="TO INFORMACJE", uwagi="te uwagi", www="te www")
    admin_browser.visit(
        asgi_live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )

    tamze = admin_browser.find_by_id("tamze")

    with wait_for_page_load(admin_browser):
        tamze.click()

    assert "Dodaj wydawnictwo" in admin_browser.html

    for elem in ["TO INFORMACJE", "te uwagi"]:
        assert elem in admin_browser.html, "BRAK %r" % elem
    assert "te www" not in admin_browser.html

    assert "te www" not in admin_browser.html


def test_admin_wydawnictwo_zwarte_tamze(admin_browser, asgi_live_server, wydawca):
    c = any_zwarte(
        informacje="TO INFORMACJE",
        uwagi="te uwagi",
        miejsce_i_rok="te miejsce i rok",
        wydawca=wydawca,
        wydawca_opis="te wydawnictwo",
        www="ten adres WWW",
        isbn="Z_ISBN",
        e_isbn="E_ISBN",
    )
    admin_browser.visit(
        asgi_live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )
    tamze = admin_browser.find_by_id("tamze")
    tamze.click()
    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(
        lambda driver: "Dodaj wydawnictwo" in driver.page_source
    )
    for elem in [
        "TO INFORMACJE",
        "te uwagi",
        "te miejsce i rok",
        "te wydawnictwo",
        "Z_ISBN",
        "E_ISBN",
        "Wydawca Testowy",
    ]:
        assert elem in admin_browser.html, "BRAK %r" % elem
    assert "ten adres WWW" not in admin_browser.html


def test_admin_patent_toz(admin_browser, asgi_live_server):
    c = any_patent(informacje="TO INFORMACJE")
    admin_browser.visit(
        asgi_live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
    )

    wcc = Patent.objects.count
    assert wcc() == 1

    toz = admin_browser.find_by_id("toz")
    toz.click()

    assertPopupContains(admin_browser, "Utworzysz kopię tego rekordu")
    WebDriverWait(admin_browser, SHORT_WAIT_TIME).until(
        lambda driver: admin_browser.is_element_present_by_id("navigation-menu")
    )

    wait_for(lambda: wcc() == 2)


def test_admin_patent_tamze(admin_browser, asgi_live_server):
    c = any_patent(informacje="TO INFORMACJE")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            asgi_live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
        )

    with wait_for_page_load(admin_browser):
        admin_browser.execute_script("document.getElementById('tamze').click()")

    assert admin_browser.find_by_id("id_informacje").value == "TO INFORMACJE"
