from urllib.parse import urlencode

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


@pytest.mark.django_db
def test_zapytanie_przelaczanie_postaci_przez_formularz_get(
    page: Page, live_server, wydawnictwo_ciagle, denorms
):
    """Wybór postaci wyniku (`<select id="id_postac">`) jedzie razem z
    zapytaniem przez formularz GET strony `/zapytanie/`.

    Test dowodzi, że wybór w select-u faktycznie DZIAŁA (nie tylko że strona
    się ładuje): domyślna postać „rekordy" renderuje tabelę redakcyjną z
    komórkami ID (`td.rekord-id-cell`), a po przełączeniu na „lista" i
    złożeniu formularza URL zawiera `postac=list`, tabela redakcyjna znika,
    a w jej miejsce pojawia się partial multiseeka
    (`.multiseek-list-report`) z tytułem utworzonej publikacji. Gdyby select
    nie jechał przez formularz albo widok/partial były zepsute, ta asercja
    by padła.
    """
    denorms.flush()

    admin = baker.make(BppUser, is_superuser=True, is_staff=True)
    sid = _login_cookie(admin)
    page.context.add_cookies(
        [{"name": "sessionid", "value": sid, "url": live_server.url}]
    )

    query = f"rok = {wydawnictwo_ciagle.rok}"
    params = urlencode({"model": "rekord", "query": query})
    page.goto(f"{live_server.url}{reverse('bpp:zapytanie')}?{params}")
    page.evaluate("Cookielaw.accept()")

    # Domyślna postać „rekordy" — tabela redakcyjna z komórkami ID, bez
    # partiala multiseeka. `.rekord-id-cell` jest unikalna dla tej tabeli
    # (strona pomocy z przykładami ma inne tabele `table.hover.stack`).
    expect(page.locator("td.rekord-id-cell").first).to_be_visible()
    expect(page.locator(".multiseek-list-report")).to_have_count(0)

    page.select_option("#id_postac", "list")
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click("button[type=submit]")

    assert "postac=list" in page.url

    expect(page.locator(".multiseek-list-report")).to_be_visible()
    expect(page.locator(".multiseek-list-report")).to_contain_text(
        wydawnictwo_ciagle.tytul_oryginalny
    )
    expect(page.locator("td.rekord-id-cell")).to_have_count(0)
