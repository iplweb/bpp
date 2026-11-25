from django.contrib import admin

from bpp.admin.helpers.przemapowane_rekordy import przemapowane_publikacje_html

from .models import PrzeMapowanieZrodla


def _pk_z_logu(klucz):
    """Identyfikator publikacji z pozycji logu albo ``None``, gdy pozycja
    go nie ma (stare lub ręcznie utworzone wpisy) — taka pozycja jest
    pokazywana bez linków zamiast wywracać stronę."""
    if isinstance(klucz, (list, tuple)) and len(klucz) == 2:
        klucz = klucz[1]
    # ``bool`` jest podtypem ``int`` — nie jest identyfikatorem.
    if isinstance(klucz, int) and not isinstance(klucz, bool):
        return klucz
    return None


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
            (_pk_z_logu(r.get("id")), r.get("tytul", ""), r.get("rok"))
            for r in obj.rekordy_historia
        )

    def has_add_permission(self, request):
        # Nie pozwalaj na ręczne dodawanie - tylko przez formularz
        return False

    def has_change_permission(self, request, obj=None):
        # Log jest tylko do odczytu; podgląd daje uprawnienie ``view``
        # (grupa „wprowadzanie danych”).
        return False

    def has_delete_permission(self, request, obj=None):
        # Możesz zezwolić na usuwanie tylko superuserowi
        return request.user.is_superuser
