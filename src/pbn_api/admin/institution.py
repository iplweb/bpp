from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikJednostkiWBPPFilter
from pbn_api.models import Institution

from django.contrib import admin


@admin.register(Institution)
class InstitutionAdmin(BaseMongoDBAdmin):

    list_display = [
        "name",
        "addressCity",
        "addressStreet",
        "addressStreetNumber",
        "addressPostalCode",
        "website",
        "rekord_w_bpp",
    ]

    search_fields = [
        "mongoId",
        "name",
        "addressCity",
        "addressStreet",
        "addressPostalCode",
        "polonUid",
    ]
    list_filter = [OdpowiednikJednostkiWBPPFilter] + BaseMongoDBAdmin.list_filter
