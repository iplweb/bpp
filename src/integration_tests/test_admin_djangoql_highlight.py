"""Podświetlanie składni DjangoQL w pasku wyszukiwania admina ma iść za
przełącznikiem trybu — aktywne tylko, gdy zaznaczono „używaj DjangoQL"."""

from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load


def _highlight_active(page: Page) -> bool:
    """Nakładka jest AKTYWNA, gdy tekst pola jest transparentny
    (``.dql-highlight-input``) i kolorowany backdrop jest widoczny."""
    return page.evaluate(
        "() => {"
        "  const ta = document.querySelector('textarea[name=q]');"
        "  const bd = document.querySelector('.dql-highlight-backdrop');"
        "  return !!ta && ta.classList.contains('dql-highlight-input')"
        "    && !!bd && getComputedStyle(bd).display !== 'none';"
        "}"
    )


def test_admin_djangoql_highlight_follows_toggle(
    channels_live_server, admin_page: Page, transactional_db
):
    # Admin Źródła używa BppDjangoQLSearchMixin i nadpisuje search_fields,
    # więc completion_admin.js rysuje przełącznik trybu (.djangoql-toggle).
    admin_page.goto(channels_live_server.url + "/admin/bpp/zrodlo/")
    wait_for_page_load(admin_page)

    # textarę i przełącznik tworzy completion_admin.js na DOMReady; nasza
    # nakładka doczepia się klatkę później i znaczy pole atrybutem
    # dataset.dqlHighlight='on' — poczekaj aż wszystko wstanie.
    admin_page.wait_for_selector("input.djangoql-toggle", timeout=10000)
    admin_page.wait_for_function(
        "() => document.querySelector('textarea[name=q]')"
        "  && document.querySelector('textarea[name=q]')"
        "       .dataset.dqlHighlight === 'on'",
        timeout=10000,
    )

    toggle = admin_page.locator("input.djangoql-toggle")

    # Zaznaczony przełącznik → tryb DjangoQL → podświetlanie AKTYWNE.
    if not toggle.is_checked():
        toggle.check()
    assert _highlight_active(admin_page) is True

    # Odznaczony → zwykłe wyszukiwanie podłańcuchowe → podświetlanie ZNIKA
    # (pole ma wyglądać jak normalny input).
    toggle.uncheck()
    assert _highlight_active(admin_page) is False

    # Ponowne zaznaczenie → podświetlanie wraca.
    toggle.check()
    assert _highlight_active(admin_page) is True
