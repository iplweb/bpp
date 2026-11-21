import reversion
from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ngettext

from bpp.admin.helpers.pbn_api.gui import (
    sprobuj_wyslac_do_pbn_gui,
)
from bpp.models import Autor, Status_Korekty, Uczelnia
from bpp.views.cache_publiczny import uniewaznij_cache_publiczny
from bpp.wersjonowanie import zapewnij_wersje_poczatkowa
from pbn_export_queue.tasks import queue_pbn_export_batch


def ustaw_status(queryset, nazwa_statusu):
    status = Status_Korekty.objects.get(nazwa=nazwa_statusu)
    updated = queryset.exclude(status_korekty=status).update(status_korekty=status)
    # ``update()`` nie wysyła ``post_save`` — status korekty decyduje
    # o widoczności rekordu publicznie, więc cache stron musi się odświeżyć.
    uniewaznij_cache_publiczny()
    return updated


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

    # Multi-hosted: zapamiętaj uczelnię z requestu, żeby wysyłka w tle
    # użyła właściwej konfiguracji PBN (a nie pierwszej-z-brzegu).
    uczelnia = Uczelnia.objects.get_for_request(request)

    # Queue the batch export in background
    queue_pbn_export_batch.delay(
        app_label=app_label,
        model_name=model_name,
        record_ids=record_ids,
        user_id=request.user.id,
        uczelnia_id=uczelnia.pk if uczelnia else None,
    )

    modeladmin.message_user(
        request,
        f"Zakolejkowano {count} {ngettext('rekord', 'rekordów', count)} "
        f"do wysyłki do PBN. Proces przebiega w tle.",
        messages.SUCCESS,
    )


wyslij_do_pbn_w_tle.short_description = "Wyślij do PBN w tle"


def ustaw_pokazuj_true(modeladmin, request, queryset):
    # „Widoczność” w sensie dawnego ``pokazuj``: strona jednostki + ranking.
    updated = queryset.filter(
        Q(pokazuj_na_stronie_jednostki=False) | Q(pokazuj_w_rankingu=False)
    ).update(pokazuj_na_stronie_jednostki=True, pokazuj_w_rankingu=True)
    # ``update()`` nie wysyła ``post_save`` — bez jawnej inwalidacji
    # publiczne strony (jednostki, indeks) pokazywałyby stary stan do TTL.
    uniewaznij_cache_publiczny()
    modeladmin.message_user(
        request,
        f"Ustawiono {updated} {ngettext('autora', 'autorów', updated)} jako widocznych",
    )


ustaw_pokazuj_true.short_description = (
    "Pokaż wybranych autorów na stronach jednostek i w rankingu"
)


def ustaw_pokazuj_false(modeladmin, request, queryset):
    updated = queryset.filter(
        Q(pokazuj_na_stronie_jednostki=True) | Q(pokazuj_w_rankingu=True)
    ).update(pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False)
    # Patrz ``ustaw_pokazuj_true``: ``update()`` omija sygnały.
    uniewaznij_cache_publiczny()
    modeladmin.message_user(
        request,
        f"Ustawiono {updated} {ngettext('autora', 'autorów', updated)} jako ukrytych",
    )


ustaw_pokazuj_false.short_description = (
    "Ukryj wybranych autorów na stronach jednostek i w rankingu"
)


#: Flagi publicznej widoczności autora przełączane akcjami „… wszędzie”.
#: ``pokazuj_siec_powiazan`` celowo pominięte: sieć powiązań i tak nie jest
#: dostępna dla autora ze schowaną stroną, a „pokaż wszędzie” nie powinno
#: nadpisywać ustawienia uczelni (pole jest trójstanowe).
POLA_WIDOCZNOSCI_AUTORA = (
    "pokazuj_na_stronie_jednostki",
    "pokazuj_w_rankingu",
    "pokazuj_w_wyszukiwaniu",
    "pokazuj_w_indeksie",
    "pokazuj_w_api",
    "pokazuj_strone_autora",
)

KOMUNIKAT_UKRYTO_WSZEDZIE = "Ukryto wszędzie (akcja masowa)"
KOMUNIKAT_POKAZANO_WSZEDZIE = "Pokazano wszędzie (akcja masowa)"


def _ustaw_widocznosc_wszedzie(request, queryset, widoczny, komentarz):
    """Ustaw wszystkie flagi publicznej widoczności autorów na ``widoczny``.

    Jeden ``UPDATE`` ustawia wszystkie flagi naraz, więc constraint
    ``bpp_autor_strona_schowana_wymaga_ukrycia`` (schowana strona autora
    wymaga wyłączenia wyszukiwania i indeksu) jest spełniony w obu
    kierunkach. Każdy zmieniony autor dostaje wersję w historii (reversion)
    i wpis ``LogEntry`` — to akcja „hurtowa”, którą trzeba móc prześledzić
    i cofnąć. Zwraca liczbę zmienionych autorów.
    """
    wartosci = dict.fromkeys(POLA_WIDOCZNOSCI_AUTORA, widoczny)
    # ``exclude(**wartosci)`` = NOT (wszystkie flagi już mają tę wartość).
    pks = list(queryset.exclude(**wartosci).values_list("pk", flat=True))
    if not pks:
        return 0

    for autor in Autor.objects.filter(pk__in=pks):
        # Rekordy bez historii: zapisz stan sprzed zmiany, żeby dało się
        # do niego wrócić z „Historii” autora.
        zapewnij_wersje_poczatkowa(autor)

    with transaction.atomic(), reversion.create_revision():
        updated = Autor.objects.filter(pk__in=pks).update(**wartosci)
        autorzy = list(Autor.objects.filter(pk__in=pks))
        for autor in autorzy:
            reversion.add_to_revision(autor)
        reversion.set_user(request.user)
        reversion.set_comment(komentarz)
        LogEntry.objects.log_actions(
            request.user.pk, autorzy, CHANGE, change_message=komentarz
        )
        # ``update()`` nie wysyła ``post_save``; w bloku ``atomic``
        # unieważnienie wykona się raz, po COMMIT.
        uniewaznij_cache_publiczny()
    return updated


def ukryj_autorow_wszedzie(modeladmin, request, queryset):
    updated = _ustaw_widocznosc_wszedzie(
        request, queryset, False, KOMUNIKAT_UKRYTO_WSZEDZIE
    )
    modeladmin.message_user(
        request,
        f"Ukryto wszędzie {updated} {ngettext('autora', 'autorów', updated)}",
    )


ukryj_autorow_wszedzie.short_description = (
    "Ukryj wybranych autorów wszędzie (strony jednostek, ranking, "
    "wyszukiwanie, indeks, API, strona autora)"
)
ukryj_autorow_wszedzie.allowed_permissions = ("change",)


def pokaz_autorow_wszedzie(modeladmin, request, queryset):
    updated = _ustaw_widocznosc_wszedzie(
        request, queryset, True, KOMUNIKAT_POKAZANO_WSZEDZIE
    )
    modeladmin.message_user(
        request,
        f"Pokazano wszędzie {updated} {ngettext('autora', 'autorów', updated)}",
    )


pokaz_autorow_wszedzie.short_description = (
    "Pokaż wybranych autorów wszędzie (strony jednostek, ranking, "
    "wyszukiwanie, indeks, API, strona autora)"
)
pokaz_autorow_wszedzie.allowed_permissions = ("change",)
