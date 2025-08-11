from django.db import models

from pbn_api.admin import BasePBNAPIAdmin, PrettyJSONWidgetReadonly
from pbn_api.models import PublikacjaInstytucji_V2

from django.contrib import admin


@admin.register(PublikacjaInstytucji_V2)
class PublikacjaInstytucjiAdmin(BasePBNAPIAdmin):
    list_per_page = 25
    actions = None

    autocomplete_fields = ["objectId"]
    readonly_fields = ["uuid", "objectId", "created_on", "last_updated"]
    fields = readonly_fields + ["json_data"]

    list_display = ["__str__", "objectId", "created_on", "last_updated"]
    date_hierarchy = "last_updated"

    formfield_overrides = {models.JSONField: {"widget": PrettyJSONWidgetReadonly}}

    def has_delete_permission(self, request, obj=...):
        return False
