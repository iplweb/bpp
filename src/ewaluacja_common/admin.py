from django.contrib import admin

from .models import OkresEwaluacji, Rodzaj_Autora


@admin.register(Rodzaj_Autora)
class Rodzaj_AutoraAdmin(admin.ModelAdmin):
    list_display = ["skrot", "nazwa", "jest_w_n", "licz_sloty"]
    list_filter = ["jest_w_n", "licz_sloty"]
    search_fields = ["nazwa", "skrot"]
    ordering = ["skrot"]

    fieldsets = (
        (None, {"fields": ("nazwa", "skrot")}),
        (
            "Ustawienia",
            {
                "fields": ("jest_w_n", "licz_sloty"),
                "description": "Konfiguracja zachowania dla tego rodzaju autora",
            },
        ),
    )


@admin.register(OkresEwaluacji)
class OkresEwaluacjiAdmin(admin.ModelAdmin):
    """Tylko do odczytu: okresy definiuje wydanie (migracja danych), nie
    użytkownik — od nich zależą zapisane wyniki liczby N, metryk i
    optymalizacji."""

    list_display = ["__str__", "rok_od", "rok_do", "uwagi"]
    ordering = ["rok_od"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
