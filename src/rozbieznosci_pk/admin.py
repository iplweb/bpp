from django.contrib import admin

from rozbieznosci_pk.models import IgnorujRozbieznoscPk, RozbieznosciPkLog


@admin.register(IgnorujRozbieznoscPk)
class IgnorujRozbieznoscPkAdmin(admin.ModelAdmin):
    list_display = ["object", "created_on"]

    def has_module_permission(self, request):
        return request.user.is_superuser


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        uczelnia = getattr(request, "_uczelnia", None)
        if uczelnia:
            return qs.filter(
                rekord__autorzy_set__jednostka__uczelnia=uczelnia
            ).distinct()
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
