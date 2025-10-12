import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Autor, Zrodlo


@pytest.fixture(scope="function")
def autorzy_page(page: Page, live_server):
    baker.make(Autor, nazwisko="Atest", imiona="foo")

    for _a in range(100):
        baker.make(Autor)

    page.goto(live_server.url + reverse("bpp:browse_autorzy"))
    page.evaluate("Cookielaw.accept()")
    return page


@pytest.mark.django_db
def test_autorzy_search_form(autorzy_page: Page, live_server):
    page = autorzy_page

    # Search for "Atest"
    page.fill("input[name='search']", "Atest")
    page.press("input[name='search']", "Enter")
    page.wait_for_function(
        "() => document.body && document.body.textContent.includes('Atest')"
    )

    # Reload and search for "Btest"
    page.goto(live_server.url + reverse("bpp:browse_autorzy"))
    page.fill("input[name='search']", "Btest")
    page.press("input[name='search']", "Enter")
    page.wait_for_function(
        "() => document.body && !document.body.textContent.includes('Atest')"
    )


@pytest.mark.django_db
@pytest.mark.serial
def test_autorzy_literki(autorzy_page: Page):
    page = autorzy_page

    # Click on letter A
    page.get_by_role("link", name="A", exact=True).click()
    expect(page.locator("body")).to_contain_text("Atest")

    # Click on letter B
    page.goto(page.url + "..")
    page.get_by_role("link", name="B", exact=True).click()
    expect(page.locator("body")).not_to_contain_text("Atest")


@pytest.fixture(scope="function")
def zrodla_page(page: Page, live_server):
    baker.make(Zrodlo, nazwa="Atest")

    for _a in range(100):
        baker.make(Zrodlo)

    page.goto(live_server.url + reverse("bpp:browse_zrodla"))
    page.evaluate("Cookielaw.accept()")
    return page


@pytest.mark.django_db
def test_zrodla_index(zrodla_page: Page):
    expect(zrodla_page.locator("body")).to_contain_text("Atest")


@pytest.mark.django_db
def test_zrodla_literki(zrodla_page: Page):
    page = zrodla_page

    # Click on letter A
    page.get_by_role("link", name="A", exact=True).click()
    expect(page.locator("body")).to_contain_text("Atest")

    # Click on letter B
    page.goto(page.url + "..")
    page.get_by_role("link", name="B", exact=True).click()
    expect(page.locator("body")).not_to_contain_text("Atest")


@pytest.mark.django_db
def test_zrodla_search_form(zrodla_page: Page, live_server):
    page = zrodla_page

    # Search for "Atest"
    page.fill("input[name='search']", "Atest")
    page.press("input[name='search']", "Enter")
    page.wait_for_function(
        "() => document.body && document.body.textContent.includes('Atest')"
    )

    # Reload and search for "Btest"
    page.goto(live_server.url + reverse("bpp:browse_zrodla"))
    page.fill("input[name='search']", "Btest")
    page.press("input[name='search']", "Enter")
    page.wait_for_function(
        "() => document.body && !document.body.textContent.includes('Atest')"
    )
