from django.contrib import admin

from dspace_api.models import Mapowanie_DSpace, SentToDSpace


@admin.register(Mapowanie_DSpace)
class Mapowanie_DSpaceAdmin(admin.ModelAdmin):
    list_display = ["uczelnia", "charakter_formalny", "collection_uuid", "opis"]
    list_filter = ["uczelnia"]
    autocomplete_fields = ["charakter_formalny"]
    search_fields = ["opis"]


@admin.register(SentToDSpace)
class SentToDSpaceAdmin(admin.ModelAdmin):
    list_display = [
        "object_id",
        "content_type",
        "uczelnia",
        "submitted_successfully",
        "dspace_uuid",
        "last_updated_on",
    ]
    list_filter = ["submitted_successfully", "uczelnia"]
    search_fields = ["object_id", "exception"]
    readonly_fields = [
        "content_type",
        "object_id",
        "uczelnia",
        "dspace_uuid",
        "bitstreams",
        "data_sent",
        "submitted_successfully",
        "submitted_at",
        "exception",
        "api_response_status",
        "last_updated_on",
    ]

    def has_add_permission(self, request):
        return False
