"""Playwright utility functions for tests."""

from playwright.sync_api import Page


def wait_for_page_load(
    page: Page, timeout: int = 10000, load_state: str = "domcontentloaded"
):
    """Wait for page to fully load.

    Args:
        page: Playwright Page object
        timeout: Timeout in milliseconds (default 10000)
        load_state: Load state to wait for (default "domcontentloaded").
                   Options: "load", "domcontentloaded", "networkidle".
                   Note: "networkidle" may not work with WebSocket connections.
    """
    page.wait_for_load_state(load_state, timeout=timeout)
    page.wait_for_function("() => document.readyState === 'complete'", timeout=timeout)
    page.wait_for_function("() => document.body !== null", timeout=timeout)


def wait_for_websocket_connection(page: Page, timeout: int = 10000):
    """Wait for WebSocket connection to be established.

    Args:
        page: Playwright Page object
        timeout: Timeout in milliseconds (default 10000)
    """
    page.wait_for_function(
        "() => typeof bppNotifications !== 'undefined' && "
        "bppNotifications.chatSocket && "
        "bppNotifications.chatSocket.readyState === 1",  # WebSocket.OPEN
        timeout=timeout,
    )


def select_select2_autocomplete(
    page: Page,
    element_id: str,
    value: str,
    wait_for_new_value: bool = True,
    value_before_enter: str = None,
    timeout: int = 10000,
):
    """Fill a Select2 autocomplete control with AJAX support.

    Args:
        page: Playwright Page object
        element_id: ID of the element (without #)
        value: Text to type to search
        wait_for_new_value: Whether to wait for value to change after selection
        value_before_enter: Deprecated, not used
        timeout: Timeout in milliseconds (default 10000)
    """
    # Wait for Select2 to be initialized. Two markup variants coexist:
    #   - django-autocomplete-light: ``<select> + .select2-container`` (sibling)
    #   - vanilla django-admin: ``#select2-{id}-container`` (rendered span)
    # Both are usually present after init. Wait for either to appear, then
    # always click on ``.select2-selection`` (inside the sibling container)
    # — that's the element Select2 actually wires the dropdown toggle to.
    id_selector = f"#select2-{element_id}-container"
    sibling_selector = f"#{element_id} + .select2-container"
    selection_selector = f"#{element_id} + .select2-container .select2-selection"
    page.wait_for_selector(f"{id_selector}, {sibling_selector}", timeout=timeout)

    # Get the underlying select element's current value
    select_selector = f"#{element_id}"
    old_select_value = page.locator(select_selector).input_value()

    # Open the dropdown by clicking on the selection element. Fall back to
    # JS-triggered click if the locator click fails (e.g. element is
    # off-screen on a tall admin form).
    try:
        page.locator(selection_selector).click(timeout=5000)
    except Exception:
        page.locator(select_selector).evaluate(
            """element => {
                const sibling = element.nextElementSibling;
                if (sibling && sibling.classList.contains('select2-container')) {
                    sibling.querySelector('.select2-selection').click();
                }
            }"""
        )

    # Wait for dropdown to open
    page.wait_for_selector(".select2-dropdown", state="visible", timeout=timeout)

    # Type the search term using pressSequentially to trigger AJAX search
    search_input = page.locator(".select2-search__field")
    search_input.press_sequentially(value, delay=50)

    # Wait for AJAX search to complete by checking for loading indicators to disappear
    # Polish text "Trwa wyszukiwanie…" or "Trwa ładowanie…" indicates loading
    page.wait_for_function(
        """() => {
            const results = document.querySelector('.select2-results');
            if (!results) return false;
            const text = results.textContent;
            // Wait until loading messages disappear and we have actual results
            const isLoading = text.includes('Trwa wyszukiwanie')
                           || text.includes('Trwa ładowanie')
                           || text.includes('Searching')
                           || text.includes('Loading');
            const hasResults = document.querySelectorAll(
                '.select2-results__option:not(.loading-results):not(.select2-results__message)'
            ).length > 0;
            return !isLoading && hasResults;
        }""",
        timeout=timeout,
    )

    # Press Enter to select the first/highlighted result
    search_input.press("Enter")

    # Wait for the actual signals that selection propagated:
    # (1) Select2 closes the dropdown after Enter, (2) underlying <select>
    # value changes. Both are event-driven — no need for a fixed sleep.
    try:
        page.wait_for_selector(".select2-dropdown", state="hidden", timeout=2000)
    except Exception:
        # Force close if still open
        page.evaluate("django.jQuery('.select2-hidden-accessible').select2('close')")

    if wait_for_new_value:
        # Wait for the underlying select value to change
        page.wait_for_function(
            f"() => document.querySelector('{select_selector}').value !== "
            f"'{old_select_value}'",
            timeout=timeout,
        )
    else:
        # No event-driven signal available — small polishing wait so the
        # next interaction starts after Select2's internal change handlers
        # finish (jQuery 'change' listeners run synchronously, but custom
        # widgets may queue setTimeout(0) callbacks).
        page.wait_for_timeout(50)


def close_all_select2_dropdowns(page: Page):
    """Close any open Select2 dropdowns to ensure clean DOM state.

    Args:
        page: Playwright Page object
    """
    page.evaluate(
        """() => {
        if (typeof django !== 'undefined' && django.jQuery) {
            django.jQuery('.select2-hidden-accessible').select2('close');
        }
    }"""
    )
    page.wait_for_timeout(100)


def proper_click_element(page: Page, selector: str):
    """Click an element using JavaScript to ensure it's clickable.

    Args:
        page: Playwright Page object
        selector: CSS selector for the element
    """
    # Scroll element into view and click via JavaScript
    page.locator(selector).evaluate(
        """element => {
            element.scrollIntoView();
            element.click();
        }"""
    )
