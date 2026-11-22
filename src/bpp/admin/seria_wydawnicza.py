from django.contrib import admin
from reversion_compare.admin import CompareVersionAdmin

from ..models.seria_wydawnicza import Seria_Wydawnicza
from .core import BaseBppAdminMixin
from .helpers.mixins import BppSoftDeleteAdminMixin
from .helpers.wersje import HistoriaWersjiMixin


class Seria_WydawniczaAdmin(
    BaseBppAdminMixin,
    BppSoftDeleteAdminMixin,
    # Historia zmian (FD#587): tuż przed terminalną klasą admina.
    HistoriaWersjiMixin,
    CompareVersionAdmin,
):
    list_display = [
        "nazwa",
    ]
    search_fields = [
        "nazwa",
    ]


admin.site.register(Seria_Wydawnicza, Seria_WydawniczaAdmin)
