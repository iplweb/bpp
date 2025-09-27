"""Playwright utility functions for tests."""

from playwright.sync_api import Page


def wait_for_page_load(page: Page, timeout: int = 10000):
    """Wait for page to fully load.

    Args:
        page: Playwright Page object
        timeout: Timeout in milliseconds (default 10000)
    """
    page.wait_for_load_state("networkidle", timeout=timeout)
    page.wait_for_function("() => document.readyState === 'complete'", timeout=timeout)
    page.wait_for_function("() => document.body !== null", timeout=timeout)


def wait_for_websocket_connection(page: Page, timeout: int = 10000):
    """Wait for WebSocket connection to be established.

    Args:
        page: Playwright Page object
        timeout: Timeout in milliseconds (default 10000)
    """
    try:
        page.wait_for_function(
            "() => typeof bppNotifications !== 'undefined' && "
            "bppNotifications.chatSocket && "
            "bppNotifications.chatSocket.readyState === 1",  # WebSocket.OPEN
            timeout=timeout,
        )
    except BaseException:
        # If bppNotifications doesn't exist, notifications might not be enabled on this page
        pass


def select_select2_autocomplete(
    page: Page,
    element_id: str,
    value: str,
    wait_for_new_value: bool = True,
    value_before_enter: str = None,
    timeout: int = 5000,
):
    """Fill a Select2 autocomplete control.

    Args:
        page: Playwright Page object
        element_id: ID of the element (without #)
        value: Text to type
        wait_for_new_value: Whether to wait for value to change
        value_before_enter: Text to wait for before pressing Enter
        timeout: Timeout in milliseconds
    """
    # Wait for Select2 container to be present
    container_selector = f"#select2-{element_id}-container"
    try:
        page.wait_for_selector(container_selector, timeout=timeout)
    except BaseException:
        # Fallback - try to find the select2 element directly
        container_selector = f"#{element_id} + .select2-container"
        page.wait_for_selector(container_selector, timeout=timeout)

    # Get current value (might be None if no container found)
    old_value = ""
    try:
        old_value = page.locator(container_selector).text_content() or ""
    except BaseException:
        pass

    # Click on the select2 element to open dropdown
    # Try different methods to open the dropdown
    try:
        # Method 1: Click on the container directly
        page.locator(container_selector).click()
    except BaseException:
        try:
            # Method 2: Click on the select2 selection element
            page.locator(
                f"#{element_id} + .select2-container .select2-selection"
            ).click()
        except BaseException:
            # Method 3: Use JavaScript to trigger the dropdown
            page.locator(f"#{element_id}").evaluate(
                """element => {
                    const sibling = element.nextElementSibling;
                    if (sibling && sibling.classList.contains('select2-container')) {
                        sibling.querySelector('.select2-selection').click();
                    }
                }"""
            )

    # Wait for dropdown to open
    page.wait_for_selector(".select2-dropdown", state="visible", timeout=timeout)

    # Type the search term
    search_input = page.locator(".select2-search__field")
    search_input.fill(value)

    if value_before_enter:
        # Wait for specific text to appear in results
        page.wait_for_function(
            f"() => document.querySelector('.select2-results').textContent.includes('{value_before_enter}')",
            timeout=timeout,
        )

    # Press Enter to select
    search_input.press("Enter")

    if wait_for_new_value:
        # Wait for the value to change
        page.wait_for_function(
            f"() => document.querySelector('{container_selector}').textContent !== '{old_value}'",
            timeout=timeout,
        )


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
