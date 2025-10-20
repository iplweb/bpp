from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import OptimizationAuthorResult, OptimizationPublication, OptimizationRun


class OptimizationPublicationInline(admin.TabularInline):
    model = OptimizationPublication
    extra = 0
    readonly_fields = (
        "rekord_id",
        "kind",
        "points",
        "slots",
        "is_low_mono",
        "author_count",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OptimizationAuthorResultInline(admin.TabularInline):
    model = OptimizationAuthorResult
    extra = 0
    readonly_fields = (
        "autor",
        "rodzaj_autora",
        "total_points",
        "total_slots",
        "mono_slots",
        "slot_limit_total",
        "slot_limit_mono",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dyscyplina_naukowa",
        "uczelnia",
        "started_at",
        "status",
        "total_points",
        "total_publications",
        "low_mono_percentage",
        "view_results_link",
    )
    list_filter = ("status", "dyscyplina_naukowa", "uczelnia", "started_at")
    search_fields = ("dyscyplina_naukowa__nazwa", "uczelnia__nazwa")
    readonly_fields = (
        "dyscyplina_naukowa",
        "uczelnia",
        "started_at",
        "finished_at",
        "status",
        "total_points",
        "total_slots",
        "total_publications",
        "low_mono_count",
        "low_mono_percentage",
        "validation_passed",
        "view_results_link",
    )
    inlines = [OptimizationAuthorResultInline]
    date_hierarchy = "started_at"

    def view_results_link(self, obj):
        if obj.pk:
            url = reverse("ewaluacja_optymalizacja:run-detail", args=[obj.pk])
            return format_html('<a href="{}">Zobacz wyniki</a>', url)
        return "-"

    view_results_link.short_description = "Wyniki"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(OptimizationAuthorResult)
class OptimizationAuthorResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "optimization_run",
        "autor",
        "rodzaj_autora",
        "total_points",
        "total_slots",
        "mono_slots",
    )
    list_filter = ("optimization_run__dyscyplina_naukowa", "rodzaj_autora")
    search_fields = ("autor__nazwisko", "autor__imiona")
    readonly_fields = (
        "optimization_run",
        "autor",
        "rodzaj_autora",
        "total_points",
        "total_slots",
        "mono_slots",
        "slot_limit_total",
        "slot_limit_mono",
    )
    inlines = [OptimizationPublicationInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(OptimizationPublication)
class OptimizationPublicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author_result",
        "rekord_id",
        "kind",
        "points",
        "slots",
        "is_low_mono",
        "efficiency",
    )
    list_filter = ("kind", "is_low_mono")
    readonly_fields = (
        "author_result",
        "rekord_id",
        "kind",
        "points",
        "slots",
        "is_low_mono",
        "author_count",
        "efficiency",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
