from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikWBPPFilter
from pbn_api.admin.helpers import format_json
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

    fields = BaseMongoDBAdmin.readonly_fields + [
        "pretty_json",
    ]

    list_filter = [OdpowiednikWBPPFilter] + BaseMongoDBAdmin.list_filter

    def pretty_json(self, obj=None):
        return format_json(obj, "versions")

    pretty_json.short_description = "Odebrane dane (versions)"
