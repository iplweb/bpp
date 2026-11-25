from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from bpp.admin.helpers.przemapowane_rekordy import przemapowane_publikacje_html

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
        "przemapowane_publikacje",
        "cofnieto",
        "cofnieto_przez",
    ]
    exclude = ["publikacje_historia"]

    @admin.display(description="Przemapowane publikacje")
    def przemapowane_publikacje(self, obj):
        return przemapowane_publikacje_html(
            (p.get("id"), p.get("tytul", ""), p.get("rok"))
            for p in obj.publikacje_historia
        )

    def has_add_permission(self, request):
        """Nie pozwalaj na ręczne dodawanie - tylko przez formularz."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Możesz zezwolić na usuwanie tylko superuserowi."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Log jest tylko do odczytu; podgląd daje uprawnienie ``view``
        (grupa „wprowadzanie danych”)."""
        return False

    def akcje(self, obj):
        """Kolumna z przyciskami akcji."""
        if obj.mozna_cofnac:
            # Tekst potwierdzenia idzie w atrybucie ``data-*``, a klik
            # obsługuje ``admin_cofnij.js``. Nazwa źródła NIE może trafić do
            # inline JS: przeglądarka dekoduje encje HTML przed wykonaniem
            # ``onclick``, więc apostrof w nazwie psuł potwierdzenie
            # (i pozwalał wstrzyknąć kod).
            nazwa = obj.zrodlo_z.nazwa if obj.zrodlo_z else "[usunięte]"
            return format_html(
                '<a href="{}" class="admin-action-btn--warning '
                'przemapowanie-cofnij" data-potwierdzenie="{}">'
                '<span class="fi-refresh"></span> Cofnij</a>',
                reverse("przemapuj_zrodlo:cofnij", args=[obj.pk]),
                "Czy na pewno chcesz cofnąć to przemapowanie?\n\n"
                f"Przywróci to {obj.liczba_publikacji} publikacji "
                f"do źródła „{nazwa}”.",
            )
        elif obj.jest_cofniete:
            return format_html(
                '<span class="admin-status--muted admin-status--italic">'
                '<span class="fi-check"></span> Cofnięte'
                "</span>"
            )
        else:
            return format_html('<span class="admin-status--muted">-</span>')

    akcje.short_description = "Akcje"
    akcje.allow_tags = True

    class Media:
        # Foundation-Icons z lokalnych statików (pakiet npm foundation-datepicker
        # dostarcza CSS razem z fontami) — ten sam plik, którego używa `bare.html`
        # i szablony admina. Wcześniej był tu URL do cdnjs: zewnętrzna zależność
        # sieciowa przy każdym otwarciu ekranu.
        css = {"all": ("foundation-datepicker/foundation/fonts/foundation-icons.css",)}
        js = ("przemapuj_zrodlo/admin_cofnij.js",)
