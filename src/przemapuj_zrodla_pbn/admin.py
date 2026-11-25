from django.contrib import admin

from bpp.admin.helpers.przemapowane_rekordy import przemapowane_publikacje_html

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
        "przemapowane_rekordy",
    ]
    exclude = ["rekordy_historia"]

    @admin.display(description="Przemapowane rekordy")
    def przemapowane_rekordy(self, obj):
        # W logu klucz rekordu to para (content_type_id, object_id) z widoku
        # ``Rekord``; źródło mają tylko wydawnictwa ciągłe.
        return przemapowane_publikacje_html(
            (r["id"][1], r.get("tytul", ""), r.get("rok")) for r in obj.rekordy_historia
        )

    def has_add_permission(self, request):
        # Nie pozwalaj na ręczne dodawanie - tylko przez formularz
        return False

    def has_delete_permission(self, request, obj=None):
        # Możesz zezwolić na usuwanie tylko superuserowi
        return request.user.is_superuser
