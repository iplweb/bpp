"""Playwright fixtures for authenticated browser sessions."""

import pytest
from playwright.sync_api import Page


@pytest.fixture
def admin_page(page: Page, admin_user, live_server, transactional_db):
    """Provide a pre-authenticated admin page."""
    # Import here to avoid Django app loading issues
    from django.test import Client

    # First, we need to get the session cookie from Django
    client = Client()
    client.force_login(admin_user)

    # Get the session cookie from the test client
    session_cookie = client.cookies["sessionid"]

    # Add the cookie to the Playwright page
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie.value,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )

    # Store the user on the page object for compatibility
    page.authorized_user = admin_user

    return page


@pytest.fixture
def preauth_page(page: Page, normal_django_user, live_server, transactional_db):
    """Provide a pre-authenticated regular user page."""
    # Import here to avoid Django app loading issues
    from django.test import Client

    # First, we need to get the session cookie from Django
    client = Client()
    client.force_login(normal_django_user)

    # Get the session cookie from the test client
    session_cookie = client.cookies["sessionid"]

    # Add the cookie to the Playwright page
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie.value,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )

    # Store the user on the page object for compatibility
    page.authorized_user = normal_django_user

    return page


@pytest.fixture
def preauth_asgi_page(preauth_page: Page, channels_live_server, transactional_db):
    """Provide a pre-authenticated page with WebSocket connection."""
    # Import here to avoid Django app loading issues
    from django_bpp.playwright_util import (
        wait_for_page_load,
        wait_for_websocket_connection,
    )

    page = preauth_page
    page.goto(channels_live_server.url)
    wait_for_page_load(page)
    wait_for_websocket_connection(page)
    page.evaluate("Cookielaw.accept();")
    import time

    time.sleep(1)
    return page
