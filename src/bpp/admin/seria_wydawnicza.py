from django.contrib import admin

from ..models.seria_wydawnicza import Seria_Wydawnicza
from .core import BaseBppAdminMixin
from .helpers.mixins import BppSoftDeleteAdminMixin


class Seria_WydawniczaAdmin(
    BaseBppAdminMixin, BppSoftDeleteAdminMixin, admin.ModelAdmin
):
    list_display = [
        "nazwa",
    ]
    search_fields = [
        "nazwa",
    ]


admin.site.register(Seria_Wydawnicza, Seria_WydawniczaAdmin)
