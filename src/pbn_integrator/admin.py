"""Admin `pbn_integrator` — raport rekordów z kosza pominiętych przez import."""

from django.contrib import admin

from .models import RekordWKoszuPominietyPrzezImport


@admin.register(RekordWKoszuPominietyPrzezImport)
class RekordWKoszuPominietyPrzezImportAdmin(admin.ModelAdmin):
    """Raport TYLKO DO ODCZYTU — wpisy tworzy wyłącznie import
    (``pbn_integrator/kosz.py``). Rekord przywraca się z kosza w adminie
    danego typu publikacji (akcja „♻️ Przywróć zaznaczone")."""

    list_display = ("komunikat", "pominieto", "ile_razy", "zrodlo_importu")
    list_filter = ("zrodlo_importu", "content_type", "pominieto")
    search_fields = ("object_id", "pbn_uid__pk", "komunikat")
    date_hierarchy = "pominieto"
    list_select_related = ("content_type", "pbn_uid")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
