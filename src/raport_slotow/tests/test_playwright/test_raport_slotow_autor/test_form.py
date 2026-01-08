import pytest
from django.urls import reverse
from playwright.sync_api import Page


@pytest.mark.django_db
def test_AutorRaportSlotowForm_javascript(admin_page: Page, live_server):
    url = live_server.url + reverse("raport_slotow:index")
    admin_page.goto(url)
    elem = admin_page.locator("#id_slot")
    elem.type("12")
    admin_page.keyboard.press("Tab")
    res = admin_page.locator("#id_dzialanie_0")
    assert not res.is_checked()

    elem.press_sequentially("", delay=0)  # Focus on element
    admin_page.keyboard.press("Backspace")
    admin_page.keyboard.press("Backspace")
    admin_page.keyboard.press("Tab")
    res = admin_page.locator("#id_dzialanie_0")
    assert res.is_checked()
