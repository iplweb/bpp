from django.contrib import admin
from django.utils.html import format_html

from bpp.admin.core import DynamicAdminFilterMixin

from .models import MetrykaAutora, StatusGenerowania


@admin.register(MetrykaAutora)
class MetrykaAutoraAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "autor",
        "dyscyplina_naukowa",
        "jednostka",
        "slot_maksymalny",
        "slot_nazbierany",
        "punkty_nazbierane",
        "srednia_za_slot_nazbierana",
        "procent_wykorzystania_slotow",
        "data_obliczenia",
    ]

    list_filter = ["dyscyplina_naukowa", "jednostka", "procent_wykorzystania_slotow"]

    search_fields = ["autor__nazwisko", "autor__imiona", "jednostka__nazwa"]

    readonly_fields = [
        "srednia_za_slot_nazbierana",
        "srednia_za_slot_wszystkie",
        "procent_wykorzystania_slotow",
        "data_obliczenia",
    ]

    fieldsets = [
        (
            "Podstawowe informacje",
            {"fields": ("autor", "dyscyplina_naukowa", "jednostka")},
        ),
        ("Parametry ewaluacji", {"fields": ("rok_min", "rok_max", "slot_maksymalny")}),
        (
            "Wyniki algorytmu plecakowego",
            {
                "fields": (
                    "slot_nazbierany",
                    "punkty_nazbierane",
                    "srednia_za_slot_nazbierana",
                    "prace_nazbierane",
                )
            },
        ),
        (
            "Wszystkie prace",
            {
                "fields": (
                    "slot_wszystkie",
                    "punkty_wszystkie",
                    "srednia_za_slot_wszystkie",
                    "liczba_prac_wszystkie",
                    "prace_wszystkie",
                )
            },
        ),
        (
            "Podsumowanie",
            {"fields": ("procent_wykorzystania_slotow", "data_obliczenia")},
        ),
    ]

    ordering = ["-srednia_za_slot_nazbierana"]


@admin.register(StatusGenerowania)
class StatusGenerowaniaAdmin(admin.ModelAdmin):
    list_display = [
        "status_display",
        "data_rozpoczecia",
        "data_zakonczenia",
        "liczba_przetworzonych",
        "liczba_bledow",
        "czas_trwania",
    ]

    readonly_fields = [
        "data_rozpoczecia",
        "data_zakonczenia",
        "w_trakcie",
        "liczba_przetworzonych",
        "liczba_bledow",
        "ostatni_komunikat",
        "task_id",
        "czas_trwania",
    ]

    fieldsets = [
        ("Status", {"fields": ("w_trakcie", "task_id")}),
        ("Daty", {"fields": ("data_rozpoczecia", "data_zakonczenia", "czas_trwania")}),
        ("Statystyki", {"fields": ("liczba_przetworzonych", "liczba_bledow")}),
        ("Komunikat", {"fields": ("ostatni_komunikat",)}),
    ]

    def status_display(self, obj):
        if obj.w_trakcie:
            return format_html('<span class="admin-status--orange">W trakcie</span>')
        elif obj.data_zakonczenia:
            return format_html('<span class="admin-status--green">Zakończone</span>')
        else:
            return format_html('<span class="admin-status--gray">Brak danych</span>')

    status_display.short_description = "Status"

    def has_add_permission(self, request):
        # Singleton - nie pozwalaj dodawać nowych
        return False

    def has_delete_permission(self, request, obj=None):
        # Singleton - nie pozwalaj usuwać
        return False
