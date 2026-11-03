"""Wykresy na stronie głównej admina ładują się dopiero, gdy są widoczne."""

import re

from playwright.sync_api import Page, expect

DOLNY_WYKRES = "#charakter-formalny-chart-remaining1"
ZALADOWANY = re.compile(r"\bis-loaded\b")

# Obraz testowy CI nie ma node_modules, więc prawdziwego Plotly tam nie ma.
# Testujemy logikę leniwego ładowania, nie samo rysowanie — stub wystarcza.
PLOTLY_STUB = """
window.Plotly = {
    setPlotConfig: function () {},
    newPlot: function (el) {
        el.on = function () {};
        return Promise.resolve(el);
    }
};
"""


def test_admin_dashboard_wykresy_leniwe(
    channels_live_server, admin_page: Page, transactional_db
):
    admin_page.set_viewport_size({"width": 1280, "height": 700})
    admin_page.route(
        "**/plotly.js/dist/*.js",
        lambda route: route.fulfill(
            content_type="application/javascript",
            body=PLOTLY_STUB if "plotly.min" in route.request.url else "",
        ),
    )
    zadania = []
    admin_page.on(
        "request",
        lambda r: zadania.append(r.url) if "/admin-dashboard/" in r.url else None,
    )

    admin_page.goto(channels_live_server.url + "/admin/")

    # Widoczny od razu wykres się wczytuje (razem z leniwie doładowanym Plotly).
    expect(admin_page.locator("#weekday-chart")).to_have_class(
        ZALADOWANY,
        timeout=20000,
    )
    assert admin_page.evaluate("() => typeof window.Plotly") == "object"

    # Wykres daleko pod ekranem NIE pobrał jeszcze danych.
    assert not any("charakter-formalny-stats-remaining1" in u for u in zadania)

    admin_page.locator(DOLNY_WYKRES).scroll_into_view_if_needed()
    expect(admin_page.locator(DOLNY_WYKRES)).to_have_class(
        ZALADOWANY,
        timeout=20000,
    )
    assert any("charakter-formalny-stats-remaining1" in u for u in zadania)
