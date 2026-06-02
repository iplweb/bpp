"""Regresja layoutu rekordu rozbijanego przez treść streszczenia.

Streszczenia importowane z zewnątrz zawierają operatory porównania wpisane
wprost w tekst (np. ``<30 IU/dL``). Renderowane przez ``|safe`` i przepuszczone
przez produkcyjny minifikator HTML (``django-minify-html``) ``<`` bez
zamykającego ``>`` był traktowany jak otwarcie znacznika, który połykał dalszy
markup (w tym zamykające ``</p></div>``) — prawa kolumna rekordu lądowała
wewnątrz lewej i strona zlewała się do jednej kolumny.

Filtr ``|safe_streszczenie`` escape'uje te operatory, więc minifikator widzi
poprawny, zbalansowany HTML.
"""

import lxml.html
import minify_html
from django.template import Context, Template

# Args identyczne z produkcyjnym BppMinifyHtmlMiddleware.minify_args
# (django_bpp/settings/production.py).
PROD_MINIFY_ARGS = dict(
    minify_css=True,
    minify_js=True,
    keep_input_type_text_attr=True,
    keep_closing_tags=True,
)

# Fragment realnego streszczenia (rekord 586 z bpp.ihit.waw.pl), który rozbijał
# layout: '<' jako operator "mniejsze niż", bez zamykającego '>'.
BROKEN_ABSTRACT = (
    "VWD1 with a VWF antigen level (VWF:Ag) of <30IU/dL or <40IU/dL, "
    "in which about 80% of patients exhibited VWF gene mutations."
)

PAGE_TEMPLATE = (
    "{% load prace %}"
    "<div class='columns'>"
    "<div class='left-column'><p class='abstract'>"
    "{{ abstract|FILTER }}"
    "</p></div>"
    "<div class='right-column'>RIGHT_COLUMN_MARKER</div>"
    "</div>"
)


def _render_and_minify(filter_expr, abstract):
    template_str = PAGE_TEMPLATE.replace("FILTER", filter_expr)
    rendered = Template(template_str).render(Context({"abstract": abstract}))
    return minify_html.minify(
        "<!DOCTYPE html><html><body>" + rendered + "</body></html>",
        **PROD_MINIFY_ARGS,
    )


def _columns(html):
    tree = lxml.html.fromstring(html)
    left = tree.xpath("//div[contains(@class,'left-column')]")[0]
    right = tree.xpath("//div[contains(@class,'right-column')]")[0]
    return left, right


def test_safe_streszczenie_keeps_columns_separate_after_minify():
    html = _render_and_minify("safe_streszczenie", BROKEN_ABSTRACT)
    left, right = _columns(html)

    # prawa kolumna MUSI być rodzeństwem lewej, a nie jej dzieckiem
    assert right not in left.iter(), (
        "right-column wessana do left-column -- streszczenie zjadło "
        "zamykające znaczniki (regresja layoutu jednokolumnowego)"
    )
    # operatory porównania przetrwały jako czytelny tekst, bez utraty treści
    assert "&lt;30IU/dL" in html
    assert "<30IU/dL" in left.text_content()
    assert "80% of patients exhibited" in left.text_content()


def test_raw_safe_breaks_columns_after_minify():
    """Dokumentuje pierwotny błąd i potwierdza, że powyższy test ma "zęby".

    Surowe ``|safe`` + minifikator wsysa zamykające znaczniki, więc prawa
    kolumna staje się potomkiem lewej.
    """
    html = _render_and_minify("safe", BROKEN_ABSTRACT)
    left, right = _columns(html)
    assert right in left.iter()
