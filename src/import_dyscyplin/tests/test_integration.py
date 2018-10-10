import pytest
import time
from django.urls import reverse
from model_mommy import mommy

from bpp.models import Uczelnia
from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.django_db(transaction=True)
def test_integracyjny(preauth_admin_browser, live_server):
    mommy.make(Uczelnia)
    preauth_admin_browser.visit(live_server + reverse("import_dyscyplin:index"))

    preauth_admin_browser.find_by_id("download-example-file").click()
    time.sleep(2)

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_id("add-new-file").click()

    preauth_admin_browser.find_by_id("id_plik").type("/home/seluser/Downloads/default.xlsx")

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_id("id_submit").click()

    preauth_admin_browser.wait_for_condition(
        lambda browser: "Lubelski" in preauth_admin_browser.html
    )
