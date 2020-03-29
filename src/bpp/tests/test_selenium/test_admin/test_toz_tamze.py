# -*- encoding: utf-8 -*-
import time

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.tests import any_ciagle
from bpp.tests.util import any_zwarte, any_patent, assertPopupContains
from django_bpp.selenium_util import wait_for_page_load
import pytest

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def test_admin_wydawnictwo_ciagle_toz(preauth_admin_browser, nginx_live_server):
    Wydawnictwo_Ciagle.objects.all().delete()
    c = any_ciagle(informacje="TO INFORMACJE")

    preauth_admin_browser.visit(
        nginx_live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )

    wcc = Wydawnictwo_Ciagle.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id("toz")
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)
    assert preauth_admin_browser.is_element_present_by_id(
        "navigation-menu", wait_time=5000
    )

    assert wcc() == 2


def test_admin_wydawnictwo_zwarte_toz(preauth_admin_browser, nginx_live_server):
    c = any_zwarte(informacje="TO INFOMRACJE")

    preauth_admin_browser.visit(
        nginx_live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )

    wcc = Wydawnictwo_Zwarte.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id("toz")
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)
    preauth_admin_browser.is_element_present_by_id("navigation-menu", 5000)
    assert wcc() == 2


def test_admin_wydawnictwo_ciagle_tamze(preauth_admin_browser, nginx_live_server):
    c = any_ciagle(informacje="TO INFORMACJE", uwagi="te uwagi", www="te www")
    preauth_admin_browser.visit(
        nginx_live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )

    tamze = preauth_admin_browser.find_by_id("tamze")

    with wait_for_page_load(preauth_admin_browser):
        tamze.click()

    assert "Dodaj wydawnictwo" in preauth_admin_browser.html

    for elem in ["TO INFORMACJE", "te uwagi"]:
        assert elem in preauth_admin_browser.html, "BRAK %r" % elem
    assert "te www" not in preauth_admin_browser.html

    assert "te www" not in preauth_admin_browser.html


def test_admin_wydawnictwo_zwarte_tamze(
    preauth_admin_browser, nginx_live_server, wydawca
):
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
    preauth_admin_browser.visit(
        nginx_live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )
    tamze = preauth_admin_browser.find_by_id("tamze")
    tamze.click()
    time.sleep(1)
    assert "Dodaj wydawnictwo" in preauth_admin_browser.html
    for elem in [
        "TO INFORMACJE",
        "te uwagi",
        "te miejsce i rok",
        "te wydawnictwo",
        "Z_ISBN",
        "E_ISBN",
        "Wydawca Testowy",
    ]:
        assert elem in preauth_admin_browser.html, "BRAK %r" % elem
    assert "ten adres WWW" not in preauth_admin_browser.html


def test_admin_patent_toz(preauth_admin_browser, nginx_live_server):
    c = any_patent(informacje="TO INFORMACJE")
    preauth_admin_browser.visit(
        nginx_live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
    )

    wcc = Patent.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id("toz")
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)

    preauth_admin_browser.is_element_present_by_id("navigation-menu", 5000)
    assert wcc() == 2


def test_admin_patent_tamze(preauth_admin_browser, nginx_live_server):
    c = any_patent(informacje="TO INFORMACJE")
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.visit(
            nginx_live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
        )

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.execute_script("document.getElementById('tamze').click()")

    assert preauth_admin_browser.find_by_id("id_informacje").value == "TO INFORMACJE"
