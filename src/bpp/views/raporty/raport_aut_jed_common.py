"""Wspólne procedury dla raportu jednostek oraz autorów.
"""


import bleach
from django.http.response import HttpResponse
from django.template import loader
from django_tables2 import Column, Table


def sumif(table):
    return sum(x.impact_factor for x in table.data)


def sumpk(table):
    return sum(x.punkty_kbn for x in table.data)


def sumif_kc(table):
    return sum(x.kc_impact_factor or x.impact_factor for x in table.data)


def sumpk_kc(table):
    return sum(x.kc_punkty_kbn or x.punkty_kbn for x in table.data)


class SumyImpactKbnMixin(Table):
    impact_factor = Column(
        "IF",
        footer=sumif_kc,
        attrs={"td": {"align": "right"}},
        orderable=False,
    )
    punkty_kbn = Column(
        "PK (MNiSzW) x",
        footer=sumpk_kc,
        attrs={"td": {"align": "right"}},
        orderable=False,
    )


MSW_ALLOWED_TAGS = [
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "code",
    "em",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "center",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "tr",
    "td",
    "th",
    "div",
    "thead",
    "tbody",
    "body",
    "head",
    "meta",
    "html",
]

MSW_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "abbr": ["title"],
    "acronym": ["title"],
    "meta": ["charset"],
}


class MSWordFromTemplateResponse(HttpResponse):
    def __init__(self, request, context, template_name, visible_name, *args, **kwargs):
        super(HttpResponse, self).__init__(*args, **kwargs)
        self["Content-type"] = "application/msword"
        self["Content-disposition"] = "attachment; filename=%s" % visible_name.encode(
            "utf-8"
        )  # urllib.quote(visible_name.encode("utf-8"))
        c = loader.render_to_string(template_name, context, request=request)
        c = bleach.clean(
            c, tags=MSW_ALLOWED_TAGS, attributes=MSW_ALLOWED_ATTRIBUTES, strip=True
        )
        c = c.replace("<table>", "<table border=1 cellspacing=0>")
        self.content = (
            '<html><head><meta charset="utf-8"></head><body>' + c + "</body></html>"
        )
        self["Content-length"] = len(self.content)
