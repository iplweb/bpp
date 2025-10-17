from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


class BppAdminSite(admin.AdminSite):
    site_title = "Moduł redagowania BPP"
    site_header = "Moduł redagowania"
    index_title = "Panel Sterowania"

    def index(self, request, extra_context=None):
        """
        Override index to add dashboard statistics to context
        """
        from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

        extra_context = extra_context or {}
        extra_context["stats"] = {
            "total_publications": Wydawnictwo_Ciagle.objects.count()
            + Wydawnictwo_Zwarte.objects.count(),
            "total_authors": Autor.objects.count(),
            "total_units": Jednostka.objects.count(),
            "total_users": User.objects.filter(is_active=True).count(),
        }

        return super().index(request, extra_context=extra_context)
