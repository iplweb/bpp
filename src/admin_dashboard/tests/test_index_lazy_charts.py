"""Strona główna admina ładuje wykresy leniwie (lazy-charts.js)."""

import re

import pytest
from django.urls import reverse

WYKRESY = [
    "weekday_stats",
    "day_of_month_activity_stats",
    "new_publications_stats",
    "cumulative_publications_stats",
    "cumulative_impact_factor_stats",
    "cumulative_points_kbn_stats",
    "charakter_formalny_stats_top90",
    "charakter_formalny_stats_remaining10",
    "charakter_formalny_stats_remaining1",
]


@pytest.mark.django_db
def test_admin_index_wykresy_leniwe(admin_client):
    res = admin_client.get(reverse("admin:index"))
    assert res.status_code == 200
    html = res.content.decode()

    # Plotly nie może blokować <head> — doładowuje go lazy-charts.js.
    assert not re.search(r"<script[^>]+plotly\.min\.js", html)
    assert "data-plotly-src=" in html
    assert "admin_dashboard/js/lazy-charts.js" in html

    for nazwa in WYKRESY:
        url = reverse(f"admin_dashboard:{nazwa}")
        assert f'data-chart-url="{url}"' in html, nazwa


@pytest.mark.django_db
def test_admin_index_htmx_ladowany_raz(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    assert len(re.findall(r"<script[^>]+/htmx\.org/dist/htmx[^\"']*\.js", html)) == 1


@pytest.mark.parametrize(
    "sciezka",
    [
        "htmx.org/dist/htmx.min.js",
        "plotly.js/dist/plotly.min.js",
        "plotly.js/dist/plotly-locale-pl.js",
        "admin_dashboard/js/lazy-charts.js",
    ],
)
def test_statyki_admina_widoczne_dla_collectstatic(sciezka):
    # TolerantManifestStaticFilesStorage nie wywali szablonu na brakującym
    # pliku — w produkcji skończyłoby się cichym 404. Stąd jawny test
    # białej listy node_modules (NPM_FILE_PATTERNS) i finderów.
    from django.contrib.staticfiles import finders

    assert finders.find(sciezka), sciezka
