import logging

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html

from dspace_api.links import public_url_for_sent
from dspace_api.models import Mapowanie_DSpace, SentToDSpace

logger = logging.getLogger(__name__)


@admin.register(Mapowanie_DSpace)
class Mapowanie_DSpaceAdmin(admin.ModelAdmin):
    list_display = ["uczelnia", "charakter_formalny", "collection_uuid", "opis"]
    list_filter = ["uczelnia"]
    autocomplete_fields = ["charakter_formalny"]
    search_fields = ["opis"]

    class Media:
        js = ("dspace_api/dspace_collection_picker.js",)

    # Feature A: jedna uczelnia → zawsze domyślna; wiele → uczelnia z requestu.
    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        if "uczelnia" not in data:
            from bpp.models import Uczelnia

            uczelnia = Uczelnia.objects.get_for_request(request)
            if uczelnia is not None:
                data["uczelnia"] = uczelnia.pk
        return data

    # Feature B: pole collection_uuid jako combobox zasilany na żywo z DSpace.
    # Progressive enhancement — bez JS zostaje zwykłe pole tekstowe UUID.
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "collection_uuid" and formfield is not None:
            formfield.widget.attrs.update(
                {
                    "class": "dspace-collection-picker",
                    "data-collections-url": reverse(
                        "admin:dspace_api_mapowanie_dspace_collections"
                    ),
                    "data-uczelnia-field": "id_uczelnia",
                }
            )
        return formfield

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "collections/",
                self.admin_site.admin_view(self.collections_json_view),
                name="dspace_api_mapowanie_dspace_collections",
            ),
        ]
        return custom + urls

    def collections_json_view(self, request):
        """Zwróć listę kolekcji DSpace wybranej uczelni jako JSON.

        Błędy (timeout/auth/sieć/brak konfiguracji) zwracamy jako ``error`` ze
        statusem 200 + pustą listą — JS pokazuje wtedy fallback do ręcznego
        wpisania UUID, zamiast traktować to jak twardy błąd HTTP."""
        uczelnia_id = request.GET.get("uczelnia")
        if not uczelnia_id:
            return JsonResponse({"collections": []})

        from bpp.models import Uczelnia
        from dspace_api.client import DSpaceClient

        uczelnia = Uczelnia.objects.filter(pk=uczelnia_id).first()
        if uczelnia is None:
            return JsonResponse({"error": "Nie znaleziono uczelni.", "collections": []})
        if not (uczelnia.dspace_api_endpoint or "").strip():
            return JsonResponse(
                {
                    "error": "Uczelnia nie ma skonfigurowanego adresu API DSpace.",
                    "collections": [],
                }
            )
        try:
            collections = DSpaceClient(uczelnia).fetch_collections()
        except Exception:
            logger.warning(
                "DSpace: pobranie listy kolekcji nie powiodło się dla uczelni %s",
                uczelnia_id,
                exc_info=True,
            )
            return JsonResponse(
                {
                    "error": "Nie udało się pobrać listy kolekcji z DSpace. "
                    "Wpisz UUID kolekcji ręcznie.",
                    "collections": [],
                }
            )
        return JsonResponse({"collections": collections})


@admin.register(SentToDSpace)
class SentToDSpaceAdmin(admin.ModelAdmin):
    list_display = [
        "object_id",
        "content_type",
        "uczelnia",
        "submitted_successfully",
        "dspace_uuid",
        "repozytorium_link",
        "last_updated_on",
    ]
    list_filter = ["submitted_successfully", "uczelnia"]
    search_fields = ["object_id", "exception"]
    readonly_fields = [
        "content_type",
        "object_id",
        "uczelnia",
        "dspace_uuid",
        "dspace_handle",
        "repozytorium_link",
        "bitstreams",
        "data_sent",
        "submitted_successfully",
        "submitted_at",
        "exception",
        "api_response_status",
        "last_updated_on",
    ]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Zobacz w repozytorium")
    def repozytorium_link(self, obj):
        url = public_url_for_sent(obj)
        if not url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">🔗 Otwórz w repozytorium</a>',
            url,
        )
