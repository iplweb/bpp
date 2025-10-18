from django.contrib import messages
from django.utils.translation import ngettext

from bpp.admin.helpers.pbn_api.gui import (
    sprobuj_wyslac_do_pbn_gui,
)
from bpp.models import Status_Korekty
from pbn_export_queue.tasks import queue_pbn_export_batch


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
    count = queryset.count()
    if count > 10:
        modeladmin.message_user(
            request,
            f"Możesz wysłać maksymalnie 10 rekordów naraz. "
            f"Wybrano {count} {ngettext('rekord', 'rekordów', count)}.",
            messages.ERROR,
        )
        return

    for elem in queryset:
        sprobuj_wyslac_do_pbn_gui(request, elem)


wyslij_do_pbn.short_description = "Wyślij do PBN"


def wyslij_do_pbn_w_tle(modeladmin, request, queryset):
    count = queryset.count()
    if count > 2000:
        modeladmin.message_user(
            request,
            f"Możesz dodać maksymalnie 2000 rekordów do kolejki naraz. "
            f"Wybrano {count} {ngettext('rekord', 'rekordów', count)}.",
            messages.ERROR,
        )
        return

    # Get model info from queryset
    model = queryset.model
    app_label = model._meta.app_label
    model_name = model._meta.model_name

    # Collect record IDs
    record_ids = list(queryset.values_list("id", flat=True))

    # Queue the batch export in background
    queue_pbn_export_batch.delay(
        app_label=app_label,
        model_name=model_name,
        record_ids=record_ids,
        user_id=request.user.id,
    )

    modeladmin.message_user(
        request,
        f"Zakolejkowano {count} {ngettext('rekord', 'rekordów', count)} "
        f"do wysyłki do PBN. Proces przebiega w tle.",
        messages.SUCCESS,
    )


wyslij_do_pbn_w_tle.short_description = "Wyślij do PBN w tle"
