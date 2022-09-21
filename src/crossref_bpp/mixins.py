from django.conf.urls import url
from django.template.response import TemplateResponse

from .core import Komparator
from .forms import PobierzZCrossrefAPIForm
from .utils import json_format_with_wrap


class AdminCrossrefAPIMixin:
    crossref_templates = {}

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

        if request.method == "POST":
            form = PobierzZCrossrefAPIForm(request.POST)
            if form.is_valid():

                json_data = form.cleaned_data["json_data"]
                # context["json_data"] = json_data
                # context["json_presentation"] = [
                #     (
                #         key,
                #         json_format_with_wrap(item),
                #     )
                #     for key, item in sorted(json_data.items())
                # ]

                context["dane_porownania"] = Komparator.utworz_dane_porownania(
                    json_data
                )

                context["do_skopiowania"] = [
                    (key, json_format_with_wrap(item))
                    for key, item in sorted(json_data.items())
                    if key in Komparator.atrybuty.do_skopiowania
                ]

                context["ignorowane"] = [
                    (key, json_format_with_wrap(item))
                    for key, item in sorted(json_data.items())
                    if key in Komparator.atrybuty.ignorowane
                ]

                context["obce"] = [
                    (key, json_format_with_wrap(item))
                    for key, item in sorted(json_data.items())
                    if key not in Komparator.atrybuty.wszystkie
                ]

                return TemplateResponse(
                    request, self.crossref_templates.get("show", ""), context
                )

        context["crossref_form"] = form
        return TemplateResponse(
            request, self.crossref_templates.get("form", ""), context
        )
