from django.contrib import admin
from django.utils.html import format_html

from bpp.admin.core import DynamicAdminFilterMixin

from .models import PrzemapoaniePracAutora


@admin.register(PrzemapoaniePracAutora)
class PrzemapoaniePracAutoraAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = (
        "autor",
        "jednostka_z",
        "jednostka_do",
        "liczba_prac_ciaglych",
        "liczba_prac_zwartych",
        "liczba_prac",
        "utworzono",
        "utworzono_przez",
    )
    list_filter = (
        "utworzono",
        "jednostka_z",
        "jednostka_do",
    )
    search_fields = (
        "autor__nazwisko",
        "autor__imiona",
        "jednostka_z__nazwa",
        "jednostka_do__nazwa",
        "utworzono_przez__username",
    )
    date_hierarchy = "utworzono"
    readonly_fields = (
        "autor",
        "jednostka_z",
        "jednostka_do",
        "liczba_prac_ciaglych",
        "liczba_prac_zwartych",
        "liczba_prac",
        "utworzono",
        "utworzono_przez",
        "display_prace_ciagle_historia",
        "display_prace_zwarte_historia",
    )
    ordering = ("-utworzono",)

    fieldsets = (
        (
            "Podstawowe informacje",
            {
                "fields": (
                    "autor",
                    "jednostka_z",
                    "jednostka_do",
                    "utworzono",
                    "utworzono_przez",
                )
            },
        ),
        (
            "Statystyki",
            {"fields": ("liczba_prac_ciaglych", "liczba_prac_zwartych", "liczba_prac")},
        ),
        (
            "Historia przemapowanych prac ciągłych",
            {"fields": ("display_prace_ciagle_historia",), "classes": ("collapse",)},
        ),
        (
            "Historia przemapowanych prac zwartych",
            {"fields": ("display_prace_zwarte_historia",), "classes": ("collapse",)},
        ),
    )

    class Media:
        css = {
            "all": ["przemapuj_prace_autora/css/admin.css"],
        }

    def display_prace_ciagle_historia(self, obj):
        """Wyświetl historię przemapowanych prac ciągłych w czytelnej formie"""
        if not obj.prace_ciagle_historia:
            return "Brak danych"

        html = '<div class="przemapuj-historia-container">'
        html += '<table class="przemapuj-historia-table">'
        html += "<thead><tr>"
        html += "<th>ID</th>"
        html += "<th>Tytuł</th>"
        html += "<th>Rok</th>"
        html += "<th>Źródło</th>"
        html += "</tr></thead><tbody>"

        for praca in obj.prace_ciagle_historia:
            html += "<tr>"
            html += f"<td>{praca.get('id', '—')}</td>"
            html += f"<td>{praca.get('tytul', '—')}</td>"
            html += f"<td>{praca.get('rok', '—')}</td>"
            html += f"<td>{praca.get('zrodlo', '—') or '—'}</td>"
            html += "</tr>"

        html += "</tbody></table></div>"
        html += f'<p class="przemapuj-historia-summary"><strong>Łącznie: {len(obj.prace_ciagle_historia)} prac</strong></p>'
        return format_html(html)

    display_prace_ciagle_historia.short_description = "Przemapowane prace ciągłe"

    def display_prace_zwarte_historia(self, obj):
        """Wyświetl historię przemapowanych prac zwartych w czytelnej formie"""
        if not obj.prace_zwarte_historia:
            return "Brak danych"

        html = '<div class="przemapuj-historia-container">'
        html += '<table class="przemapuj-historia-table">'
        html += "<thead><tr>"
        html += "<th>ID</th>"
        html += "<th>Tytuł</th>"
        html += "<th>Rok</th>"
        html += "<th>ISBN</th>"
        html += "<th>Wydawnictwo</th>"
        html += "</tr></thead><tbody>"

        for praca in obj.prace_zwarte_historia:
            html += "<tr>"
            html += f"<td>{praca.get('id', '—')}</td>"
            html += f"<td>{praca.get('tytul', '—')}</td>"
            html += f"<td>{praca.get('rok', '—')}</td>"
            html += f"<td>{praca.get('isbn', '—') or '—'}</td>"
            html += f"<td>{praca.get('wydawnictwo', '—') or '—'}</td>"
            html += "</tr>"

        html += "</tbody></table></div>"
        html += f'<p class="przemapuj-historia-summary"><strong>Łącznie: {len(obj.prace_zwarte_historia)} prac</strong></p>'
        return format_html(html)

    display_prace_zwarte_historia.short_description = "Przemapowane prace zwarte"

    def has_add_permission(self, request):
        # Nie pozwalaj na ręczne dodawanie rekordów
        return False

    def has_delete_permission(self, request, obj=None):
        # Tylko superuser może usuwać logi
        return request.user.is_superuser
