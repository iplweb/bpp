from .core import RestrictDeletionToAdministracjaGroupMixin

from django.contrib import admin

from bpp.models import Dyscyplina_Naukowa


class Dyscyplina_NaukowaAdmin(
    RestrictDeletionToAdministracjaGroupMixin, admin.ModelAdmin
):
    list_display = (
        "kod",
        "nazwa",
        "dziedzina",
        "widoczna",
        "pbn_uid",
    )  # Sane defaults.

    fields = None
    search_fields = (
        "nazwa",
        "kod",
    )
    list_filter = ("widoczna",)

    fields = ["nazwa", "kod", "widoczna", "pbn_uid"]
    mptt_level_indent = 40


admin.site.register(Dyscyplina_Naukowa, Dyscyplina_NaukowaAdmin)
