import reversion
from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ngettext

from bpp.admin.helpers.pbn_api.gui import (
    sprobuj_wyslac_do_pbn_gui,
)
from bpp.models import Status_Korekty, Uczelnia
from bpp.views.cache_publiczny import uniewaznij_cache_publiczny
from bpp.wersjonowanie import (
    sledzone_relacje,
    zapewnij_wersje_poczatkowe,
    zapisz_wersje_osobno,
)
from pbn_export_queue.tasks import queue_pbn_export_batch

#: Górna granica liczby rekordów WERSJONOWANYCH (reversion, np. autorów)
#: zmienianych jedną akcją masową. Wersje powstają hurtem, ale przy
#: „zaznacz wszystkie” na dużej bazie (dziesiątki tysięcy rekordów) samo
#: serializowanie wersji przekroczyłoby limit czasu żądania.
MAKS_REKORDOW_AKCJI_MASOWEJ = 2000

#: Górna granica dla publikacji (wersjonowane od FD#587). Wyższa niż dla
#: autorów, żeby dało się zmienić status korekty dużej części rocznika;
#: zmierzone ~4 ms na rekord z autorem (wersja „przed” + „po”).
MAKS_REKORDOW_AKCJI_MASOWEJ_PUBLIKACJI = 5000

#: Górna granica dla modeli bez wersji — dla nich
#: powstają tylko wpisy ``LogEntry`` (``bulk_create`` w partiach), więc
#: limit jest dużo wyższy; chroni tylko przed przekroczeniem czasu żądania.
MAKS_REKORDOW_AKCJI_MASOWEJ_BEZ_WERSJI = 20000

#: Rozmiar partii ``bulk_create`` wpisów ``LogEntry``.
PARTIA_LOGENTRY = 1000


def zapisuje_historie(akcja):
    """Oznacz akcję admina, która sama zapisuje wersje (reversion) i wpisy
    historii (``zmien_hurtowo_z_historia``).

    ``VersionAdmin.changelist_view`` owija każdą akcję w jedną rewizję;
    wtedy wersja „przed” i „po” scaliłyby się w jedną i zmiany nie dałoby
    się cofnąć. ``HistoriaWersjiMixin.create_revision`` nie otwiera rewizji
    dla tak oznaczonych akcji — akcja otwiera własne.
    """
    akcja.zapisuje_historie = True
    return akcja


def limit_akcji_masowej(model):
    """Limit rekordów jednej akcji masowej dla ``model``."""
    if not reversion.is_registered(model):
        return MAKS_REKORDOW_AKCJI_MASOWEJ_BEZ_WERSJI
    if any(f.name == "status_korekty" for f in model._meta.concrete_fields):
        return MAKS_REKORDOW_AKCJI_MASOWEJ_PUBLIKACJI
    return MAKS_REKORDOW_AKCJI_MASOWEJ


def _zapisz_logentry(user_id, model, obiekty, komentarz):
    """Wpisy ``LogEntry`` CHANGE dla ``obiekty`` — jak
    ``LogEntry.objects.log_actions``, ale ``bulk_create`` w partiach
    (przy dziesiątkach tysięcy rekordów jeden INSERT byłby za duży)."""
    content_type_id = ContentType.objects.get_for_model(
        model, for_concrete_model=False
    ).pk
    LogEntry.objects.bulk_create(
        [
            LogEntry(
                user_id=user_id,
                content_type_id=content_type_id,
                object_id=str(obiekt.pk),
                object_repr=str(obiekt)[:200],
                action_flag=CHANGE,
                change_message=komentarz,
            )
            for obiekt in obiekty
        ],
        batch_size=PARTIA_LOGENTRY,
    )


