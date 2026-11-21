"""FD#526: the admin top menu must stay on top of the quick search suggestions.

The quick search box ("Wpisz, aby wyszukać...") is a select2 widget whose
dropdown is attached to <body>. The admin header is a fixed element with its
own stacking context, so the open menu used to be drawn below the dropdown.
"""

from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load

DROPDOWN = ".select2-container--open .select2-dropdown"

# First top-level menu item that has a submenu.
MENU_ITEM_WITH_SUBMENU = "#navigation-menu > li:has(> ul)"


def _open_quick_search(admin_page: Page, url: str) -> None:
    # Narrow window: the search box wraps below the menu, so its suggestions
    # drop down exactly where the submenus open.
    admin_page.set_viewport_size({"width": 1000, "height": 800})
    admin_page.goto(url + "/admin/")
    wait_for_page_load(admin_page)
    admin_page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")

    admin_page.evaluate(
        "() => (django.jQuery || jQuery)('#id_global_nav_value').select2('open')"
    )
    admin_page.locator(".select2-container--open .select2-search__field").fill("ab")
    admin_page.wait_for_selector(DROPDOWN, state="visible")


def test_otwarcie_menu_zamyka_podpowiedzi_szybkiego_wyszukiwania(
    channels_live_server, admin_page: Page
):
    _open_quick_search(admin_page, channels_live_server.url)

    admin_page.locator(MENU_ITEM_WITH_SUBMENU).first.locator("> a").hover()

    admin_page.wait_for_selector(DROPDOWN, state="detached", timeout=5000)


def test_otwarte_menu_jest_nad_podpowiedziami_szybkiego_wyszukiwania(
    channels_live_server, admin_page: Page
):
    """Even when the suggestions stay open (e.g. the menu is opened from the
    keyboard or by a script), the open menu is drawn above them."""
    _open_quick_search(admin_page, channels_live_server.url)

    # Open the menu WITHOUT a mouse event, so the dropdown is not closed by JS.
    result = admin_page.evaluate(
        """(selector) => {
            const li = document.querySelector(selector);
            li.classList.add('over');
            const header = document.getElementById('grp-header');
            const dropdown = document.querySelector(
                '.select2-container--open .select2-dropdown'
            );
            return {
                header: parseInt(getComputedStyle(header).zIndex, 10),
                dropdown: parseInt(getComputedStyle(dropdown).zIndex, 10),
                dropdownInHeader: header.contains(dropdown),
            };
        }""",
        MENU_ITEM_WITH_SUBMENU,
    )

    assert not result["dropdownInHeader"]
    assert result["header"] > result["dropdown"], result
