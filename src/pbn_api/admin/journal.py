from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import MaMNISWIDFilter, OdpowiednikZrodlaWBPPFilter
from pbn_api.models import Journal

from django.contrib import admin


@admin.register(Journal)
class JournalAdmin(BaseMongoDBAdmin):
    list_filter = [
        OdpowiednikZrodlaWBPPFilter,
        MaMNISWIDFilter,
    ] + BaseMongoDBAdmin.list_filter
    list_display = [
        "title",
        "issn",
        "eissn",
        "mniswId",
        "websiteLink",
        "rekord_w_bpp",
    ]
    search_fields = ["mongoId", "title", "websiteLink", "issn", "eissn", "mniswId"]
