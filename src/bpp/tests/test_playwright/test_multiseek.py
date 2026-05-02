import pytest
from django.urls.base import reverse
from playwright.sync_api import Page, expect

from bpp.models.cache import Rekord


@pytest.mark.django_db
def test_wyrzuc(wydawnictwo_zwarte, page: Page, live_server):
    """Test that removeFromResults function works - strikes through the element."""
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")

    # Load results into iframe using the preview button (POSTs to
    # ./live-results/ targeting the list_frame iframe). Wait for the POST
    # response so we know the iframe is about to navigate.
    with page.expect_response(
        lambda r: "live-results" in r.url and r.request.method == "POST"
    ):
        page.click("#sendQueryButton")

    # Get the iframe and wait for the navigation triggered by the POST to
    # complete. ``domcontentloaded`` on the frame returns once the new
    # document is parsed — ``.evaluate`` would otherwise race the previous
    # execution context being torn down by the navigation.
    iframe_frame = page.frame(name="list_frame")
    iframe_frame.wait_for_load_state("domcontentloaded")

    # Then wait for the actual result element to render
    iframe_frame.locator(".multiseek-element").first.wait_for(timeout=15000)

    # Call removeFromResults in iframe context (element is in iframe)
    rekord_pk = Rekord.objects.all().first().js_safe_pk
    iframe_frame.evaluate(f"multiseek.removeFromResults('{rekord_pk}')")

    # Wait for element to be struck through in iframe
    iframe_frame.wait_for_function(
        """() => {
            const element = document.querySelector('.multiseek-element');
            return element && element.style.textDecoration.includes('line-through');
        }"""
    )

    # Call again to restore (toggle behavior)
    iframe_frame.evaluate(f"multiseek.removeFromResults('{rekord_pk}')")

    # Wait for element to NOT be struck through
    iframe_frame.wait_for_function(
        """() => {
            const element = document.querySelector('.multiseek-element');
            return element && !element.style.textDecoration.includes('line-through');
        }"""
    )


def test_szukaj(page: Page, live_server):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")

    # #multiseek-szukaj (submit-mine) POSTs to ./results/ and navigates the
    # parent window. Use expect_navigation so we block until that nav
    # completes — without it, the assertions below could pass on the
    # pre-search page (which has no error message either).
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click("#multiseek-szukaj")

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
    # Wait until the form is ready instead of for networkidle.
    page.wait_for_selector("#multiseek-szukaj", state="visible")

    page.select_option("#id_ordering_0", "9")  # wyd. nadrzedne/zrodlo
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click("#multiseek-szukaj")

    expect(page.locator("body")).not_to_contain_text("Błąd serwera")
    expect(page.locator("body")).not_to_contain_text("błąd serwera")


def test_multiseek_tabelka_wyswietlanie(page: Page, live_server):
    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")
    page.wait_for_selector("#multiseek-szukaj", state="visible")

    page.select_option("#id_report_type", "1")  # tabela
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click("#multiseek-szukaj")

    expect(page.locator("body")).not_to_contain_text("błąd serwera")
    expect(page.locator("body")).not_to_contain_text("Błąd serwera")


@pytest.mark.django_db
def test_index_copernicus_schowany(page: Page, live_server, uczelnia):
    """Test that Index Copernicus is hidden when uczelnia setting is False."""
    uczelnia.pokazuj_index_copernicus = False
    uczelnia.save()

    page.goto(live_server.url + reverse("multiseek:index"))
    page.wait_for_load_state("domcontentloaded")

    assert "Index Copernicus" not in page.content()


@pytest.mark.django_db
def test_index_copernicus_widoczny(page: Page, live_server, uczelnia):
    """Test that Index Copernicus is visible when uczelnia setting is True."""
    uczelnia.pokazuj_index_copernicus = True
    uczelnia.save()

    page.goto(live_server.url + reverse("multiseek:index"))
    page.wait_for_load_state("domcontentloaded")

    assert "Index Copernicus" in page.content()
