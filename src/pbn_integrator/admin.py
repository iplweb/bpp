"""Admin `pbn_integrator` — raport rekordów z kosza pominiętych przez import."""

from django.contrib import admin

from .models import PobieranieOdpowiednikowPBN, RekordWKoszuPominietyPrzezImport


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


@admin.register(PobieranieOdpowiednikowPBN)
class PobieranieOdpowiednikowPBNAdmin(admin.ModelAdmin):
    """Zlecenia grupowego pobierania odpowiedników z PBN — postęp i raport.

    TYLKO DO ODCZYTU: zlecenia tworzy akcja grupowa „Pobierz odpowiedniki
    z PBN (w tle)” na listach publikacji i autorów."""

    list_display = (
        "utworzono",
        "rodzaj",
        "liczba_rekordow",
        "stan",
        "przetworzono",
        "zlecil",
    )
    list_filter = ("rodzaj",)
    date_hierarchy = "utworzono"
    change_form_template = "admin/pbn_integrator/pobieranie_odpowiednikow.html"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("zlecil", "content_type")
        if request.user.is_superuser:
            return qs
        # Raport zawiera tytuły prac i nazwiska — widzi go zlecający.
        return qs.filter(zlecil=request.user)

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    @admin.display(description="Rekordów")
    def liczba_rekordow(self, obj):
        return obj.liczba_rekordow

    @admin.display(description="Stan")
    def stan(self, obj):
        return obj.stan

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        from django.contrib import messages
        from django.http import HttpResponseRedirect

        from .pobieranie_odpowiednikow import podsumowanie, ponow

        zlecenie = self.get_object(request, object_id) if object_id else None
        if zlecenie is not None and request.method == "POST":
            # Jedyna dozwolona zmiana: ponowienie przerwanego zlecenia.
            if "_ponow" in request.POST and ponow(zlecenie):
                self.message_user(
                    request, "Zlecenie wróciło do kolejki.", messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    "Tego zlecenia nie można teraz ponowić — nie jest przerwane.",
                    messages.WARNING,
                )
            return HttpResponseRedirect(request.path)
        extra_context = dict(extra_context or {})
        if zlecenie is not None:
            model = zlecenie.content_type.model_class()
            extra_context.update(
                zlecenie=zlecenie,
                grupy=podsumowanie(zlecenie),
                url_rekordu=f"admin:{model._meta.app_label}_{model._meta.model_name}"
                "_change",
            )
        return super().changeform_view(request, object_id, form_url, extra_context)
