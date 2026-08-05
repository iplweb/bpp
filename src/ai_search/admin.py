from django.contrib import admin

from ai_search.models import AISearchQuery


@admin.register(AISearchQuery)
class AISearchQueryAdmin(admin.ModelAdmin):
    """Log zapytań AI (NL->DjangoQL) wraz z kosztem — wyłącznie do odczytu.

    Brak dodawania/edycji: wpisy tworzy tylko ``ZapytanieAIView._log``
    (ślad audytowy kosztów i skuteczności tłumaczenia, nie dane do ręcznej
    edycji)."""

    list_display = (
        "created",
        "user",
        "wybrany_model_danych",
        "success",
        "cost_pln",
        "cost_usd",
        "retried",
    )
    list_filter = ("success", "wybrany_model_danych", "retried", "created")
    search_fields = ("pytanie", "wygenerowany_query")
    readonly_fields = [f.name for f in AISearchQuery._meta.fields]
    date_hierarchy = "created"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
