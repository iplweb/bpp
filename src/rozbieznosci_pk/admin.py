from django.contrib import admin

from rozbieznosci_pk.models import IgnorujRozbieznoscPk, RozbieznosciPkLog


@admin.register(IgnorujRozbieznoscPk)
class IgnorujRozbieznoscPkAdmin(admin.ModelAdmin):
    list_display = ["object", "created_on"]


@admin.register(RozbieznosciPkLog)
class RozbieznosciPkLogAdmin(admin.ModelAdmin):
    list_display = ["rekord", "zrodlo", "pk_before", "pk_after", "user", "created_on"]
    list_filter = ["created_on", "user"]
    search_fields = ["rekord__tytul_oryginalny", "zrodlo__nazwa"]
    readonly_fields = [
        "rekord",
        "zrodlo",
        "pk_before",
        "pk_after",
        "user",
        "created_on",
    ]
    date_hierarchy = "created_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
