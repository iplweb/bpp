"""Playwright fixtures for authenticated browser sessions."""

import pytest
from playwright.sync_api import Page

# =============================================================================
# INWARIANT KOLEJNOŚCI PARAMETRÓW — NIE PRZESTAWIAĆ `transactional_db`!
#
# `transactional_db` MUSI być PIERWSZYM parametrem każdej z poniższych
# fikstur. Pytest tworzy fikstury o tym samym zasięgu (function) w kolejności
# lewa→prawa z sygnatury i finalizuje je w ODWROTNEJ kolejności (LIFO):
# fikstura utworzona jako ostatnia jest sprzątana jako pierwsza.
#
# `transactional_db` na końcu sygnatury → sprzątany PIERWSZY → jego
# TRUNCATE/flush bazy leci, GDY przeglądarka (page/context) jeszcze żyje i
# może mieć in-flight requesty do session-scoped Daphne. Serwer widzi
# częściowo wyczyszczoną bazę → ForeignKeyViolation / deadlock (realny
# IntegrityError z CI — audyt: docs/deweloper/audyt-testy-rownoleglosc-2026-07.md).
#
# `transactional_db` na POCZĄTKU sygnatury → tworzony PIERWSZY → sprzątany
# OSTATNI. Wtedy pytest-playwright zdąży zamknąć browser context (finalizer
# fikstury `new_context`, który woła `context.close()`) ZANIM baza zostanie
# wyczyszczona. Sam context.close() nie jest tu potrzebny — wystarczy
# kolejność parametrów, bo pytest-playwright zamyka context w swoim własnym
# finalizerze, a ten biegnie przed finalizerem `transactional_db`.
#
# `channels_live_server` jest session-scoped, więc jego pozycja w sygnaturze
# nie wpływa na sprzątanie między-testowe (żyje przez cały worker xdist).
# =============================================================================


@pytest.fixture
def admin_page(transactional_db, page: Page, admin_user, channels_live_server):
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
def preauth_page(transactional_db, page: Page, normal_django_user):
    """Provide a pre-authenticated regular user page.

    Uwaga: fikstura sama NIE startuje żadnego serwera — tylko wstrzykuje
    cookie sesji. Test, który nawiguje, musi sam zażądać `live_server`
    ALBO `channels_live_server`. Wcześniej `live_server` był tu zaszyty
    jako zależność, przez co `preauth_asgi_page` (budujący na tej
    fiksturze + `channels_live_server`) stawiał DWA serwery na test —
    dokładnie ta presja zasobowa, którą docstring `channels_live_server`
    wskazuje jako źródło kaskadowych timeoutów `page.goto`.
    """
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
def preauth_asgi_page(transactional_db, preauth_page: Page, channels_live_server):
    """Provide a pre-authenticated page with WebSocket connection."""
    # Import here to avoid Django app loading issues
    import time

    from channels_broadcast.core import get_channel_name_for_user

    from django_bpp.playwright_util import (
        wait_for_channel_subscription,
        wait_for_page_load,
        wait_for_websocket_connection,
    )

    page = preauth_page
    pre_goto = time.time()
    page.goto(channels_live_server.url)
    wait_for_page_load(page)
    wait_for_websocket_connection(page)
    wait_for_channel_subscription(
        get_channel_name_for_user(page.authorized_user), since=pre_goto
    )
    # Guard na wypadek, gdyby skrypt Cookielaw nie zdążył się załadować —
    # bez guarda gołe `Cookielaw.accept()` rzuca ReferenceError i cały test
    # pada na setupie fikstury.
    page.evaluate("if (window.Cookielaw) Cookielaw.accept();")
    # Cookielaw.accept() removes #CookielawBanner synchronously; wait for
    # the DOM to reflect that instead of sleeping a fixed second.
    page.wait_for_selector("#CookielawBanner", state="detached", timeout=2000)
    return page


# =============================================================================
# Function-scoped warianty: fresh Daphne per test.
#
# Domyślny `channels_live_server` jest session-scoped (jeden Daphne na
# worker xdist). Daje to ~2× szybszy run, ale niektóre testy są wrażliwe
# na pollution stanu między testami w shared ASGI procesie (np. wycieki
# DB connection w Daphne, race między test'em a server'em na widoczność
# committed danych). Te testy używają poniższych wariantów `_per_test`,
# które delegują do `channels_live_server_per_test` (function-scoped) —
# każdy test dostaje świeży Daphne + świeże konekcje.
# =============================================================================


@pytest.fixture
def admin_page_per_test(
    transactional_db, page: Page, admin_user, channels_live_server_per_test
):
    """Function-scoped wariant `admin_page` — fresh Daphne per test."""
    from django.test import Client

    client = Client()
    client.force_login(admin_user)
    session_cookie = client.cookies["sessionid"]

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

    page.authorized_user = admin_user
    return page


@pytest.fixture
def preauth_asgi_page_per_test(
    transactional_db, preauth_page: Page, channels_live_server_per_test
):
    """Function-scoped wariant `preauth_asgi_page` — fresh Daphne per test."""
    import time

    from channels_broadcast.core import get_channel_name_for_user

    from django_bpp.playwright_util import (
        wait_for_channel_subscription,
        wait_for_page_load,
        wait_for_websocket_connection,
    )

    page = preauth_page
    pre_goto = time.time()
    page.goto(channels_live_server_per_test.url)
    wait_for_page_load(page)
    wait_for_websocket_connection(page)
    wait_for_channel_subscription(
        get_channel_name_for_user(page.authorized_user), since=pre_goto
    )
    # Guard na wypadek, gdyby skrypt Cookielaw nie zdążył się załadować.
    page.evaluate("if (window.Cookielaw) Cookielaw.accept();")
    page.wait_for_selector("#CookielawBanner", state="detached", timeout=2000)
    return page
