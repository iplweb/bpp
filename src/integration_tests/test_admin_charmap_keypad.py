"""Klawiatura znaków specjalnych (kbw-keypad) działa na formularzach z polami
``.charmap``, a na stronach bez takich pól nie jest w ogóle ładowana."""

from playwright.sync_api import Page, expect

from django_bpp.playwright_util import wait_for_page_load


def test_admin_charmap_keypad_dziala_na_formularzu(
    channels_live_server, admin_page: Page, transactional_db
):
    admin_page.goto(channels_live_server.url + "/admin/bpp/autor/add/")
    wait_for_page_load(admin_page)

    # charmap-keypad.js dokleja przycisk 🌐 obok każdego pola .charmap.
    trigger = admin_page.locator("#id_nazwisko ~ button.keypad-trigger")
    expect(trigger).to_have_count(1, timeout=10000)

    trigger.click()
    popup = admin_page.locator(".keypad-popup")
    expect(popup).to_be_visible(timeout=5000)

    popup.locator("button.keypad-key", has_text="α").first.click()
    expect(admin_page.locator("#id_nazwisko")).to_have_value("α")


def test_admin_charmap_keypad_nie_laduje_sie_na_panelu(
    channels_live_server, admin_page: Page, transactional_db
):
    requested = []
    admin_page.on("request", lambda req: requested.append(req.url))

    admin_page.goto(channels_live_server.url + "/admin/")
    wait_for_page_load(admin_page)

    assert not [url for url in requested if "kbw-keypad" in url]
    assert admin_page.evaluate("() => typeof grp.jQuery.fn.keypad") == "undefined"
