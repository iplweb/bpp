from pbn_api.admin.base import BasePBNAPIAdmin
from pbn_api.admin.filters import (
    OdpowiednikOswiadczeniaInstytucjiAutorWBPPFilter,
    OdpowiednikOswiadczeniaInstytucjiPublikacjaWBPPFilter,
)
from pbn_api.exceptions import StatementDeletionError
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
        "disciplines",
    ]

    readonly_fields = [
        "addedTimestamp",
        "area",
        "inOrcid",
        "institutionId",
        "personId",
        "publicationId",
        "type",
        "disciplines",
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

    def has_delete_permission(self, request, *args, **kw):
        return True

    def delete_model(self, request, obj: OswiadczenieInstytucji, pbn_client=None):
        try:
            obj.sprobuj_skasowac_z_pbn(request, pbn_client)
        except StatementDeletionError as e:
            from django.contrib import messages

            messages.error(
                request,
                f"Skasowanie niemożliwe, PBN API zwróciło błąd {e}. Proszę zignorować komunikat "
                f"o pomyślnym usunięciu rekordu, wcisnąc 2x przycisk 'Wstecz' w przeglądarce i "
                f"spróbować jeszcze raz. Oświadczenie nie zostało usunięte ani z PBN, ani z lokalnej bazy.",
            )
            return
        super().delete_model(request, obj)
