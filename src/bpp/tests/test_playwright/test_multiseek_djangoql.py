import pytest
from django.test import Client
from django.urls.base import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import BppUser


def _login_cookie(user):
    """Zaloguj usera Clientem i zwróć ciasteczko sesji (dla kontekstu Playwright)."""
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


@pytest.mark.django_db
def test_drawer_shows_highlighted_query(page: Page, live_server):
    """Po kliknięciu przycisku szuflada pokazuje podświetlone DjangoQL,
    a link „Otwórz w edytorze" wskazuje na edytor zapytań."""
    admin = baker.make(BppUser, is_superuser=True, is_staff=True)
    sid = _login_cookie(admin)
    page.context.add_cookies(
        [{"name": "sessionid", "value": sid, "url": live_server.url}]
    )

    page.goto(live_server.url + reverse("multiseek:index"))
    page.evaluate("Cookielaw.accept()")

    page.click("#toDjangoqlButton")

    # Czekamy aż formatter wyrenderuje podświetlone tokeny.
    page.wait_for_selector("#djangoqlPretty span.dql-op")
    assert page.locator("#djangoqlPretty span.dql-name").count() >= 1
    assert page.locator("#djangoqlPretty span.dql-op").count() >= 1

    href = page.locator("#djangoqlOpenEditor").get_attribute("href")
    assert href and reverse("bpp:zapytanie") in href
    expect(page.locator("#djangoqlDrawer")).to_be_visible()
