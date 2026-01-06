import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Autor, Zrodlo


@pytest.fixture(scope="function")
def autorzy_page(page: Page, live_server):
    # Create many authors starting with A and B to ensure letter pills appear
    # even when filtered by letter (pagination requires > 1 page)
    for i in range(60):
        baker.make(Autor, nazwisko=f"Atest{i}", imiona="foo")
    for i in range(60):
        baker.make(Autor, nazwisko=f"Btest{i}", imiona="bar")

    page.goto(live_server.url + reverse("bpp:browse_autorzy"))
    page.wait_for_load_state("networkidle")
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

    # Click on letter A (using the letter pill selector from the modern template)
    page.locator("a.autorzy-letter-pill.autorzy-letter-single", has_text="A").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Atest")
    expect(page.locator("body")).not_to_contain_text("Btest")

    # Click on letter B
    page.locator("a.autorzy-letter-pill.autorzy-letter-single", has_text="B").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Btest")
    expect(page.locator("body")).not_to_contain_text("Atest")


@pytest.fixture(scope="function")
def zrodla_page(page: Page, live_server):
    # Create many sources starting with A and B to ensure letter pills appear
    # even when filtered by letter (pagination requires > 1 page)
    for i in range(80):
        baker.make(Zrodlo, nazwa=f"Atest{i}")
    for i in range(80):
        baker.make(Zrodlo, nazwa=f"Btest{i}")

    page.goto(live_server.url + reverse("bpp:browse_zrodla"))
    page.wait_for_load_state("networkidle")
    page.evaluate("Cookielaw.accept()")
    return page


@pytest.mark.django_db
@pytest.mark.serial
def test_zrodla_index(zrodla_page: Page):
    expect(zrodla_page.locator("body")).to_contain_text("Atest")


@pytest.mark.django_db
def test_zrodla_literki(zrodla_page: Page):
    page = zrodla_page

    # Click on letter A (using the letter pill selector from the template)
    page.locator("a.letter-pill.letter-single", has_text="A").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Atest")
    expect(page.locator("body")).not_to_contain_text("Btest")

    # Click on letter B
    page.locator("a.letter-pill.letter-single", has_text="B").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Btest")
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
