from django.contrib import admin


class BppAdminSite(admin.AdminSite):
    site_title = "Moduł redagowania BPP"
    site_header = "Moduł redagowania"
    index_title = "Redagowanie"