def zmien_hurtowo_z_historia(
    request,
    queryset,
    zmiany,
    komentarz,
    select_related=(),
    pola_repr=None,
    warunek_pod_blokada=None,
):
    """Ustaw ``zmiany`` (pole → wartość) w rekordach ``queryset`` jednym
    ``UPDATE`` i zostaw po tym ślad w „Historii” każdego zmienionego rekordu.

    Wspólna ścieżka wszystkich akcji masowych admina zmieniających dane
    hurtowym ``update()`` (który omija ``save()`` i sygnały):

    * zmieniane są tylko rekordy, w których coś się faktycznie zmieni
      (``exclude(**zmiany)`` = NOT wszystkie pola już mają te wartości);
      tylko one dostają wpisy w historii,
    * każdy zmieniony rekord dostaje wpis ``LogEntry`` (CHANGE) z
      komentarzem ``komentarz`` — widoczny na stronie „Historia”,
    * dla modeli zarejestrowanych w django-reversion (np. ``Autor``) także
      wersje: „przed” (jeśli rekord nie miał żadnej — ``zapewnij_wersje_
      poczatkowe``) i „po” — każdy rekord we własnej rewizji, więc cofnięcie
      jednego nie cofa pozostałych. Wołać POZA aktywną rewizją reversion:
      akcję admina trzeba oznaczyć ``@zapisuje_historie``,
    * publiczny cache jest unieważniany raz, po COMMIT.

    * pola ``auto_now`` (``ostatnio_zmieniony``), które ``update()`` pomija,
      dostają bieżący czas — synchronizacja przyrostowa przez API
      (``?ostatnio_zmieniony_after=``) widzi zmianę.

    ``warunek_pod_blokada`` — funkcja ``queryset → queryset`` zawężająca
    zmianę do rekordów spełniających warunek sprawdzany pod blokadą wierszy,
    w tej samej transakcji co ``UPDATE`` (patrz komentarz w kodzie).

    Liczba zapytań nie zależy od liczby rekordów (poza partiami INSERT
    ``LogEntry`` po ``PARTIA_LOGENTRY``). ``select_related`` — relacje
    potrzebne do ``__str__`` (``object_repr``). ``pola_repr`` — dla modeli
    bez wersji: jedyne pola potrzebne do ``__str__``; wtedy do
    ``object_repr`` nie ładuje się pełnych rekordów (przy dziesiątkach
    tysięcy publikacji to istotne).

    Zwraca liczbę zmienionych rekordów albo ``None``, gdy rekordów do
    zmiany jest więcej niż ``limit_akcji_masowej(model)`` (wtedy nic nie
    jest zmieniane).
    """
    model = queryset.model
    if hasattr(model, "deleted_objects"):
        # Rekord w koszu jest zamrożony (trigger ``bpp_kosz_straznik``
        # odrzuciłby UPDATE) — akcje masowe go pomijają.
        queryset = queryset.filter(deleted_at__isnull=True)
    pks = list(
        dict.fromkeys(
            queryset.exclude(**zmiany).order_by().values_list("pk", flat=True)
        )
    )
    if len(pks) > limit_akcji_masowej(model):
        return None
    if not pks:
        return 0

    wersjonowany = reversion.is_registered(model)
    with transaction.atomic():
        if warunek_pod_blokada is not None:
            # Warunek, który musi być prawdziwy W CHWILI zmiany (np. „pozycja
            # słownika jest nieużywana”). Blokujemy wiersze (``FOR UPDATE``)
            # i sprawdzamy warunek już pod blokadą: wstawienie rekordu
            # wskazującego na zablokowany wiersz czeka na nasz COMMIT
            # (klucz obcy bierze ``FOR KEY SHARE``), więc między
            # sprawdzeniem a ``UPDATE`` nic nie może zacząć go używać.
            zablokowane = list(
                model._default_manager.select_for_update()
                .filter(pk__in=pks)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            pks = list(
                warunek_pod_blokada(model._default_manager.filter(pk__in=zablokowane))
                .exclude(**zmiany)
                .order_by()
                .values_list("pk", flat=True)
            )
            if not pks:
                return 0
        follow = ()
        if wersjonowany:
            # Stan sprzed zmiany dla rekordów bez historii — żeby dało się
            # do niego wrócić z „Historii”.
            zapewnij_wersje_poczatkowe(model, pks, select_related=select_related)
            follow = sledzone_relacje(model)
        # ``update()`` nie ustawia pól ``auto_now``. Tylko w wartościach,
        # nie w ``exclude`` powyżej — inaczej każdy rekord byłby „zmieniony”.
        teraz = timezone.now()
        auto_now = {
            pole.name: teraz
            for pole in model._meta.concrete_fields
            if getattr(pole, "auto_now", False) and pole.name not in zmiany
        }
        updated = model._default_manager.filter(pk__in=pks).update(**zmiany, **auto_now)
        obiekty = model._default_manager.filter(pk__in=pks)
        if pola_repr is not None and not wersjonowany:
            # Wersje potrzebują pełnych rekordów; sam ``object_repr`` nie.
            obiekty = obiekty.only("pk", *pola_repr)
        obiekty = list(
            obiekty.select_related(*select_related).prefetch_related(*follow)
        )
        if wersjonowany:
            # Każdy rekord we WŁASNEJ rewizji (patrz ``zapisz_wersje_osobno``).
            zapisz_wersje_osobno(obiekty, user=request.user, komentarz=komentarz)
        _zapisz_logentry(request.user.pk, model, obiekty, komentarz)
        # ``update()`` nie wysyła ``post_save`` — bez jawnej inwalidacji
        # publiczne strony pokazywałyby stary stan do TTL. W bloku
        # ``atomic`` unieważnienie wykona się raz, po COMMIT.
        uniewaznij_cache_publiczny()
    return updated


def komunikat_limitu(modeladmin, request, model):
    modeladmin.message_user(
        request,
        f"Zaznaczono zbyt wiele rekordów do zmiany — jedną akcją można zmienić "
        f"najwyżej {limit_akcji_masowej(model)}. Zawęź listę filtrami "
        f"i powtórz akcję. Nic nie zostało zmienione.",
        messages.ERROR,
    )


def ustaw_status(request, queryset, nazwa_statusu):
    """Ustaw status korekty zaznaczonych publikacji (z wpisem w „Historii”).

    Status korekty decyduje o widoczności rekordu publicznie. Zwraca liczbę
    zmienionych rekordów albo ``None`` przy przekroczonym limicie."""
    status = Status_Korekty.objects.get(nazwa=nazwa_statusu)
    return zmien_hurtowo_z_historia(
        request,
        queryset,
        {"status_korekty": status},
        f"Ustawiono status korekty: {nazwa_statusu} (akcja masowa)",
        # ``Wydawnictwo_Baza.__str__`` → ``tytul_oryginalny``.
        pola_repr=("tytul_oryginalny",),
    )


def _akcja_ustaw_status(modeladmin, request, queryset, nazwa_statusu):
    updated = ustaw_status(request, queryset, nazwa_statusu)
    if updated is None:
        return komunikat_limitu(modeladmin, request, queryset.model)
    modeladmin.message_user(
        request,
        f"Ustawiono status '{nazwa_statusu}' dla {updated} "
        f"{ngettext('rekordu', 'rekordów', updated)}",
    )


@zapisuje_historie
def ustaw_przed_korekta(modeladmin, request, queryset):
    _akcja_ustaw_status(modeladmin, request, queryset, "przed korektą")


ustaw_przed_korekta.short_description = "Ustaw status korekty: przed korektą"
ustaw_przed_korekta.allowed_permissions = ("change",)


@zapisuje_historie
def ustaw_po_korekcie(modeladmin, request, queryset):
    _akcja_ustaw_status(modeladmin, request, queryset, "po korekcie")


ustaw_po_korekcie.short_description = "Ustaw status korekty: po korekcie"
ustaw_po_korekcie.allowed_permissions = ("change",)


@zapisuje_historie
def ustaw_w_trakcie_korekty(modeladmin, request, queryset):
    _akcja_ustaw_status(modeladmin, request, queryset, "w trakcie korekty")


ustaw_w_trakcie_korekty.short_description = "Ustaw status korekty: w trakcie korekty"
ustaw_w_trakcie_korekty.allowed_permissions = ("change",)


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


KOMUNIKAT_POKAZANO_JEDNOSTKI_RANKING = (
    "Pokazano na stronach jednostek i w rankingu (akcja masowa)"
)
KOMUNIKAT_UKRYTO_JEDNOSTKI_RANKING = (
    "Ukryto na stronach jednostek i w rankingu (akcja masowa)"
)


def _ustaw_widocznosc_jednostki_ranking(modeladmin, request, queryset, widoczny):
    # „Widoczność” w sensie dawnego ``pokazuj``: strona jednostki + ranking.
    updated = zmien_hurtowo_z_historia(
        request,
        queryset,
        {"pokazuj_na_stronie_jednostki": widoczny, "pokazuj_w_rankingu": widoczny},
        KOMUNIKAT_POKAZANO_JEDNOSTKI_RANKING
        if widoczny
        else KOMUNIKAT_UKRYTO_JEDNOSTKI_RANKING,
        select_related=("tytul",),  # ``Autor.__str__``
    )
    if updated is None:
        return komunikat_limitu(modeladmin, request, queryset.model)
    stan = "widocznych" if widoczny else "ukrytych"
    modeladmin.message_user(
        request,
        f"Ustawiono {updated} {ngettext('autora', 'autorów', updated)} jako {stan}",
    )


@zapisuje_historie
def ustaw_pokazuj_true(modeladmin, request, queryset):
    _ustaw_widocznosc_jednostki_ranking(modeladmin, request, queryset, True)


ustaw_pokazuj_true.short_description = (
    "Pokaż wybranych autorów na stronach jednostek i w rankingu"
)
ustaw_pokazuj_true.allowed_permissions = ("change",)


@zapisuje_historie
def ustaw_pokazuj_false(modeladmin, request, queryset):
    _ustaw_widocznosc_jednostki_ranking(modeladmin, request, queryset, False)


ustaw_pokazuj_false.short_description = (
    "Ukryj wybranych autorów na stronach jednostek i w rankingu"
)
ustaw_pokazuj_false.allowed_permissions = ("change",)


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
    kierunkach. Historia, limit i cache — patrz ``zmien_hurtowo_z_historia``.
    """
    return zmien_hurtowo_z_historia(
        request,
        queryset,
        dict.fromkeys(POLA_WIDOCZNOSCI_AUTORA, widoczny),
        komentarz,
        select_related=("tytul",),  # ``Autor.__str__``
    )


@zapisuje_historie
def ukryj_autorow_wszedzie(modeladmin, request, queryset):
    updated = _ustaw_widocznosc_wszedzie(
        request, queryset, False, KOMUNIKAT_UKRYTO_WSZEDZIE
    )
    if updated is None:
        return komunikat_limitu(modeladmin, request, queryset.model)
    modeladmin.message_user(
        request,
        f"Ukryto wszędzie {updated} {ngettext('autora', 'autorów', updated)}",
    )


ukryj_autorow_wszedzie.short_description = (
    "Ukryj wybranych autorów wszędzie (strony jednostek, ranking, "
    "wyszukiwanie, indeks, API, strona autora)"
)
ukryj_autorow_wszedzie.allowed_permissions = ("change",)


@zapisuje_historie
def pokaz_autorow_wszedzie(modeladmin, request, queryset):
    updated = _ustaw_widocznosc_wszedzie(
        request, queryset, True, KOMUNIKAT_POKAZANO_WSZEDZIE
    )
    if updated is None:
        return komunikat_limitu(modeladmin, request, queryset.model)
    modeladmin.message_user(
        request,
        f"Pokazano wszędzie {updated} {ngettext('autora', 'autorów', updated)}",
    )


pokaz_autorow_wszedzie.short_description = (
    "Pokaż wybranych autorów wszędzie (strony jednostek, ranking, "
    "wyszukiwanie, indeks, API, strona autora)"
)
pokaz_autorow_wszedzie.allowed_permissions = ("change",)
