import pytest
from model_bakery import baker
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bpp.models import Rekord, Wydawnictwo_Ciagle
from django_bpp.playwright_util import select_select2_autocomplete, wait_for_page_load


def open_global_search(page: Page) -> None:
    """Press "/" once to open the global-search modal — after the shortcut
    is actually live.

    The "/" shortcut is a document-level ``keydown`` handler installed by
    the modal script's IIFE, which in the same run also defines
    ``window.openGlobalSearch``. ``wait_for_page_load`` only blocks for
    ``domcontentloaded``, so on a slow (CI) page jQuery + that inline
    script may not have finished when the test runs — the handler isn't
    bound yet and a single ``press("/")`` is silently dropped. This is the
    flakiness #254 exposed by deleting the fixed ``time.sleep`` that used
    to wait the script out.

    Waiting for ``window.openGlobalSearch`` to exist is the precise
    readiness signal: it is defined by the same IIFE that binds the
    keydown listener, so once it is a function the shortcut is live. Then
    press "/" exactly once, the way a user would — the test still verifies
    that a single keystroke opens the dialog.
    """
    page.wait_for_function("() => typeof window.openGlobalSearch === 'function'")
    page.keyboard.press("/")
    page.wait_for_selector("#globalSearchInput", state="visible", timeout=5000)


def test_global_search_user(
    channels_live_server,
    page: Page,
    transactional_db,
):
    rec = None
    try:
        rec = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        Rekord.objects.full_refresh()

        assert Rekord.objects.count() >= 1
        assert Rekord.objects.filter(tytul_oryginalny__icontains="Test").exists()

        page.goto(channels_live_server.url)
        wait_for_page_load(page)

        # Accept cookies if needed (synchronous; banner gone once it returns).
        page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")

        # Open the global search dialog via the "/" shortcut (resilient to
        # the keydown handler not yet being live on a cold CI page).
        open_global_search(page)

        # Type the search term directly into the input
        page.fill("#globalSearchInput", "Test")

        # Wait for "Rekord" to appear in the dropdown
        page.wait_for_function(
            "() => document.querySelector('#globalSearchResults').textContent.includes('Rekord')",
            timeout=5000,
        )

        # Press Enter to select
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        wait_for_page_load(page)

        try:
            page.wait_for_function(
                "() => document.body.textContent.includes('Charakter formalny')",
                timeout=10000,
            )
        except PlaywrightTimeoutError as e:
            html_content = page.content()
            raise PlaywrightTimeoutError(f"Page content dump: {html_content}") from e

    finally:
        if rec is not None:
            rec.delete()


@pytest.mark.serial
def test_global_search_logged_in(
    channels_live_server_per_test,
    admin_page_per_test: Page,
    transactional_db,
):
    admin_page = admin_page_per_test
    rec = None
    try:
        # Create a unique title to avoid conflicts with other tests
        import uuid

        unique_title = f"Test_{uuid.uuid4().hex[:8]}"

        rec = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=unique_title)

        # Ensure the Rekord cache is refreshed for this specific record
        Rekord.objects.full_refresh()

        # Verify the record was properly indexed
        assert Rekord.objects.filter(
            tytul_oryginalny__icontains=unique_title
        ).exists(), (
            f"Record with title '{unique_title}' not found in Rekord cache after refresh"
        )

        admin_page.goto(channels_live_server_per_test.url)
        wait_for_page_load(admin_page)

        # Accept cookies if needed (synchronous; banner gone once it returns).
        admin_page.evaluate(
            "if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }"
        )

        # Open the global search dialog via the "/" shortcut (resilient to
        # the keydown handler not yet being live on a cold CI page).
        open_global_search(admin_page)

        # Type the search term directly into the input - use the unique title
        admin_page.fill("#globalSearchInput", unique_title)

        # Wait for "Rekord" to appear in the dropdown
        admin_page.wait_for_function(
            "() => document.querySelector('#globalSearchResults').textContent.includes('Rekord')",
            timeout=5000,
        )

        # Press Enter to select
        admin_page.keyboard.press("ArrowDown")
        admin_page.keyboard.press("Enter")
        wait_for_page_load(admin_page)

        try:
            admin_page.wait_for_function(
                "() => document.body.textContent.includes('Charakter formalny')",
                timeout=10000,
            )
        except PlaywrightTimeoutError as e:
            html_content = admin_page.content()
            raise PlaywrightTimeoutError(f"Page content dump: {html_content}") from e
    finally:
        if rec is not None:
            # Delete the record and ensure it's removed from cache
            rec.delete()


def test_global_search_in_admin(
    channels_live_server, admin_page: Page, transactional_db
):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    admin_page.goto(channels_live_server.url + "/admin/")
    wait_for_page_load(admin_page)

    # Accept cookies if needed
    admin_page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")

    select_select2_autocomplete(
        admin_page,
        "id_global_nav_value",
        "Test",
        value_before_enter="ydawnictwo",
        wait_for_new_value=False,  # False, bo zmiana wartosci powoduje wczytanie strony
    )
    wait_for_page_load(admin_page)

    admin_page.wait_for_function(
        "() => document.body.textContent.includes('Zmień wydawnictwo ciągłe')",
        timeout=10000,
    )
