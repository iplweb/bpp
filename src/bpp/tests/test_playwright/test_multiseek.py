import pytest
from django.urls.base import reverse
from playwright.sync_api import Page, expect

from bpp.models.cache import Rekord


@pytest.mark.django_db
def test_wyrzuc(wydawnictwo_zwarte, page: Page, live_server):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")

    page.click("#multiseek-szukaj")
    page.wait_for_load_state("networkidle")

    rekord_pk = Rekord.objects.all().first().js_safe_pk
    page.evaluate(f"multiseek.removeFromResults('{rekord_pk}')")

    # Wait for element to be struck through
    page.wait_for_function(
        """() => {
            const element = document.querySelector('.multiseek-element');
            return element && element.style.textDecoration.includes('line-through');
        }"""
    )

    page.goto(live_server.url + reverse("multiseek:results"))
    page.wait_for_load_state("networkidle")

    expect(page.locator("body")).to_contain_text("Z zapytania usunięto")

    page.click("#pokaz-jakie")

    page.evaluate(f"multiseek.removeFromResults('{rekord_pk}')")

    # Wait for element to NOT be struck through
    page.wait_for_function(
        """() => {
            const element = document.querySelector('.multiseek-element');
            return element && !element.style.textDecoration.includes('line-through');
        }"""
    )

    page.goto(live_server.url + reverse("multiseek:results"))
    page.wait_for_load_state("networkidle")

    expect(page.locator("body")).not_to_contain_text("Z zapytania usunięto")


def test_szukaj(page: Page, live_server):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")

    page.click("#multiseek-szukaj")
    page.wait_for_load_state("networkidle")

    # Check for both lowercase and uppercase error messages
    expect(page.locator("body")).not_to_contain_text("błąd serwera")
    expect(page.locator("body")).not_to_contain_text("Błąd serwera")


@pytest.mark.django_db
def test_multiseek_sortowanie_wg_zrodlo_lub_nadrzedne(
    uczelnia,
    page: Page,
    wydawnictwo_zwarte,
    statusy_korekt,
    admin_client,
    rf,
    live_server,
):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")
    page.wait_for_load_state("networkidle")

    page.select_option("#id_ordering_0", "9")  # wyd. nadrzedne/zrodlo
    page.click("#multiseek-szukaj")
    page.wait_for_load_state("networkidle")

    expect(page.locator("body")).not_to_contain_text("Błąd serwera")
    expect(page.locator("body")).not_to_contain_text("błąd serwera")


def test_multiseek_tabelka_wyswietlanie(page: Page, live_server):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")
    page.wait_for_load_state("networkidle")

    page.select_option("#id_report_type", "1")  # tabela
    page.click("#multiseek-szukaj")
    page.wait_for_load_state("networkidle")

    expect(page.locator("body")).not_to_contain_text("błąd serwera")
    expect(page.locator("body")).not_to_contain_text("Błąd serwera")
