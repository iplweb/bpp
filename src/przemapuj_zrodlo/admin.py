from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import PrzemapowaZrodla


@admin.register(PrzemapowaZrodla)
class PrzemapowaZrodlaAdmin(admin.ModelAdmin):
    """Admin interface dla historii przemapowań źródeł."""

    list_display = [
        "utworzono",
        "zrodlo_z",
        "zrodlo_do",
        "liczba_publikacji",
        "utworzono_przez",
        "cofnieto",
        "cofnieto_przez",
        "akcje",
    ]

    list_filter = [
        "utworzono",
        "cofnieto",
    ]

    search_fields = [
        "zrodlo_z__nazwa",
        "zrodlo_do__nazwa",
        "utworzono_przez__username",
        "cofnieto_przez__username",
    ]

    readonly_fields = [
        "zrodlo_z",
        "zrodlo_do",
        "utworzono",
        "utworzono_przez",
        "liczba_publikacji",
        "publikacje_historia",
        "cofnieto",
        "cofnieto_przez",
    ]

    def has_add_permission(self, request):
        """Nie pozwalaj na ręczne dodawanie - tylko przez formularz."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Możesz zezwolić na usuwanie tylko superuserowi."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Nie pozwalaj na edycję - tylko przeglądanie."""
        return True

    def akcje(self, obj):
        """Kolumna z przyciskami akcji."""
        if obj.mozna_cofnac:
            url = reverse("przemapuj_zrodlo:cofnij", args=[obj.pk])
            return format_html(
                '<a href="{}" '
                'onclick="'
                "if (!confirm('Czy na pewno chcesz cofnąć to przemapowanie?\\n\\n"
                "Przywróci to {} publikacji do źródła \\'{}\\'.')) return false; "
                "if (this.getAttribute('data-clicked')) return false; "
                "this.setAttribute('data-clicked', 'true'); "
                "var form = document.createElement('form'); "
                "form.method = 'POST'; "
                "form.action = this.href; "
                "var csrf = document.createElement('input'); "
                "csrf.type = 'hidden'; "
                "csrf.name = 'csrfmiddlewaretoken'; "
                "function getCookie(name) {{ "
                "  var value = '; ' + document.cookie; "
                "  var parts = value.split('; ' + name + '='); "
                "  if (parts.length === 2) return parts.pop().split(';').shift(); "
                "}} "
                "var csrfFromCookie = getCookie('csrftoken'); "
                "var csrfFromInput = document.querySelector('[name=csrfmiddlewaretoken]'); "
                "csrf.value = csrfFromInput ? csrfFromInput.value : csrfFromCookie; "
                "form.appendChild(csrf); "
                "document.body.appendChild(form); "
                "form.submit(); "
                'return false;" '
                'style="background-color: #ff6b35; color: white; border: none; '
                "padding: 0.5rem 1rem; cursor: pointer; border-radius: 3px; "
                'text-decoration: none; display: inline-block;">'
                '<span class="fi-refresh"></span> Cofnij'
                "</a>",
                url,
                obj.liczba_publikacji,
                obj.zrodlo_z.nazwa if obj.zrodlo_z else "[usunięte]",
            )
        elif obj.jest_cofniete:
            return format_html(
                '<span style="color: #999; font-style: italic;">'
                '<span class="fi-check"></span> Cofnięte'
                "</span>"
            )
        else:
            return format_html('<span style="color: #999;">-</span>')

    akcje.short_description = "Akcje"
    akcje.allow_tags = True

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/foundicons/3.0.0/foundation-icons.min.css",
            )
        }
