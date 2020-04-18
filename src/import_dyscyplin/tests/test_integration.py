import os

import pytest
from django.urls import reverse
from flaky import flaky
from model_mommy import mommy

from bpp.models import Uczelnia
from django_bpp.selenium_util import wait_for_page_load


@flaky(max_runs=5)
@pytest.mark.django_db(transaction=True)
def test_integracyjny(preauth_admin_browser, nginx_live_server):
    mommy.make(Uczelnia)
    preauth_admin_browser.visit(
        nginx_live_server.url + reverse("import_dyscyplin:index")
    )

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_id("add-new-file").click()

    preauth_admin_browser.find_by_id("id_plik").type(
        os.path.join(
            os.path.dirname(__file__), "../static/import_dyscyplin/xlsx/default.xlsx"
        )
    )

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_id("id_submit").click()

    btn = preauth_admin_browser.find_by_id("submit-id-submit")
    btn[0]._element.location_once_scrolled_into_view

    with wait_for_page_load(preauth_admin_browser):
        btn.click()

    preauth_admin_browser.wait_for_condition(
        lambda browser: "Lubelski" in preauth_admin_browser.html
    )
