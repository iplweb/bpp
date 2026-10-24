from pathlib import Path

import pytest
from django.template import Context, Template

from ewaluacja_common.models import Rodzaj_Autora
from ewaluacja_metryki.templatetags.rodzaj_autora_tags import rodzaj_autora_label

SZABLON = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "ewaluacja_metryki"
    / "szczegoly.html"
)


@pytest.mark.django_db
def test_rodzaj_autora_label_escapuje_nazwe():
    Rodzaj_Autora.objects.update_or_create(
        skrot="Q", defaults={"nazwa": 'x" onmouseover="y<b>', "sort": 99}
    )

    html = rodzaj_autora_label("Q")

    assert 'title="x&quot; onmouseover=&quot;y&lt;b&gt;"' in html
    assert "<b>" not in html


@pytest.mark.django_db
def test_rodzaj_autora_label_escapuje_nieznany_skrot():
    html = rodzaj_autora_label("<")

    assert html == '<span class="label secondary" title="&lt;">&lt;</span>'


def test_szablon_szczegolow_nie_uzywa_safe_dla_danych_wykresu():
    tekst = SZABLON.read_text(encoding="utf-8")

    assert "chart_data|jsonify" in tekst
    assert "year_aggregates|jsonify" in tekst
    assert "_json|safe" not in tekst
    assert "rodzaj_autora_label|safe" not in tekst


def test_jsonify_danych_wykresu_nie_wylamuje_sie_ze_script():
    chart_data = [{"rok": 2024, "tytul": "</script><script>x()</script>"}]
    wynik = Template(
        "{% load prace %}<script>var d = {{ chart_data|jsonify }};</script>"
    ).render(Context({"chart_data": chart_data}))

    assert wynik.count("</script>") == 1
    assert "\\u003c/script\\u003e" in wynik
