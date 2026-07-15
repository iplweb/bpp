"""Admin operacji „Import pracowników i jednostek".

liveops dostarcza gotowy, read-only ``LiveOperationAdmin`` (stan, traceback,
wynik, etapy). Do tej pory nikt nie zarejestrował konkretnego modelu, więc
w adminie nie było ANI JEDNEJ operacji importu — diagnoza błędu (np. operacji
``bd90660e``) wymagała ręcznego zaglądania do bazy. Rejestrujemy operację
oraz jej wiersze (podgląd rezultatów per wiersz)."""

from django.contrib import admin
from django.utils.html import format_html
from liveops.admin import LiveOperationAdmin

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@admin.register(ImportPracownikow)
class ImportPracownikowAdmin(LiveOperationAdmin):
    """Read-only widok operacji importu — stan pipeline'u + traceback błędu."""

    list_display = (
        "short_id",
        "owner",
        "stan",
        "state",
        "created_on",
        "finished_on",
        "finished_successfully",
        "blad_skrocony",
    )
    list_filter = ("finished_successfully", "cancelled", "stan")
    search_fields = ("id", "owner__username", "traceback")

    @admin.display(description="Błąd (skrót)")
    def blad_skrocony(self, obj):
        """Ostatnia linia tracebacku — czytelne „co poszło nie tak" wprost na
        liście, bez wchodzenia w szczegóły."""
        czytelny = obj.readable_exception()
        if not czytelny:
            return "—"
        return format_html("<span style='color:#a00'>{}</span>", czytelny)


@admin.register(ImportPracownikowRow)
class ImportPracownikowRowAdmin(admin.ModelAdmin):
    """Podgląd wierszy (rezultatów) importu — kogo/jak dopasowano: autora,
    jednostkę i tytuł. Read-only: wiersze produkuje pipeline analizy."""

    list_display = (
        "id",
        "parent",
        "autor",
        "confidence",
        "jednostka",
        "jednostka_status",
        "tytul",
        "zmiany_potrzebne",
    )
    list_filter = ("confidence", "jednostka_status", "zmiany_potrzebne")
    search_fields = (
        "parent__id",
        "autor__nazwisko",
        "autor__imiona",
        "jednostka__nazwa",
    )
    raw_id_fields = ("parent", "autor", "jednostka", "autor_jednostka", "tytul")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
