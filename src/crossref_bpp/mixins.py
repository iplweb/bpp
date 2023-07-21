from django.urls import re_path as url

from .views import pobierz_z_crossref


class AdminCrossrefAPIMixin:
    crossref_templates = {}

    def get_urls(self):
        urls = super().get_urls()

        security_urls = [
            url(
                r"^pobierz-z-crossref/$",
                self.admin_site.admin_view(self.pobierz_z_crossref),
            )
        ]

        return security_urls + urls

    def pobierz_z_crossref(self, request):
        context = dict(
            self.admin_site.each_context(request),
            app_label="bpp",
            title="Pobierz z CrossRef",
        )
        return pobierz_z_crossref(request, context, self.crossref_templates)
