from django.contrib import admin

from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@admin.register(IgnorowanaRozbieznosc)
class IgnorowanaRozbieznoscAdmin(admin.ModelAdmin):
    list_display = ["metryka", "rekord", "created_on"]
    list_filter = ["metryka", "created_on"]
    search_fields = ["rekord__tytul_oryginalny"]


@admin.register(RozbieznoscLog)
class RozbieznoscLogAdmin(admin.ModelAdmin):
    list_display = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    list_filter = ["metryka", "created_on", "user"]
    search_fields = ["rekord__tytul_oryginalny", "zrodlo__nazwa"]
    readonly_fields = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    date_hierarchy = "created_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
