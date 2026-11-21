"""Session gone + HTMX load in the admin -> full navigation to the login page.

Regression: HTMX followed the login redirect and swapped the login form into
the fragment it was loading (e.g. the admin filter panel).
"""

import re

from django.contrib.sessions.models import Session
from django.contrib.staticfiles import finders
from playwright.sync_api import Page, expect

CHANGELIST = "/admin/bpp/autor/?nazwisko=Kowalski"


def _htmx_z_liveops(route):
    """Serve htmx.org from django-liveops when node_modules is missing.

    The admin loads ``htmx.org/dist/htmx.min.js``, found by YarnFinder in
    ``node_modules``. The CI test image has no ``node_modules``, so the script
    404s and ``window.htmx`` never exists. django-liveops (a Python dep,
    always installed) vendors the same htmx 1.x - use it as a fallback.
    """
    response = route.fetch()
    if response.ok:
        route.fulfill(response=response)
        return
    route.fulfill(
        path=finders.find("liveops/vendor/htmx.min.js"),
        content_type="application/javascript",
    )


def test_htmx_po_wygasnieciu_sesji_przechodzi_na_logowanie(
    channels_live_server, admin_page: Page, transactional_db
):
    admin_page.route("**/htmx.org/dist/htmx.min*.js", _htmx_z_liveops)
    admin_page.goto(channels_live_server.url + CHANGELIST)
    expect(admin_page.locator("#grp-content-container")).to_be_visible()
    admin_page.wait_for_function("() => window.htmx !== undefined")
    # Let the page's own background requests finish first, so none of them
    # can save a fresh authenticated session after we drop it.
    admin_page.wait_for_load_state("networkidle")

    # Session expired / server restarted: the browser still sends its
    # session cookie, but the server no longer knows it.
    Session.objects.all().delete()

    admin_page.evaluate(
        """() => htmx.ajax('GET', '/admin/bpp/autor/', {
            target: '#grp-content-container',
            select: '#grp-content-container',
        })"""
    )

    expect(admin_page).to_have_url(
        re.compile(r"/admin/login/\?next=%2Fadmin%2Fbpp%2Fautor%2F%3Fnazwisko"),
        timeout=20000,
    )
    # The login form is the whole page, not something nested in the old one.
    nested = "#grp-content-container #grp-content-container"
    expect(admin_page.locator(nested)).to_have_count(0)
    expect(admin_page.locator("input[name=password]")).to_have_count(1)
