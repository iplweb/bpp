from django.urls import re_path as url

from .views import pobierz_z_crossref, pobierz_z_crossref_oraz_pbn


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


class AdminCrossrefPBNAPIMixin:
    crossref_pbn_templates = {}

    def get_urls(self):
        urls = super().get_urls()

        security_urls = [
            url(
                r"^pobierz-z-crossref-pbn/$",
                self.admin_site.admin_view(self.pobierz_z_crossref_oraz_pbn),
            )
        ]

        return security_urls + urls

    def pobierz_z_crossref_oraz_pbn(self, request):
        context = dict(
            self.admin_site.each_context(request),
            app_label="bpp",
            title="Pobierz z CrossRef ORAZ PBN",
        )
        return pobierz_z_crossref_oraz_pbn(
            request, context, self.crossref_pbn_templates
        )
