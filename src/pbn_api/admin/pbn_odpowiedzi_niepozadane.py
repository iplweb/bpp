from django.contrib import admin

from bpp.admin.core import DynamicAdminFilterMixin
from pbn_api.admin.base import BasePBNAPIAdminNoReadonly
from pbn_api.models import PBNOdpowiedziNiepozadane


@admin.register(PBNOdpowiedziNiepozadane)
class PBNOdpowiedziNiepozadaneAdmin(DynamicAdminFilterMixin, BasePBNAPIAdminNoReadonly):
    list_display = [
        "kiedy_wyslano",
        "rodzaj_zdarzenia",
        "nowy_uid",
        "stary_uid",
        "uzytkownik",
        "rekord_display",
    ]
    ordering = ("-kiedy_wyslano",)
    search_fields = [
        "nowy_uid",
        "stary_uid",
        "uzytkownik",
        "dane_wyslane",
        "odpowiedz_serwera",
    ]
    readonly_fields = [
        "kiedy_wyslano",
        "content_type",
        "object_id",
        "rekord",
        "dane_wyslane",
        "odpowiedz_serwera",
        "rodzaj_zdarzenia",
        "uzytkownik",
        "stary_uid",
        "nowy_uid",
    ]
    fields = readonly_fields
    list_filter = ["rodzaj_zdarzenia", "kiedy_wyslano"]

    list_per_page = 50

    def has_add_permission(self, request):
        """Nie pozwalaj na ręczne dodawanie wpisów - są tworzone automatycznie"""
        return False

    def has_change_permission(self, request, obj=None):
        """Tylko do odczytu"""
        return True

    def has_delete_permission(self, request, obj=None):
        """Pozwól na usuwanie starych wpisów"""
        return True

    def rekord_display(self, obj):
        """Wyświetl skrócony opis rekordu"""
        if obj.rekord:
            return str(obj.rekord)[:100]
        return "-"

    rekord_display.short_description = "Rekord"
    rekord_display.admin_order_field = "object_id"
