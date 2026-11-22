from django.contrib import admin

from bpp.models import Wersja_Przeliczenia


@admin.register(Wersja_Przeliczenia)
class Wersja_PrzeliczeniaAdmin(admin.ModelAdmin):
    """Tylko podgląd: które przeliczenie i kiedy BPP zlecił po aktualizacji
    (``bpp.przeliczenia``). Wpisy zakłada i zmienia worker Celery."""

    list_display = ("nazwa", "wersja", "zlecono", "oznaczono_rekordow")
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
