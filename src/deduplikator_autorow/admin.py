from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp.admin.core import DynamicAdminFilterMixin
from pbn_api.models import Scientist

from .models import IgnoredAuthor, LogScalania, NotADuplicate


@admin.register(NotADuplicate)
class NotADuplicateAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
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


@admin.register(IgnoredAuthor)
class IgnoredAuthorAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "get_scientist_display",
        "get_autor_display",
        "reason",
        "created_by",
        "created_on",
    ]

    list_filter = [
        "created_on",
        "created_by",
    ]

    search_fields = [
        "scientist__pk",
        "autor__nazwisko",
        "autor__imiona",
        "reason",
        "created_by__username",
    ]

    readonly_fields = [
        "created_on",
    ]

    date_hierarchy = "created_on"
    ordering = ["-created_on"]

    def get_scientist_display(self, obj):
        """Display scientist with link to PBN"""
        if obj.scientist:
            scientist = obj.scientist
            if hasattr(scientist, "rekord_w_bpp") and scientist.rekord_w_bpp:
                autor = scientist.rekord_w_bpp
                return f"{autor.imiona} {autor.nazwisko} (Scientist #{scientist.pk})"
            return f"Scientist #{scientist.pk}"
        return "-"

    get_scientist_display.short_description = "Scientist (PBN)"

    def get_autor_display(self, obj):
        """Display autor with admin link"""
        if obj.autor:
            url = reverse("admin:bpp_autor_change", args=[obj.autor.pk])
            return mark_safe(f'<a href="{url}">{obj.autor}</a>')
        return "-"

    get_autor_display.short_description = "Autor (BPP)"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LogScalania)
class LogScalaniaAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "get_operation_icon",
        "get_merge_description",
        "operation_type",
        "get_main_autor_link",
        "get_modified_record_link",
        "get_discipline_change",
        "publications_transferred",
        "disciplines_transferred",
        "created_by",
        "created_on",
    ]

    list_filter = [
        "operation_type",
        "created_on",
        "created_by",
        "dyscyplina_before",
        "dyscyplina_after",
    ]

    search_fields = [
        "main_autor__nazwisko",
        "main_autor__imiona",
        "duplicate_autor_str",
        "operation_details",
        "warnings",
        "created_by__username",
    ]

    readonly_fields = [
        "main_autor",
        "duplicate_autor_str",
        "duplicate_autor_id",
        "main_scientist",
        "duplicate_scientist",
        "get_modified_record_display",
        "dyscyplina_before",
        "dyscyplina_after",
        "operation_type",
        "operation_details",
        "created_on",
        "created_by",
        "publications_transferred",
        "disciplines_transferred",
        "warnings",
    ]

    fieldsets = (
        (
            "Autorzy",
            {
                "fields": (
                    ("main_autor", "duplicate_autor_str"),
                    ("main_scientist", "duplicate_scientist"),
                    "duplicate_autor_id",
                )
            },
        ),
        (
            "Szczegóły operacji",
            {
                "fields": (
                    "operation_type",
                    "get_modified_record_display",
                    ("dyscyplina_before", "dyscyplina_after"),
                    "operation_details",
                )
            },
        ),
        (
            "Statystyki",
            {
                "fields": (
                    ("publications_transferred", "disciplines_transferred"),
                    "warnings",
                )
            },
        ),
        ("Informacje systemowe", {"fields": (("created_by", "created_on"),)}),
    )

    date_hierarchy = "created_on"
    ordering = ["-created_on"]

    def get_operation_icon(self, obj):
        """Return icon for operation type"""
        icons = {
            "PUBLICATION_TRANSFER": "📄",
            "DISCIPLINE_TRANSFER": "🎓",
            "DISCIPLINE_REMOVED": "❌",
            "AUTHOR_DELETED": "🗑️",
        }
        return icons.get(obj.operation_type, "❓")

    get_operation_icon.short_description = ""

    def get_merge_description(self, obj):
        """Returns a description of the merge operation"""
        return f"{obj.duplicate_autor_str[:50]} → {obj.main_autor}"

    get_merge_description.short_description = "Scalanie"

    def get_main_autor_link(self, obj):
        """Create link to main author"""
        if obj.main_autor:
            url = reverse("admin:bpp_autor_change", args=[obj.main_autor.pk])
            return mark_safe(f'<a href="{url}">{obj.main_autor}</a>')
        return "-"

    get_main_autor_link.short_description = "Autor główny"
    get_main_autor_link.admin_order_field = "main_autor"

    def get_modified_record_link(self, obj):
        """Create link to modified record"""
        if obj.modified_record:
            try:
                # Get the admin URL for the object
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                url = reverse(
                    f"admin:{app_label}_{model_name}_change", args=[obj.object_id]
                )
                return mark_safe(
                    f'<a href="{url}">{obj.content_type.name} #{obj.object_id}</a>'
                )
            except BaseException:
                return f"{obj.content_type.name} #{obj.object_id}"
        return "-"

    get_modified_record_link.short_description = "Zmodyfikowany rekord"

    def get_modified_record_display(self, obj):
        """Display modified record with link in detail view"""
        if obj.modified_record:
            try:
                # Get the admin URL for the object
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                url = reverse(
                    f"admin:{app_label}_{model_name}_change", args=[obj.object_id]
                )

                # Try to get string representation of the object
                try:
                    obj_str = str(obj.modified_record)
                except BaseException:
                    obj_str = f"{obj.content_type.name} #{obj.object_id}"

                return mark_safe(f'<a href="{url}" target="_blank">{obj_str}</a>')
            except BaseException:
                return f"{obj.content_type.name} #{obj.object_id}"
        return "-"

    get_modified_record_display.short_description = "Zmodyfikowany rekord"

    def get_discipline_change(self, obj):
        """Show discipline change"""
        if obj.dyscyplina_before or obj.dyscyplina_after:
            before = str(obj.dyscyplina_before) if obj.dyscyplina_before else "brak"
            after = str(obj.dyscyplina_after) if obj.dyscyplina_after else "brak"

            if obj.dyscyplina_before and not obj.dyscyplina_after:
                return format_html(
                    '<span style="color: red;">{} → {}</span>', before, after
                )
            elif not obj.dyscyplina_before and obj.dyscyplina_after:
                return format_html(
                    '<span style="color: green;">{} → {}</span>', before, after
                )
            elif before != after:
                return format_html(
                    '<span style="color: orange;">{} → {}</span>', before, after
                )
            else:
                return format_html("<span>{}</span>", after)
        return "-"

    get_discipline_change.short_description = "Zmiana dyscypliny"

    def has_add_permission(self, request):
        """Disable manual creation of log entries"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete log entries"""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Log entries are read-only"""
        return False
