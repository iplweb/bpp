from pbn_api.admin.base import BasePBNAPIAdmin
from pbn_api.admin.filters import (
    OdpowiednikOswiadczeniaInstytucjiAutorWBPPFilter,
    OdpowiednikOswiadczeniaInstytucjiPublikacjaWBPPFilter,
)
from pbn_api.models import OswiadczenieInstytucji

from django.contrib import admin, messages

from bpp.models import Rekord, Uczelnia


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

    def has_delete_permission(self, request, *args, **kw):
        return True

    def delete_model(self, request, obj: OswiadczenieInstytucji, pbn_client=None):
        uczelnia = Uczelnia.objects.default
        if uczelnia is None:
            return

        if pbn_client is None:
            pbn_client = uczelnia.pbn_client(request.user.pbn_token)

        try:
            pbn_client.delete_publication_statement(
                obj.publicationId_id, obj.personId_id, obj.type
            )
        except Exception as e:
            messages.error(
                request,
                f"Skasowanie niemożliwe, PBN API zwróciło błąd {e}. Proszę zignorować komunikat "
                f"o pomyślnym usunięciu rekordu, wcisnąc 2x przycisk wstecz w przeglądarce i "
                f"spróbować jeszcze raz. ",
            )
            return

        super(OswiadczeniaInstytucjiAdmin, self).delete_model(request, obj)
