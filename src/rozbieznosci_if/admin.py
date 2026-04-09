# TODO: Multi-site — filtruj po autorach z aktualnej uczelni
# Register your models here.
from django.contrib import admin

from rozbieznosci_if.models import IgnorujRozbieznoscIf, RozbieznosciIfLog


@admin.register(IgnorujRozbieznoscIf)
class IgnorujRozbieznoscIfAdmin(admin.ModelAdmin):
    list_display = ["object", "created_on"]


@admin.register(RozbieznosciIfLog)
class RozbieznosciIfLogAdmin(admin.ModelAdmin):
    list_display = ["rekord", "zrodlo", "if_before", "if_after", "user", "created_on"]
    list_filter = ["created_on", "user"]
    search_fields = ["rekord__tytul_oryginalny", "zrodlo__nazwa"]
    readonly_fields = [
        "rekord",
        "zrodlo",
        "if_before",
        "if_after",
        "user",
        "created_on",
    ]
    date_hierarchy = "created_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
