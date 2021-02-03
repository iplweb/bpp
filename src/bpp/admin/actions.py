from django.utils.translation import ngettext

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
