"""Widget wsparcia Freshworks w adminie ładuje się LENIWIE — skrypt z
``euc-widget.freshworks.com`` jest wstrzykiwany dopiero po kliknięciu
przycisku „Support BPP" (``#bppSupportButton``), a nie na każdej stronie.

Szablon ``admin/base_site.html`` renderuje widget tylko przy
``TESTING=False``. Strony serwuje osobny proces Daphne, więc
``settings``/``override_settings`` w procesie testowym go nie dotyczą —
stąd własna fixture z callbackiem ``setup_freshworks_daphne``, który ustawia
``TESTING=False`` W SUBPROCESIE (wzorzec z ``test_zglos_captcha_gating.py``).

Test NIE sięga do internetu: każdy request do domeny Freshworks
przechwytuje ``page.route`` i podstawia stub skryptu, który — jak prawdziwy
bootstrap Freshworks (``widgetRenderComplete``) — odtwarza kolejkę ``.q``
stuba i podmienia ``window.FreshworksWidget``.
"""

import pytest
from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load
from integration_tests._freshworks_daphne_setup import setup_freshworks_daphne

ADMIN_URL = "/admin/bpp/zrodlo/"
FRESHWORKS_ROUTE = "**/euc-widget.freshworks.com/**"

# Imitacja bootstrapu Freshworks: odtwórz kolejkę stuba, potem podmień
# window.FreshworksWidget na funkcję, która tylko zapisuje wywołania.
STUB_WIDGET_JS = """
(function () {
    window.__fwCalls = window.__fwCalls || [];
    var queued = (window.FreshworksWidget && window.FreshworksWidget.q) || [];
    window.FreshworksWidget = function () {
        window.__fwCalls.push(Array.prototype.slice.call(arguments));
    };
    queued.forEach(function (args) {
        window.FreshworksWidget.apply(null, args);
    });
})();
"""


@pytest.fixture
def freshworks_live_server(transactional_db):
    """Per-test Daphne z ``TESTING=False`` (widget renderuje się w adminie)."""
    from channels_live_server import _spawn_daphne

    server, server_process, modified_settings = _spawn_daphne(
        setup=setup_freshworks_daphne
    )
    try:
        yield server
    finally:
        server_process.terminate()
        server_process.join()
        modified_settings.disable()


def _track_freshworks(page: Page, abort=False):
    """Przechwyć domenę Freshworks; zwróć listę URL-i requestów do niej."""
    requests = []

    def handler(route):
        requests.append(route.request.url)
        if abort:
            route.abort()
        else:
            route.fulfill(
                status=200,
                content_type="application/javascript",
                body=STUB_WIDGET_JS,
            )

    page.route(FRESHWORKS_ROUTE, handler)
    return requests


def _calls(page: Page):
    return page.evaluate("() => window.__fwCalls || []")


def test_freshworks_widget_laduje_sie_dopiero_po_kliknieciu(
    freshworks_live_server, admin_page: Page
):
    requests = _track_freshworks(admin_page)

    admin_page.goto(freshworks_live_server.url + ADMIN_URL)
    wait_for_page_load(admin_page)
    admin_page.wait_for_load_state("networkidle")

    button = admin_page.locator("#bppSupportButton")
    assert button.is_visible()

    # Na starcie: zero requestów do Freshworks i brak tagu <script>.
    assert requests == []
    assert admin_page.locator("script[src*='freshworks.com']").count() == 0

    # Pierwsze kliknięcie: skrypt wstrzyknięty raz, kolejka odtworzona.
    button.click()
    admin_page.wait_for_function("() => (window.__fwCalls || []).length >= 4")
    assert len(requests) == 1
    assert requests[0].endswith("/widgets/205000000433.js")

    calls = _calls(admin_page)
    assert [c[0] for c in calls] == ["hide", "prefill", "identify", "open"]
    assert calls[0] == ["hide", "launcher"]
    assert calls[1][2]["custom_fields"]["cf_adres_url"] == admin_page.url
    assert calls[2][2]["email"] == admin_page.authorized_user.email

    # Stan „ładowanie" znika, gdy widget podmieni stuba.
    admin_page.wait_for_function(
        "() => !document.querySelector('#bppSupportButton')"
        "  .classList.contains('is-loading')"
    )

    # Drugie kliknięcie: close, bez ponownego wstrzykiwania skryptu.
    button.click()
    assert [c[0] for c in _calls(admin_page)][4:] == ["close"]

    # Trzecie: znów open.
    button.click()
    assert [c[0] for c in _calls(admin_page)][4:] == ["close", "open"]

    assert len(requests) == 1
    assert admin_page.locator("script[src*='freshworks.com']").count() == 1


def test_freshworks_widget_szybkie_klikanie_nie_wstrzykuje_dwa_razy(
    freshworks_live_server, admin_page: Page
):
    requests = _track_freshworks(admin_page)

    admin_page.goto(freshworks_live_server.url + ADMIN_URL)
    wait_for_page_load(admin_page)

    # Dwa kliknięcia w tym samym ticku — skrypt nie zdąży się załadować.
    admin_page.evaluate(
        "() => { const b = document.querySelector('#bppSupportButton');"
        "  b.click(); b.click(); }"
    )
    admin_page.wait_for_function("() => (window.__fwCalls || []).length >= 4")
    admin_page.wait_for_load_state("networkidle")

    assert len(requests) == 1
    assert admin_page.locator("script[src*='freshworks.com']").count() == 1
    assert [c[0] for c in _calls(admin_page)] == [
        "hide",
        "prefill",
        "identify",
        "open",
    ]


def test_freshworks_widget_blad_ladowania(freshworks_live_server, admin_page: Page):
    requests = _track_freshworks(admin_page, abort=True)

    admin_page.goto(freshworks_live_server.url + ADMIN_URL)
    wait_for_page_load(admin_page)

    button = admin_page.locator("#bppSupportButton")
    button.click()

    admin_page.wait_for_selector("#bppSupportButton.is-error", timeout=10000)
    assert len(requests) == 1
    assert "support.iplweb.pl" in button.get_attribute("title")
    assert "is-loading" not in button.get_attribute("class")
