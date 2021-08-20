from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikWBPPFilter
from pbn_api.models import Publication

from django.contrib import admin


@admin.register(Publication)
class PublicationAdmin(BaseMongoDBAdmin):
    show_full_result_count = False

    list_display = [
        "title",
        "type",
        "volume",
        "year",
        "publicUri",
        "doi",
        "rekord_w_bpp",
    ]
    search_fields = [
        "mongoId",
        "title",
        "isbn",
        "doi",
        "publicUri",
    ]

    list_filter = [OdpowiednikWBPPFilter] + BaseMongoDBAdmin.list_filter
