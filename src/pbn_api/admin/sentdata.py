from django.contrib import admin

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from pbn_api.admin.base import BasePBNAPIAdminNoReadonly
from pbn_api.admin.widgets import JSONWithActionsWidget
from pbn_api.models import SentData


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
    fields = readonly_fields + ["data_sent"]
    list_filter = ["uploaded_okay", "typ_rekordu"]

    list_per_page = 25

    # Override the base class formfield_overrides to use our custom widget
    formfield_overrides = {}

    def wyslij_ponownie(self, request, qset):
        pass

        for elem in qset:
            obj = elem.object
            sprobuj_wyslac_do_pbn_gui(request, obj)

    wyslij_ponownie.short_description = "Wyślij ponownie (tylko błędne)"

    def wyslij_ponownie_force(self, request, qset):
        for elem in qset:
            obj = elem.object
            sprobuj_wyslac_do_pbn_gui(request, obj, force_upload=True)

    wyslij_ponownie_force.short_description = (
        "Wyślij ponownie (wszystko; wymuś ponowny transfer)"
    )

    actions = [wyslij_ponownie, wyslij_ponownie_force]

    def has_delete_permission(self, request, *args, **kw):
        return True

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Override widget for data_sent field
        if db_field.name == "data_sent":
            # Try to get the object ID from the URL
            object_id = None
            if request and "object_id" in request.resolver_match.kwargs:
                object_id = request.resolver_match.kwargs["object_id"]

            widget = JSONWithActionsWidget(
                attrs={"data-object-id": object_id or "unknown"}
            )
            kwargs["widget"] = widget
            kwargs["label"] = "Wysłane dane"

        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def exception_details(self, obj):
        if obj.exception:
            try:
                return obj.exception.split('"details":')[1][:-3]
            except BaseException:
                return obj.exception

    exception_details.short_description = "Opis problemu"
    exception_details.admin_order_field = "exception"
