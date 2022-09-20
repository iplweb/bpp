import json
from textwrap import fill

from django.conf.urls import url
from django.template.response import TemplateResponse

from .forms import PobierzZCrossrefAPIForm


class AdminCrossrefAPIMixin:
    crossref_templates = {}

    znane_klucze = [
        "DOI",
        "ISSN",
        "URL",
        "abstract",
        "author",
        "issn-type",
        "issue",
        "license",
        "link",
        "page",
        "publisher",
        "resource",
        "short-container-title",
        "subject",
        "title",
        "type",
        "volume",
    ]

    ignorowane_klucze = [
        "content-domain",
        "created",
        "deposited",
        "indexed",
        "is-referenced-by-count",
        "issued",
        "journal-issue",
        "member",
        "original-title",
        "published",
        "published-online",
        "reference-count",
        "references-count",
        "relation",
        "short-title",
        "source",
        "subtitle",
    ]

    def get_urls(self):
        # get the default urls
        urls = super().get_urls()

        # define security urls
        security_urls = [
            url(
                r"^pobierz-z-crossref/$",
                self.admin_site.admin_view(self.pobierz_z_crossref),
            )
            # Add here more urls if you want following same logic
        ]

        # Make sure here you place your added urls first than the admin default urls
        return security_urls + urls

    # Your view definition fn
    def pobierz_z_crossref(self, request):
        form = PobierzZCrossrefAPIForm()

        context = dict(
            self.admin_site.each_context(request),
            app_label="bpp",
            title="Pobierz z CrossRef",
        )

        def nicely_format(s, width=70):
            news = []
            for elem in s:
                if len(elem) > width:
                    elem = fill(elem, width=width)
                news.append(elem)
            return "\n".join(news)

        if request.method == "POST":
            form = PobierzZCrossrefAPIForm(request.POST)
            if form.is_valid():
                json_data = form.cleaned_data["json_data"]
                context["json_data"] = json_data
                context["json_presentation"] = [
                    (
                        key,
                        nicely_format(json.dumps(item, indent=2).split("\n")),
                    )
                    for key, item in sorted(json_data.items())
                ]

                return TemplateResponse(
                    request, self.crossref_templates.get("show", ""), context
                )

        context["crossref_form"] = form
        return TemplateResponse(
            request, self.crossref_templates.get("form", ""), context
        )
