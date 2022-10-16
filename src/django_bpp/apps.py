from django.contrib.admin.apps import AdminConfig


class BppAdminConfig(AdminConfig):
    default_site = "bpp.admin_site.BppAdminSite"
