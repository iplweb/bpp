from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp.admin.core import DynamicAdminFilterMixin
from pbn_api.models import Scientist

from .models import (
    DuplicateCandidate,
    DuplicateScanRun,
    IgnoredAuthor,
    LogScalania,
    NotADuplicate,
)


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


@admin.register(DuplicateScanRun)
class DuplicateScanRunAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "status",
        "get_progress",
        "total_authors_to_scan",
        "authors_scanned",
        "duplicates_found",
        "created_by",
        "started_at",
        "finished_at",
    ]

    list_filter = [
        "status",
        "started_at",
        "created_by",
    ]

    search_fields = [
        "created_by__username",
        "error_message",
    ]

    readonly_fields = [
        "started_at",
        "finished_at",
        "status",
        "total_authors_to_scan",
        "authors_scanned",
        "duplicates_found",
        "error_message",
        "celery_task_id",
        "created_by",
    ]

    date_hierarchy = "started_at"
    ordering = ["-started_at"]
    actions = ["start_new_scan", "cancel_scan"]

    def get_progress(self, obj):
        """Display progress percentage with bar"""
        percent = obj.progress_percent
        if obj.status == DuplicateScanRun.Status.RUNNING:
            return format_html(
                '<div style="width:100px;background:#ddd;">'
                '<div style="width:{}%;background:#4CAF50;height:20px;"></div>'
                "</div> {}%",
                percent,
                percent,
            )
        return f"{percent}%"

    get_progress.short_description = "Postęp"

    @admin.action(description="Uruchom nowe skanowanie")
    def start_new_scan(self, request, queryset):
        """Start a new duplicate scan"""
        from .tasks import scan_for_duplicates

        # Check if any scan is already running
        if DuplicateScanRun.objects.filter(
            status=DuplicateScanRun.Status.RUNNING
        ).exists():
            self.message_user(
                request,
                "Skanowanie jest już w trakcie. Poczekaj na jego zakończenie.",
                level="warning",
            )
            return

        # Start new scan
        scan_for_duplicates.delay(user_id=request.user.pk)
        self.message_user(
            request,
            "Nowe skanowanie duplikatów zostało uruchomione w tle.",
            level="success",
        )

    @admin.action(description="Anuluj skanowanie")
    def cancel_scan(self, request, queryset):
        """Cancel selected running scans"""
        from .tasks import cancel_scan

        cancelled_count = 0
        for scan_run in queryset.filter(status=DuplicateScanRun.Status.RUNNING):
            cancel_scan.delay(scan_run.pk)
            cancelled_count += 1

        if cancelled_count:
            self.message_user(
                request,
                f"Anulowano {cancelled_count} skanowanie(ń).",
                level="success",
            )
        else:
            self.message_user(
                request,
                "Brak aktywnych skanowań do anulowania.",
                level="warning",
            )

    def has_add_permission(self, request):
        """Disable manual creation - use action instead"""
        return False

    def has_change_permission(self, request, obj=None):
        """Scan runs are read-only"""
        return False


@admin.register(DuplicateCandidate)
class DuplicateCandidateAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "get_main_autor_link",
        "get_duplicate_autor_link",
        "get_confidence_display",
        "status",
        "main_publications_count",
        "duplicate_publications_count",
        "reviewed_by",
        "reviewed_at",
    ]

    list_filter = [
        "status",
        "scan_run",
        ("confidence_score", admin.AllValuesFieldListFilter),
        "reviewed_at",
    ]

    search_fields = [
        "main_autor__nazwisko",
        "main_autor__imiona",
        "duplicate_autor__nazwisko",
        "duplicate_autor__imiona",
        "main_autor_name",
        "duplicate_autor_name",
    ]

    readonly_fields = [
        "scan_run",
        "main_autor",
        "main_osoba_z_instytucji",
        "duplicate_autor",
        "confidence_score",
        "confidence_percent",
        "reasons",
        "main_autor_name",
        "duplicate_autor_name",
        "main_publications_count",
        "duplicate_publications_count",
        "created_at",
        "reviewed_at",
        "reviewed_by",
    ]

    date_hierarchy = "created_at"
    ordering = ["-confidence_score"]

    def get_main_autor_link(self, obj):
        """Create link to main author"""
        if obj.main_autor:
            url = reverse("admin:bpp_autor_change", args=[obj.main_autor.pk])
            return mark_safe(f'<a href="{url}">{obj.main_autor_name}</a>')
        return obj.main_autor_name

    get_main_autor_link.short_description = "Autor główny"
    get_main_autor_link.admin_order_field = "main_autor__nazwisko"

    def get_duplicate_autor_link(self, obj):
        """Create link to duplicate author"""
        if obj.duplicate_autor:
            url = reverse("admin:bpp_autor_change", args=[obj.duplicate_autor.pk])
            return mark_safe(f'<a href="{url}">{obj.duplicate_autor_name}</a>')
        return obj.duplicate_autor_name

    get_duplicate_autor_link.short_description = "Potencjalny duplikat"
    get_duplicate_autor_link.admin_order_field = "duplicate_autor__nazwisko"

    def get_confidence_display(self, obj):
        """Display confidence with color coding"""
        percent = obj.confidence_percent * 100
        if percent >= 70:
            color = "green"
        elif percent >= 50:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {};">{:.0f}% ({})</span>',
            color,
            percent,
            obj.confidence_score,
        )

    get_confidence_display.short_description = "Pewność"
    get_confidence_display.admin_order_field = "confidence_score"

    def has_add_permission(self, request):
        """Disable manual creation"""
        return False

    def has_change_permission(self, request, obj=None):
        """Candidates are managed through the deduplication view"""
        return False
