from pbn_api.admin.base import BasePBNAPIAdmin
from pbn_api.admin.filters import (
    OdpowiednikPublikacjiInstytucjiAutorWBPPFilter,
    OdpowiednikPublikacjiInstytucjiPublikacjaWBPPFilter,
)
from pbn_api.models import PublikacjaInstytucji

from django.contrib import admin

from bpp.models import Rekord


@admin.register(PublikacjaInstytucji)
class PublikacjaInstytucjiAdmin(BasePBNAPIAdmin):
    list_per_page = 25
    actions = None
    autocomplete_fields = [
        "insPersonId",
        "institutionId",
        "publicationId",
    ]
    list_select_related = ["insPersonId", "institutionId", "publicationId"]
    list_filter = [
        "userType",
        "publicationType",
        OdpowiednikPublikacjiInstytucjiPublikacjaWBPPFilter,
        OdpowiednikPublikacjiInstytucjiAutorWBPPFilter,
    ]
    list_display = [
        "publicationId",
        "odpowiednik_publikacji_w_bpp",
        "publicationType",
        "insPersonId",
        "odpowiednik_osoby_w_bpp",
        "userType",
    ]
    readonly_fields = [
        "insPersonId",
        "institutionId",
        "publicationId",
        "publicationType",
        "userType",
        "publicationVersion",
        "publicationYear",
    ]

    fields = readonly_fields + ["snapshot"]

    def odpowiednik_publikacji_w_bpp(self, obj: PublikacjaInstytucji):
        return Rekord.objects.filter(pbn_uid_id=obj.publicationId_id).first()

    def odpowiednik_osoby_w_bpp(self, obj: PublikacjaInstytucji):
        return obj.insPersonId.rekord_w_bpp

    def odpowiednik_instytucji_w_bpp(self, obj: PublikacjaInstytucji):
        return obj.institutionId.rekord_w_bpp
