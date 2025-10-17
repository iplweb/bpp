from django.contrib import admin

from .models import PrzeMapowanieZrodla


@admin.register(PrzeMapowanieZrodla)
class PrzeMapowanieZrodlaAdmin(admin.ModelAdmin):
    list_display = [
        "utworzono",
        "zrodlo_stare",
        "zrodlo_nowe",
        "liczba_rekordow",
        "utworzono_przez",
    ]
    list_filter = ["utworzono"]
    search_fields = [
        "zrodlo_stare__nazwa",
        "zrodlo_nowe__nazwa",
        "utworzono_przez__username",
    ]
    readonly_fields = [
        "utworzono",
        "utworzono_przez",
        "liczba_rekordow",
        "rekordy_historia",
    ]

    def has_add_permission(self, request):
        # Nie pozwalaj na ręczne dodawanie - tylko przez formularz
        return False

    def has_delete_permission(self, request, obj=None):
        # Możesz zezwolić na usuwanie tylko superuserowi
        return request.user.is_superuser
