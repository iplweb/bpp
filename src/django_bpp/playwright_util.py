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
    # Wait for Select2 container to be present
    container_selector = f"#select2-{element_id}-container"
    try:
        page.wait_for_selector(container_selector, timeout=timeout)
    except Exception:
        # Fallback - try to find the select2 element directly
        container_selector = f"#{element_id} + .select2-container"
        page.wait_for_selector(container_selector, timeout=timeout)

    # Get the underlying select element's current value
    select_selector = f"#{element_id}"
    old_select_value = page.locator(select_selector).input_value()

    # Click on the select2 element to open dropdown
    # Try different methods to open the dropdown
    try:
        # Method 1: Click on the container directly
        page.locator(container_selector).click()
    except Exception:
        try:
            # Method 2: Click on the select2 selection element
            page.locator(
                f"#{element_id} + .select2-container .select2-selection"
            ).click()
        except Exception:
            # Method 3: Use JavaScript to trigger the dropdown
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

    # Wait for selection to propagate (increased from 500ms to 750ms for stability)
    page.wait_for_timeout(750)

    # Verify dropdown is closed after selection to ensure clean state for next operation
    try:
        page.wait_for_selector(".select2-dropdown", state="hidden", timeout=2000)
    except Exception:
        # Force close if still open
        page.evaluate("django.jQuery('.select2-hidden-accessible').select2('close')")
        page.wait_for_timeout(200)

    if wait_for_new_value:
        # Wait for the underlying select value to change
        page.wait_for_function(
            f"() => document.querySelector('{select_selector}').value !== "
            f"'{old_select_value}'",
            timeout=timeout,
        )


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
