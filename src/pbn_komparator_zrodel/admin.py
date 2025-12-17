from django.contrib import admin

from .models import KomparatorZrodelMeta, LogAktualizacjiZrodla, RozbieznoscZrodlaPBN


@admin.register(RozbieznoscZrodlaPBN)
class RozbieznoscZrodlaPBNAdmin(admin.ModelAdmin):
    list_display = [
        "zrodlo",
        "rok",
        "ma_rozbieznosc_punktow",
        "punkty_bpp",
        "punkty_pbn",
        "ma_rozbieznosc_dyscyplin",
        "updated_at",
    ]
    list_filter = ["ma_rozbieznosc_punktow", "ma_rozbieznosc_dyscyplin", "rok"]
    search_fields = ["zrodlo__nazwa", "zrodlo__issn", "zrodlo__e_issn"]
    raw_id_fields = ["zrodlo"]
    readonly_fields = [
        "zrodlo",
        "rok",
        "ma_rozbieznosc_punktow",
        "punkty_bpp",
        "punkty_pbn",
        "ma_rozbieznosc_dyscyplin",
        "dyscypliny_bpp",
        "dyscypliny_pbn",
        "created_at",
        "updated_at",
    ]
    ordering = ["-updated_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LogAktualizacjiZrodla)
class LogAktualizacjiZrodlaAdmin(admin.ModelAdmin):
    list_display = [
        "zrodlo",
        "rok",
        "typ_zmiany",
        "user",
        "created_at",
    ]
    list_filter = ["typ_zmiany", "rok"]
    search_fields = ["zrodlo__nazwa"]
    raw_id_fields = ["zrodlo", "user"]
    readonly_fields = [
        "zrodlo",
        "rok",
        "typ_zmiany",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(KomparatorZrodelMeta)
class KomparatorZrodelMetaAdmin(admin.ModelAdmin):
    list_display = [
        "ostatnie_uruchomienie",
        "status",
    ]
    readonly_fields = [
        "ostatnie_uruchomienie",
        "status",
        "ostatni_blad",
        "statystyki",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
