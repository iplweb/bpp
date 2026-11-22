from django.contrib.admin.apps import AdminConfig


class BppAdminConfig(AdminConfig):
    default_site = "bpp.admin_site.BppAdminSite"

    def ready(self):
        super().ready()  # autodiscover — wszystkie moduły admin.py
        from django.contrib import admin

        from bpp.admin.helpers.wersje import podepnij_historie_wersji

        # FD#587: modele z ``MODELE_Z_HISTORIA`` dostają historię wersji.
        podepnij_historie_wersji(admin.site)
