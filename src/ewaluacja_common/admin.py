from django.contrib import admin

from .models import Rodzaj_Autora


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
