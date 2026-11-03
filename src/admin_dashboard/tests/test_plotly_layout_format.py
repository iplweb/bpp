"""
Układy wykresów dashboardu muszą pasować do plotly.js 3+ (#883).

Od plotly.js 3.0 `title` przekazany jako zwykły string jest po cichu
ignorowany (wykres się rysuje, tylko bez tytułu), a `titlefont`,
`titleside` itd. zniknęły. Poprawny format to `{"text": ..., "font": ...}`.
"""

import pytest
from django.urls import reverse

CHART_VIEWS = [
    "weekday_stats",
    "day_of_month_activity_stats",
    "new_publications_stats",
    "cumulative_publications_stats",
    "cumulative_impact_factor_stats",
    "cumulative_points_kbn_stats",
    "charakter_formalny_stats_top90",
    "charakter_formalny_stats_remaining10",
    "charakter_formalny_stats_remaining1",
    "database_stats",
]

REMOVED_IN_PLOTLY_3 = {"titlefont", "titleside", "titleposition", "titleoffset"}


def _walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key, value
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}[{i}]")


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", CHART_VIEWS)
def test_chart_layout_uses_plotly3_title_format(client, superuser, view_name):
    client.force_login(superuser)
    response = client.get(reverse(f"admin_dashboard:{view_name}"))
    assert response.status_code == 200

    for path, key, value in _walk(response.json()):
        assert key not in REMOVED_IN_PLOTLY_3, path
        # `layout`, `trend_layout` — tytuł wykresu i tytuły osi siedzą pod nimi
        if key == "title" and "layout" in path:
            assert isinstance(value, dict), f"{path} = {value!r}"
