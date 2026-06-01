from django.contrib import admin

from .models import DefinicjaRaportu


@admin.register(DefinicjaRaportu)
class DefinicjaRaportuAdmin(admin.ModelAdmin):
    list_display = [
        "nazwa",
        "poziom",
        "report",
        "poziom_dostepu",
        "aktywny",
        "kolejnosc",
    ]
    list_editable = ["aktywny", "kolejnosc"]
    list_filter = ["poziom", "poziom_dostepu", "aktywny"]
    search_fields = ["nazwa", "slug"]
    prepopulated_fields = {"slug": ("nazwa",)}
    filter_horizontal = ["wymagane_grupy", "uczelnie"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "nazwa",
                    "slug",
                    "poziom",
                    "report",
                    "kolejnosc",
                    "aktywny",
                ]
            },
        ),
        (
            "Uprawnienia i widoczność",
            {
                "fields": ["poziom_dostepu", "wymagane_grupy", "uczelnie"],
                "description": "Kto widzi raport (poziom dostępu + opcjonalne "
                "grupy) i na stronach których uczelni się pojawia "
                "(puste = wszędzie).",
            },
        ),
    ]
