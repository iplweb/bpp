from pbn_api.admin.base import BasePBNAPIAdmin
from pbn_api.models import SentData

from django.contrib import admin


@admin.register(SentData)
class SentDataAdmin(BasePBNAPIAdmin):
    list_display = ["object", "last_updated_on", "uploaded_okay"]
    ordering = ("-last_updated_on",)
    search_fields = ["data_sent", "exception"]
    readonly_fields = [
        "content_type",
        "object_id",
        "data_sent",
        "last_updated_on",
        "uploaded_okay",
        "exception",
    ]
    list_filter = ["uploaded_okay"]

    list_per_page = 25

    def wyslij_ponownie(self, request, qset):
        from bpp.admin.helpers import sprobuj_wgrac_do_pbn

        for elem in qset:
            obj = elem.object
            sprobuj_wgrac_do_pbn(request, obj)

    wyslij_ponownie.short_description = "Wyślij ponownie (tylko błędne)"

    def wyslij_ponownie_force(self, request, qset):
        from bpp.admin.helpers import sprobuj_wgrac_do_pbn

        for elem in qset:
            obj = elem.object
            sprobuj_wgrac_do_pbn(request, obj, force_upload=True)

    wyslij_ponownie_force.short_description = (
        "Wyślij ponownie (wszystko; wymuś ponowny transfer)"
    )

    actions = [wyslij_ponownie, wyslij_ponownie_force]

    def has_delete_permission(self, request, *args, **kw):
        return True
