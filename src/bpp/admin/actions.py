from django.utils.translation import ngettext

from bpp.admin.helpers.pbn_api.gui import (
    sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
    sprobuj_wyslac_do_pbn_gui,
)
from bpp.models import Status_Korekty


def ustaw_status(queryset, nazwa_statusu):
    status = Status_Korekty.objects.get(nazwa=nazwa_statusu)
    return queryset.exclude(status_korekty=status).update(status_korekty=status)


def ustaw_przed_korekta(modeladmin, request, queryset):
    updated = ustaw_status(queryset, "przed korektą")
    modeladmin.message_user(
        request,
        f"Ustawiono status 'przed korektą' dla {updated} {ngettext('rekordu', 'rekordów', updated)}",
    )


ustaw_przed_korekta.short_description = "Ustaw status korekty: przed korektą"


def ustaw_po_korekcie(modeladmin, request, queryset):
    updated = ustaw_status(queryset, "po korekcie")
    modeladmin.message_user(
        request,
        f"Ustawiono status 'po korekcie' dla {updated} {ngettext('rekordu', 'rekordów', updated)}",
    )


ustaw_po_korekcie.short_description = "Ustaw status korekty: po korekcie"


def ustaw_w_trakcie_korekty(modeladmin, request, queryset):
    updated = ustaw_status(queryset, "w trakcie korekty")
    modeladmin.message_user(
        request,
        f"Ustawiono status 'w trakcie korekty' dla {updated} {ngettext('rekordu', 'rekordów', updated)}",
    )


ustaw_w_trakcie_korekty.short_description = "Ustaw status korekty: w trakcie korekty"


def wyslij_do_pbn(modeladmin, request, queryset):
    for elem in queryset:
        sprobuj_wyslac_do_pbn_gui(request, elem)


wyslij_do_pbn.short_description = "Wyślij do PBN"


def wyslij_do_pbn_w_tle(modeladmin, request, queryset):
    for elem in queryset:
        sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request, elem)


wyslij_do_pbn_w_tle.short_description = "Wyślij do PBN w tle"
