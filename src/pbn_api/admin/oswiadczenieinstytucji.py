from pbn_api.admin.base import BasePBNAPIAdmin
from pbn_api.admin.filters import (
    OdpowiednikOswiadczeniaInstytucjiAutorWBPPFilter,
    OdpowiednikOswiadczeniaInstytucjiPublikacjaWBPPFilter,
)
from pbn_api.models import OswiadczenieInstytucji

from django.contrib import admin

from bpp.models import Rekord


@admin.register(OswiadczenieInstytucji)
class OswiadczeniaInstytucjiAdmin(BasePBNAPIAdmin):
    autocomplete_fields = ["institutionId", "personId", "publicationId"]

    list_select_related = ["publicationId", "personId", "institutionId"]

    search_fields = [
        "publicationId__title",
        "publicationId__year",
        "publicationId__pk",
        "personId__lastName",
        "personId__name",
    ]

    list_display = [
        "publicationId",
        "odpowiednik_publikacji_w_bpp",
        "personId",
        "odpowiednik_osoby_w_bpp",
        "area",
        "inOrcid",
        "type",
    ]

    readonly_fields = [
        "addedTimestamp",
        "area",
        "inOrcid",
        "institutionId",
        "personId",
        "publicationId",
        "type",
    ]

    list_filter = [
        OdpowiednikOswiadczeniaInstytucjiPublikacjaWBPPFilter,
        OdpowiednikOswiadczeniaInstytucjiAutorWBPPFilter,
        "type",
        "inOrcid",
    ]

    def odpowiednik_publikacji_w_bpp(self, obj: OswiadczenieInstytucji):
        return Rekord.objects.filter(pbn_uid_id=obj.publicationId_id).first()

    def odpowiednik_osoby_w_bpp(self, obj: OswiadczenieInstytucji):
        return obj.personId.rekord_w_bpp
