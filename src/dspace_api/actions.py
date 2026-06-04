from collections import Counter

from django.contrib import messages
from django.utils.translation import ngettext

from dspace_api.eksport import eksportuj_rekord
from dspace_api.tasks import queue_dspace_export_batch


def wyslij_do_dspace(modeladmin, request, queryset):
    count = queryset.count()
    if count > 10:
        modeladmin.message_user(
            request,
            f"Możesz wysłać maksymalnie 10 rekordów naraz. Wybrano {count}.",
            messages.ERROR,
        )
        return

    licznik = Counter()
    powody = []
    for rec in queryset:
        for w in eksportuj_rekord(rec):
            licznik[w["status"]] += 1
            if w["status"] in ("pominieto", "blad"):
                powody.append(f"{rec} → {w['uczelnia']}: {w['powod']}")

    podsumowanie = ", ".join(f"{k}: {v}" for k, v in licznik.items())
    modeladmin.message_user(request, f"DSpace — {podsumowanie}", messages.SUCCESS)
    if powody:
        modeladmin.message_user(
            request,
            "Pominięcia/błędy:\n" + "\n".join(powody),
            messages.WARNING,
        )


wyslij_do_dspace.short_description = "Wyślij do DSpace"


def wyslij_do_dspace_w_tle(modeladmin, request, queryset):
    count = queryset.count()
    if count > 2000:
        modeladmin.message_user(
            request,
            f"Możesz zakolejkować maksymalnie 2000 rekordów. Wybrano {count}.",
            messages.ERROR,
        )
        return

    model = queryset.model
    queue_dspace_export_batch.delay(
        app_label=model._meta.app_label,
        model_name=model._meta.model_name,
        record_ids=list(queryset.values_list("id", flat=True)),
        user_id=request.user.id,
    )
    modeladmin.message_user(
        request,
        f"Zakolejkowano {count} {ngettext('rekord', 'rekordów', count)} "
        f"do wysyłki do DSpace (w tle).",
        messages.SUCCESS,
    )


wyslij_do_dspace_w_tle.short_description = "Wyślij do DSpace w tle"
