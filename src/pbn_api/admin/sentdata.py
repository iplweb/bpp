from pbn_api.admin.base import BasePBNAPIAdminNoReadonly
from pbn_api.admin.helpers import format_json
from pbn_api.models import SentData

from django.contrib import admin


@admin.register(SentData)
class SentDataAdmin(BasePBNAPIAdminNoReadonly):

    list_display = [
        "object",
        "last_updated_on",
        "typ_rekordu",
        "pbn_uid_id",
        "uploaded_okay",
        "exception_details",
    ]
    ordering = ("-last_updated_on",)
    search_fields = ["data_sent", "exception"]
    readonly_fields = [
        "content_type",
        "object_id",
        "last_updated_on",
        "uploaded_okay",
        "exception",
        "pbn_uid_id",
        "typ_rekordu",
    ]
    fields = readonly_fields + ["pretty_json"]
    list_filter = ["uploaded_okay", "typ_rekordu"]

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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def pretty_json(self, obj=None):
        return format_json(obj, "data_sent")

    pretty_json.short_description = "Wysłane dane"

    def exception_details(self, obj):
        if obj.exception:
            try:
                return obj.exception.split('"details":')[1][:-3]
            except BaseException:
                return obj.exception

    exception_details.short_description = "Opis problemu"
    exception_details.admin_order_field = "exception"
