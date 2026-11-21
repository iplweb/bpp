"""Admin `pbn_integrator` — na razie wyłącznie rejestr wskrzeszeń.

Rejestr osiągalny tylko przez ``manage.py shell`` nie spełniałby swojej roli:
to jego dostępność dla operatora była całym uzasadnieniem zmiany decyzji #14
planu fazy 03 („POMIŃ + ZARAPORTUJ" → „PRZYWRÓĆ + ODNOTUJ"). Kontekst:
docstring ``RekordPrzywroconyPrzezImport``.
"""

from django.contrib import admin

from .models import RekordPrzywroconyPrzezImport


@admin.register(RekordPrzywroconyPrzezImport)
class RekordPrzywroconyPrzezImportAdmin(admin.ModelAdmin):
    """Ślad audytowy — TYLKO DO ODCZYTU.

    Wpisy powstają wyłącznie w ``pbn_integrator/kosz.py``, na ścieżce importu.
    Rejestr, w którym operator może dopisać, zmienić albo skasować wpis,
    przestaje być dowodem — a dowodem miał być, bo to on równoważy ryzyko
    auto-restore'u wskazane w pierwotnej decyzji #14. Stąd trzy `False` niżej,
    a nie samo `readonly_fields` (to ostatnie chowa pola, ale wciąż pozwala
    dodać i skasować wiersz).
    """

    list_display = (
        "rekord",
        "przywrocono",
        "zrodlo_importu",
        "pbn_uid",
    )
    list_filter = ("zrodlo_importu", "content_type", "przywrocono")
    # `object_id` w wyszukiwarce, bo operator idzie tu zwykle od konkretnej
    # publikacji („czy TEN rekord wrócił?") — pod to jest indeks
    # `pbnint_przywr_ct_objid_idx`.
    search_fields = ("object_id", "pbn_uid__pk")
    date_hierarchy = "przywrocono"
    # `rekord` to GenericForeignKey — nie da się go `select_related`, więc
    # changelista i tak dobija po jednym zapytaniu na wiersz przy renderowaniu
    # `__str__`. `content_type` jest zwykłym FK i tyle da się tanio uprzedzić.
    list_select_related = ("content_type", "pbn_uid")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
