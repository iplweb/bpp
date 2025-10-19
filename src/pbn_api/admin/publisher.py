from django.contrib import admin

from pbn_api.admin import MaMNISWIDFilter
from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikWydawcyWBPPFilter
from pbn_api.models import Publisher


@admin.register(Publisher)
class PublisherAdmin(BaseMongoDBAdmin):
    list_display = ["publisherName", "mniswId", "mongoId", "rekord_w_bpp"]
    search_fields = ["mongoId", "publisherName", "mniswId"]
    list_filter = [
        OdpowiednikWydawcyWBPPFilter,
        MaMNISWIDFilter,
        "status",
        "verificationLevel",
        "verified",
    ] + BaseMongoDBAdmin.list_filter
