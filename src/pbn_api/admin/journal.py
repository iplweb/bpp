from django.contrib import admin

from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import (
    MaDOIFilter,
    MaEISSNFilter,
    MaISSNFilter,
    MaMNISWIDFilter,
    OdpowiednikZrodlaWBPPFilter,
)
from pbn_api.models import Journal


@admin.register(Journal)
class JournalAdmin(BaseMongoDBAdmin):
    list_filter = [
        OdpowiednikZrodlaWBPPFilter,
        MaMNISWIDFilter,
        MaISSNFilter,
        MaEISSNFilter,
        MaDOIFilter,
        "status",
    ] + BaseMongoDBAdmin.list_filter
    list_display = [
        "title",
        "issn",
        "eissn",
        "mniswId",
        "websiteLink",
        "status",
        "rekord_w_bpp",
    ]
    search_fields = ["mongoId", "title", "websiteLink", "issn", "eissn", "mniswId"]
