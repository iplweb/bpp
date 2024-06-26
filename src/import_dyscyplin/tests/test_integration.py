import os

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from bpp.tests import proper_click_element

from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.django_db(transaction=True)
def test_integracyjny(admin_browser, channels_live_server):
    baker.make(Uczelnia)
    admin_browser.visit(channels_live_server.url + reverse("import_dyscyplin:index"))

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_id("add-new-file").click()

    admin_browser.find_by_id("id_plik").type(
        os.path.join(
            os.path.dirname(__file__), "../static/import_dyscyplin/xlsx/default.xlsx"
        )
    )

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_id("id_submit").click()

    btn = admin_browser.find_by_id("submit-id-submit")
    btn[0]._element.location_once_scrolled_into_view

    with wait_for_page_load(admin_browser):
        proper_click_element(admin_browser, btn)
        # btn.click()

    admin_browser.wait_for_condition(lambda browser: "Lubelski" in admin_browser.html)
