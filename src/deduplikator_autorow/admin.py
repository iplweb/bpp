from pbn_api.models import Scientist
from .models import NotADuplicate

from django.contrib import admin


@admin.register(NotADuplicate)
class NotADuplicateAdmin(admin.ModelAdmin):
    list_display = [
        "autor",
        "created_by",
        "created_on",
    ]

    list_filter = [
        "created_on",
        "created_by",
    ]

    search_fields = [
        "autor__nazwisko",
        "autor__imiona",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
    ]

    readonly_fields = [
        "created_on",
    ]

    date_hierarchy = "created_on"

    ordering = ["-created_on"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_author_first_name(self, obj):
        """Pobiera imiona autora z rekordu BPP"""
        try:
            scientist = Scientist.objects.get(pk=obj.scientist_pk)
            if scientist.rekord_w_bpp:
                return scientist.rekord_w_bpp.imiona or "-"
            return "-"
        except (Scientist.DoesNotExist, AttributeError):
            return "-"

    get_author_first_name.short_description = "Imiona"
    get_author_first_name.admin_order_field = "scientist_pk"

    def get_author_last_name(self, obj):
        """Pobiera nazwisko autora z rekordu BPP"""
        try:
            scientist = Scientist.objects.get(pk=obj.scientist_pk)
            if scientist.rekord_w_bpp:
                return scientist.rekord_w_bpp.nazwisko or "-"
            return "-"
        except (Scientist.DoesNotExist, AttributeError):
            return "-"

    get_author_last_name.short_description = "Nazwisko"
    get_author_last_name.admin_order_field = "scientist_pk"
