from contextlib import contextmanager

import denorm
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers as admin_helpers
from django.contrib.admin.options import TO_FIELD_VAR
from django.contrib.admin.utils import unquote
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import router, transaction
from django.db.models import ProtectedError
from django.template.response import TemplateResponse
from django.urls import reverse
from django_softdelete.filters import SoftDeleteFilter

from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.system import Status_Korekty


class ZapiszZAdnotacjaMixin:
    readonly_fields = ("ostatnio_zmieniony",)


class AdnotacjeZDatamiMixin:
    readonly_fields = ("utworzono", "ostatnio_zmieniony", "id")


class AdnotacjeZDatamiOrazPBNMixin:
    readonly_fields = (
        "utworzono",
        "ostatnio_zmieniony",
        "id",
        "pbn_id",
    )


class DomyslnyStatusKorektyMixin:
    status_korekty = forms.ModelChoiceField(
        required=True,
        queryset=Status_Korekty.objects.all(),
        initial=lambda: Status_Korekty.objects.first(),
    )


class Wycinaj_W_z_InformacjiMixin:
    def clean_informacje(self):
        i = self.cleaned_data.get("informacje")
        if i:
            x = i.lower()
            n = 0
            if x.startswith("w:"):
                n = 2
            if x.startswith("w :"):
                n = 3
            if n:
                return i[n:].strip()
        return i


class OptionalPBNSaveMixin:
    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        from bpp.models import Uczelnia

        # „Zapisz i wyślij do PBN" ma sens tylko, gdy formularz da się zapisać.
        # Rekord z kosza (albo widok tylko do odczytu) nie ma przycisku „Zapisz",
        # więc nie może też mieć przycisków wysyłki do PBN.
        moze_zapisac = (
            self.has_add_permission(request)
            if add
            else self.has_change_permission(request, obj)
        )
        uczelnia = Uczelnia.objects.get_for_request(request) if moze_zapisac else None
        if uczelnia is not None:
            if uczelnia.pbn_integracja and uczelnia.pbn_aktualizuj_na_biezaco:
                context.update({"show_save_and_pbn": True})

        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_post_save_change(self, request, obj):
        from .pbn_api.gui import (
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
            sprobuj_wyslac_do_pbn_gui,
        )

        if "_continue_and_pbn" in request.POST:
            sprobuj_wyslac_do_pbn_gui(request, obj)

        elif "_continue_and_pbn_later" in request.POST:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request, obj)

        else:
            # Otherwise, use default behavior
            return super().response_post_save_change(request, obj)

        # Przekieruj użytkownika na formularz zmian
        opts = self.model._meta
        route = f"admin:{opts.app_label}_{opts.model_name}_change"

        post_url = reverse(route, args=(obj.pk,))

        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(post_url)


#: Wyjaśnienie przy wyszarzonym przycisku „Usuń" (FD#539).
POWOD_BLOKADY_USUWANIA_PBN = (
    "Rekordu nie można usunąć, bo ma odpowiednik w PBN (PBN UID). PBN nie "
    "pozwala kasować prac z repozytorium — jeżeli rekord ma zniknąć, usuń go "
    "najpierw ręcznie po stronie PBN, a potem odepnij PBN UID w tym "
    "formularzu."
)


class RestrictDeletionWhenPBNUIDSetMixin:
    """Rekord z PBN UID nie jest usuwalny (ani do kosza, ani trwale).

    FD#539: zamiast znikać, przycisk „Usuń" na formularzu jest WYSZARZONY
    z wyjaśnieniem (``usun_zablokowany_powod`` w ``admin/submit_line.html``).
    Docelowo (poza zakresem): kolejka usuwania z PBN — wycofanie rekordu
    z profilu instytucji — która pozwoli kasować także takie rekordy.
    """

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            if obj.pbn_uid_id is not None:
                return False
        return super().has_delete_permission(request, obj)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        if (
            obj is not None
            and obj.pbn_uid_id is not None
            and getattr(obj, "deleted_at", None) is None
        ):
            context["usun_zablokowany_powod"] = POWOD_BLOKADY_USUWANIA_PBN
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )


class BlokujRekordPrzedZapisemMixin:
    """Przy edycji (POST na change view) blokuje wiersz rekordu
    (``SELECT ... FOR UPDATE``) jako PIERWSZE zapytanie w transakcji admina.

    Po co: zapis rekordu z denormem ``cached_punkty_dyscyplin`` liczy
    ``pre_save`` PRZED ``UPDATE`` -- czyli najpierw DELETE/INSERT
    w ``bpp_cache_punktacja_*``, dopiero potem blokada wiersza rodzica.
    Flush denorm (celery) robi odwrotnie: ``select_for_update(skip_locked)``
    na rodzicu, potem te same wiersze cache. Odwrotna kolejność blokad
    = deadlock (ABBA, Rollbar #5363). Blokując rodzica na samym początku
    ``_changeform_view`` (Django otwiera ``transaction.atomic`` w
    ``changeform_view`` dla POST-a, więc jesteśmy już w transakcji),
    obie ścieżki mają kolejność rodzic -> cache: flush albo pominie rekord
    (``skip_locked``), albo admin poczeka, aż flush skończy.

    Celowo BEZ retry na deadlock -- ma być widoczny, jeśli wróci.

    ``select_for_update`` ustawia ``_for_write``, więc cacheops nie
    obsługuje tego zapytania z cache (``_should_cache`` -> False).
    """

    def _zablokuj_rekord_do_edycji(self, request, object_id):
        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        opts = self.model._meta
        try:
            field = opts.get_field(to_field) if to_field else opts.pk
        except FieldDoesNotExist:
            return  # Django sam odrzuci niedozwolony to_field
        try:
            value = field.to_python(unquote(object_id))
        except (ValidationError, ValueError):
            return  # śmieciowe id -- Django zwróci standardowy redirect/404
        list(
            self.model._base_manager.select_for_update(of=("self",))
            .filter(**{field.name: value})
            .values_list("pk", flat=True)
        )

    def _changeform_view(self, request, object_id, form_url, extra_context):
        if (
            request.method == "POST"
            and object_id is not None
            and "_saveasnew" not in request.POST
        ):
            self._zablokuj_rekord_do_edycji(request, object_id)
        return super()._changeform_view(request, object_id, form_url, extra_context)


class OdroczPunktyDyscyplinMixin:
    """Zapis z admina NIE liczy ``cached_punkty_dyscyplin`` w ``pre_save``.

    Admin zapisuje rodzica (``save_model``) PRZED inline'ami autorów
    (``save_related``), więc ``@denormalized cached_punkty_dyscyplin``
    liczony w ``pre_save`` szedł na STARYCH autorach -- i jeszcze przed
    ``UPDATE`` rodzica kasował/wstawiał wiersze ``bpp_cache_punktacja_*``
    (kolejność blokad odwrotna do flusha denorm, Rollbar #5363). Ta praca
    była zbędna: ``BaseBppAdminMixin.save_related`` po zapisie inline'ów
    i tak przebudowuje tabele cache, a kolumnę JSON przelicza flush denorm.

    ``denorm.deferred()`` (django-denorm-iplweb >= 1.15.0) sprawia, że przy
    UPDATE kolumna zostaje bez zmian (``col = col``), przy INSERT dostaje
    default (``None``), a na wyjściu z bloku powstaje marker
    ``DirtyInstance`` -- flush policzy JSON raz, na danych po zapisie.

    Zewnętrzne ``atomic`` jest konieczne: ``changeform_view`` Django sam
    otwiera i COMMITUJE swoje ``atomic``, więc bez niego markery
    zapisałyby się już po commicie, poza transakcją z danymi. Wewnątrz
    atomic Django staje się savepointem; blokada rekordu z
    ``BlokujRekordPrzedZapisemMixin`` nadal idzie przed zapisem cache.

    Uwaga: w obrębie requestu ``obj.cached_punkty_dyscyplin`` jest
    nieaktualne (do flusha) -- nic w ścieżce zapisu admina go nie czyta.
    """

    odroczone_pole_denorm = "cached_punkty_dyscyplin"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST":
            return super().changeform_view(request, object_id, form_url, extra_context)

        with (
            transaction.atomic(using=router.db_for_write(self.model)),
            denorm.deferred(f"{self.model._meta.label}.{self.odroczone_pole_denorm}"),
        ):
            return super().changeform_view(request, object_id, form_url, extra_context)


class PokazSkasowaneFilter(SoftDeleteFilter):
    """Filtr „kosz" dla changelisty modeli soft-delete.

    RÓŻNICA WOBEC PAKIETU JEST JEDNA: brak parametru w URL-u znaczy tutaj
    „tylko żywe", a nie „wszystko". Pakietowy ``SoftDeleteFilter`` mapuje
    ``self.value() or 'all'`` na ``'ALL'`` i zwraca cały queryset, więc
    wejście na gołą changelistę pokazywałoby kosz wymieszany z żywymi
    rekordami. Skoro ``get_queryset`` mixinu podaje ``global_objects``,
    to ten filtr jest JEDYNYM miejscem, które chowa kosz — bez tej zmiany
    nie schowałby go nikt.

    SEMANTYKA WARTOŚCI ZOSTAJE PAKIETOWA, celowo: ``is_deleted=true`` to
    rekordy skasowane (pakiet mapuje ``'true'`` na
    ``deleted_at__isnull=False``). Parametr w URL-u czyta się więc wprost
    i da się go bezpiecznie zabookmarkować.
    """

    title = "♻️ Kosz"

    def lookups(self, request, model_admin):
        return (
            ("true", "🗑️ Tylko skasowane"),
            ("all", "Wszystkie (żywe + kosz)"),
        )

    def choices(self, changelist):
        """Pierwsza pozycja to stan domyślny — a ten NIE znaczy „wszystkie".

        Odziedziczona etykieta „All" opisywałaby dokładnie odwrotność tego,
        co filtr robi bez parametru.
        """
        wybory = super().choices(changelist)
        domyslny = next(iter(wybory))
        domyslny["display"] = "Bez kosza (tylko żywe)"
        yield domyslny
        yield from wybory

    def queryset(self, request, queryset):
        wartosc = self.value()
        if wartosc == "all":
            return queryset
        if wartosc == "true":
            return queryset.filter(deleted_at__isnull=False)
        return queryset.filter(deleted_at__isnull=True)


class BppSoftDeleteAdminMixin:
    """Kosz w adminie dla modeli soft-delete (publikacje, ``Autor``,
    struktura uczelni, słowniki).

    Daje: changelistę nad ``global_objects`` z filtrem kosza, akcje
    „przywróć" / „usuń do kosza (z powodem)", stronę potwierdzenia
    kasowania z informacją o PBN i pytaniem o aktywne zlecenie wysyłki,
    rekord z kosza tylko do odczytu, tłumaczenie błędu blokady kosza z bazy
    (``BPP_KOSZ:``) na komunikat oraz JEDEN punkt wstrzyknięcia
    ``request.user``. Trwałe usuwanie z kosza jest wyłączone.

    UPRAWNIENIA: kosz = ``delete``; przywracanie = ``delete`` + ``change``. Akcje są dokładane do listy tylko, gdy
    user ma uprawnienie, a każda akcja dodatkowo sprawdza
    ``has_delete_permission(request, obj)`` PER REKORD (np. FD#539: rekord
    z PBN UID nie trafi do kosza także akcją masową).

    ⚠️ MIEJSCE W LIŚCIE BAZ: **OSTATNIE**, tuż przed terminalnym
    ``admin.ModelAdmin`` (albo przed konkretną klasą bazową admina).
    ``get_queryset`` poniżej nie woła ``super()`` (musi podmienić menedżer
    bazowy na ``global_objects``), więc postawiony na początku MRO uciąłby
    cały łańcuch — w tym ``SiteFilteredAdminMixin.get_queryset``, które
    zawęża widok nie-superusera do jego uczelni (FD#390). Strażnik:
    ``test_admin.py::test_staff_widzi_tylko_autorow_swojej_uczelni``.
    """

    delete_confirmation_template = "admin/bpp/kosz_delete_confirmation.html"

    def get_queryset(self, request):
        """Podstawa łańcucha: ``global_objects`` (żywe + kosz).

        Skasowanego rekordu nie da się inaczej ani otworzyć, ani
        przywrócić. Kosz chowa dopiero ``PokazSkasowaneFilter``.
        """
        qs = self.model.global_objects.get_queryset()
        if getattr(request.resolver_match, "url_name", None) == "autocomplete":
            # Autocomplete admina (``AutocompleteJsonView`` pyta admina
            # modelu docelowego) nie podsuwa rekordów z kosza.
            qs = qs.filter(deleted_at__isnull=True)
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_filter(self, request):
        """Filtr kosza zawsze OSTATNI w panelu filtrów (decyzja właściciela)
        — także gdy admin ma własne ``list_filter`` z tym filtrem."""
        list_filter = [
            f
            for f in (super().get_list_filter(request) or [])
            if f is not PokazSkasowaneFilter
        ]
        list_filter.append(PokazSkasowaneFilter)
        return list_filter

    # --- blokada kosza z bazy → komunikat zamiast 500 ---------------------

    def _z_obsluga_bledu_kosza(self, request, widok, *args, **kwargs):
        from django.db import DatabaseError
        from django.http import HttpResponseRedirect

        from bpp.models.soft_delete import jest_bledem_kosza

        try:
            return widok(request, *args, **kwargs)
        except DatabaseError as e:
            if not jest_bledem_kosza(e):
                raise
            self.message_user(
                request,
                "Operacja odrzucona: rekord jest w koszu (zamrożony) — najpierw "
                "go przywróć. " + str(e).split("BPP_KOSZ:", 1)[1].split("\n")[0],
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.get_full_path())

    def changeform_view(self, request, *args, **kwargs):
        return self._z_obsluga_bledu_kosza(
            request, super().changeform_view, *args, **kwargs
        )

    def changelist_view(self, request, *args, **kwargs):
        return self._z_obsluga_bledu_kosza(
            request, super().changelist_view, *args, **kwargs
        )

    # --- rekord w koszu: tylko do odczytu --------------------------------

    def has_change_permission(self, request, obj=None):
        """Rekordu z kosza nie edytujemy — najpierw „Przywróć".

        Edycja rekordu w koszu ominęłaby przepływ przywracania (punktacja,
        PBN, ``SoftDeleteLog``), a inline'y dzieci i tak są puste (domyślny
        menedżer ``*_Autor`` ukrywa wiersze publikacji z kosza).
        """
        if obj is not None and getattr(obj, "deleted_at", None) is not None:
            return False
        return super().has_change_permission(request, obj)

    def get_view_on_site_url(self, obj=None):
        """Rekord z kosza nie ma „Pokaż na stronie" — strona publiczna daje
        dla niego 404."""
        if obj is not None and getattr(obj, "deleted_at", None) is not None:
            return None
        return super().get_view_on_site_url(obj)

    def has_delete_permission(self, request, obj=None):
        """Rekord już w koszu nie ma przycisku „Usuń" (opróżnianie kosza to
        osobna akcja superusera)."""
        if obj is not None and getattr(obj, "deleted_at", None) is not None:
            return False
        return super().has_delete_permission(request, obj)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        if obj is not None and getattr(obj, "deleted_at", None) is not None:
            context["rekord_w_koszu"] = obj
            if self.moze_przywracac(request):
                context["kosz_przywroc_url"] = reverse(
                    f"admin:{self._nazwa_url_przywroc()}", args=[obj.pk]
                )
            self.message_user(
                request,
                f"🗑️ Rekord jest w koszu (od {obj.deleted_at:%Y-%m-%d %H:%M}). "
                + (
                    "Aby go edytować, przywróć go przyciskiem „♻️ Przywróć” "
                    "na dole strony."
                    if "kosz_przywroc_url" in context
                    else "Aby go edytować, przywróć go akcją „♻️ Przywróć "
                    "zaznaczone” na liście z filtrem „Kosz → 🗑️ Tylko "
                    "skasowane”."
                ),
                level=messages.WARNING,
            )
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )

    # --- jeden punkt wstrzykniecia usera --------------------------------

    @contextmanager
    def _soft_delete_user_context(self, request):
        """JEDEN punkt wstrzyknięcia ``request.user`` (i powodu) dla całego
        przepływu kosza w adminie. Deleguje do ``soft_delete_context`` —
        thread-locala czytają receivery (``SoftDeleteLog``, reversion).
        ``hard_delete()`` nie przyjmuje ``user=``, więc atrybucja trwałego
        usunięcia ma tylko ten kanał."""
        with soft_delete_context(
            user=request.user, reason=self._powod_z_requestu(request)
        ):
            yield

    def _powod_z_requestu(self, request):
        if request.method != "POST":
            return ""
        return request.POST.get("powod", "")

    # --- PBN a kosz -----------------------------------------------------

    def stan_pbn_przed_koszem(self, obj):
        """Co kosz zrobi z PBN — do strony potwierdzenia (bez efektów
        ubocznych). ``wycofanie``: rekord ma odpowiednik w PBN, więc
        receiver zleci wycofanie oświadczeń instytucji. ``blokada``:
        komunikat, gdy rekord ma niezakończony wpis kolejki PBN."""
        from bpp.models.soft_delete import BppPublikacjaSoftDeleteMixin
        from pbn_export_queue.operacje import (
            KOMUNIKAT_REKORD_W_KOLEJCE,
            aktywny_wpis,
        )

        stan = {"wycofanie": False, "blokada": None}
        if not isinstance(obj, BppPublikacjaSoftDeleteMixin):
            return stan
        stan["wycofanie"] = bool(getattr(obj, "pbn_uid_id", None))
        if aktywny_wpis(obj) is not None:
            stan["blokada"] = KOMUNIKAT_REKORD_W_KOLEJCE
        return stan

    def blokada_kosza(self, obj):
        """Komunikat, dlaczego rekord NIE może trafić do kosza, albo ``None``
        (guard modelu albo kolejka PBN)."""
        return self.blokada_kosza_szczegoly(obj)[0]

    def blokada_kosza_szczegoly(self, obj):
        """``(komunikat, grupy)`` — dlaczego rekord NIE może trafić do kosza
        i KTÓRE rekordy go blokują (``GrupaBlokady`` per relacja; guard
        modelu albo kolejka PBN). ``(None, [])``, gdy nic nie blokuje."""
        from pbn_export_queue.operacje import grupa_blokady_kolejki

        try:
            obj.sprawdz_czy_mozna_do_kosza()
        except ProtectedError as e:
            return e.args[0], list(getattr(e, "grupy", []))
        komunikat = self.stan_pbn_przed_koszem(obj)["blokada"]
        if komunikat is None:
            return None, []
        grupa = grupa_blokady_kolejki(obj)
        return komunikat, [grupa] if grupa is not None else []

    # --- kasowanie = kosz -----------------------------------------------

    def get_deleted_objects(self, objs, request):
        """Kosz NIE kaskaduje — strona potwierdzenia (i ``delete_selected``)
        pokazuje same rekordy, a nie drzewo kolektora Django.

        Kolektor wyliczałby twardą kaskadę (np. punktację źródła), której
        nie ma, i żądał uprawnień do kasowania modeli, których nikt nie
        rusza. Guardy kosza (``sprawdz_czy_mozna_do_kosza``) i tak
        sprawdzamy osobno.
        """
        objs = list(objs)
        return (
            [str(o) for o in objs],
            {str(self.model._meta.verbose_name_plural): len(objs)},
            set(),
            [],
        )

    def _soft_delete_jeden(self, request, obj, powod):
        """Soft-delete jednego rekordu; ``False`` gdy nie wolno/zablokowano.

        Per instancja: jeden zablokowany rekord nie przewraca całego
        zaznaczenia. Uprawnienie sprawdzane PER REKORD (FD#539 itd.).
        """
        from bpp.models.soft_delete import NiedozwolonaZmianaKosza
        from pbn_export_queue.operacje import RekordWKolejcePBN

        if getattr(obj, "deleted_at", None) is not None:
            self.message_user(
                request, f"Pominięto „{obj}” — jest już w koszu.", messages.WARNING
            )
            return False
        if not self.has_delete_permission(request, obj):
            self.message_user(
                request,
                f"Pominięto „{obj}” — brak uprawnień do usunięcia tego rekordu"
                f"{self._dlaczego_nie_mozna_usunac(obj)}.",
                level=messages.ERROR,
            )
            return False
        try:
            obj.delete(user=request.user, reason=powod)
            return True
        except (ProtectedError, RekordWKolejcePBN, NiedozwolonaZmianaKosza) as e:
            self.message_user(request, e.args[0], level=messages.ERROR)
            return False

    def _dlaczego_nie_mozna_usunac(self, obj):
        if getattr(obj, "pbn_uid_id", None):
            return " (ma odpowiednik w PBN — patrz przycisk „Usuń” na rekordzie)"
        return ""

    def delete_view(self, request, object_id, extra_context=None):
        """„Usuń" na rekordzie = kosz, ze stroną potwierdzenia, która:

        - pokazuje, że rekord zostanie WYCOFANY z PBN (gdy ma odpowiednik),
        - odmawia od razu, gdy guard blokuje (autor z żywymi pracami,
          książka z żywymi rozdziałami, używany słownik) albo rekord jest
          w kolejce PBN,
        - uprzedza o powiązaniach od rekordów Z KOSZA (np. prace autora
          w koszu): nie blokują, ale ich przywrócenie będzie wymagało
          najpierw przywrócenia tego rekordu.
        """
        obj = self.get_object(request, unquote(object_id))
        if obj is not None and self.has_delete_permission(request, obj):
            blokada, grupy = self.blokada_kosza_szczegoly(obj)
            powiazania = getattr(obj, "powiazania_w_koszu", None)
            powiazania = powiazania() if powiazania is not None else []
            extra_context = {
                **(extra_context or {}),
                "kosz_blokada": blokada,
                "kosz_blokada_grupy": grupy,
                "kosz_blokada_w_koszu": sum(g.w_koszu for g in grupy),
                "kosz_powiazania_w_koszu": powiazania,
                "kosz_powiazania_w_koszu_liczba": sum(g.liczba for g in powiazania),
                "title": "Usuń do kosza",
                "kosz_pbn": self.stan_pbn_przed_koszem(obj),
            }
            if request.method == "POST" and blokada:
                # POST bez spełnionych warunków (np. ręcznie spreparowany)
                # — nie wołamy super(), żeby Django nie zameldowało
                # „usunięto pomyślnie".
                return self.render_delete_form(
                    request,
                    {
                        **self.admin_site.each_context(request),
                        "object": obj,
                        "opts": self.model._meta,
                        "object_name": str(self.model._meta.verbose_name),
                        "title": "Usuń do kosza",
                        **extra_context,
                    },
                )
        return super().delete_view(request, object_id, extra_context)

    def log_deletion(self, request, obj, object_repr):
        """Brak wpisu DELETION — rekord nie został usunięty, tylko trafił do
        kosza; ślad („Przeniesiono do kosza") zapisuje receiver kosza
        (rewizja reversion albo ``LogEntry`` CHANGE)."""
        return None

    def log_deletions(self, request, queryset):
        """Jak ``log_deletion`` (Django >= 5.1 woła wersję zbiorczą)."""
        return None

    def delete_model(self, request, obj):
        """Przycisk „Usuń" na changeformie przenosi do kosza (z userem
        i powodem ze strony potwierdzenia)."""
        with self._soft_delete_user_context(request):
            self._soft_delete_jeden(request, obj, self._powod_z_requestu(request))

    def delete_queryset(self, request, queryset):
        """Akcja ``delete_selected`` — kosz PER INSTANCJA (nigdy zbiorczo);
        rekordy zablokowane (np. w kolejce PBN) zostają z komunikatem."""
        with self._soft_delete_user_context(request):
            powod = self._powod_z_requestu(request)
            for obj in queryset:
                self._soft_delete_jeden(request, obj, powod)

    # --- akcje kosza ----------------------------------------------------

    @admin.action(
        description="♻️ Przywróć zaznaczone (z kosza)",
        permissions=["change", "delete"],
    )
    def przywroc_zaznaczone(self, request, queryset):
        """Przywraca rekordy z kosza (pomija żywe — ``restore()`` przelicza
        punktację i kolejkuje PBN, więc no-op byłby kosztowny)."""
        przywrocono = 0
        with self._soft_delete_user_context(request):
            for obj in queryset:
                if obj.deleted_at is None:
                    continue
                if self._przywroc_jeden(request, obj):
                    przywrocono += 1
        if not przywrocono:
            self.message_user(
                request,
                "Nie przywrócono nic — w zaznaczeniu nie było rekordów "
                "z kosza (albo przywrócenie było niemożliwe). Ustaw filtr "
                "„Kosz” na „🗑️ Tylko skasowane”, zaznacz rekordy i powtórz.",
                level=messages.WARNING,
            )
            return
        self.message_user(
            request,
            f"Przywrócono z kosza: {przywrocono}.",
            level=messages.SUCCESS,
        )

    def _przywroc_jeden(self, request, obj):
        """``restore()`` jednego rekordu; ``False`` (z komunikatem), gdy
        reguły kosza na to nie pozwalają (kolejka PBN, konflikt unikalności,
        rekord już nie w koszu). Wspólne dla akcji i przycisku „Przywróć"."""
        from bpp.models.soft_delete import (
            KonfliktPrzywracania,
            NiedozwolonaZmianaKosza,
        )
        from pbn_export_queue.operacje import RekordWKolejcePBN

        try:
            obj.restore(user=request.user)
        except (
            KonfliktPrzywracania,
            RekordWKolejcePBN,
            NiedozwolonaZmianaKosza,
        ) as e:
            # ``WskazaniaWKoszu`` ma wersję z linkami do rekordów z kosza.
            komunikat = getattr(e, "komunikat_html", None)
            self.message_user(
                request,
                komunikat() if komunikat is not None else str(e),
                level=messages.ERROR,
            )
            return False
        return True

    def moze_przywracac(self, request):
        """Przywracanie = ``delete`` + ``change`` (jak akcja
        ``przywroc_zaznaczone``). Uprawnienia na poziomie MODELU — obiektowe
        ``has_change_permission`` rekordu z kosza zawsze odmawia (tylko do
        odczytu). Admin bez edycji w formularzu (``has_change_permission``
        zawsze ``False``, np. zgłoszenia publikacji) nadpisuje to i pyta
        o uprawnienie ``change`` użytkownika wprost."""
        return self.has_delete_permission(request) and self.has_change_permission(
            request
        )

    def _nazwa_url_przywroc(self):
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_przywroc"

    def get_urls(self):
        from django.urls import path

        return [
            path(
                "<path:object_id>/przywroc/",
                self.admin_site.admin_view(self.przywroc_view),
                name=self._nazwa_url_przywroc(),
            ),
            *super().get_urls(),
        ]

    def przywroc_view(self, request, object_id):
        """Przycisk „♻️ Przywróć" na stronie rekordu z kosza (tylko POST).

        Te same uprawnienia i reguły co akcja „Przywróć zaznaczone"; po
        sukcesie wraca na stronę (już edytowalnego) rekordu."""
        from django.core.exceptions import PermissionDenied
        from django.http import HttpResponseNotAllowed, HttpResponseRedirect

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self.moze_przywracac(request):
            raise PermissionDenied
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(
                request, self.model._meta, object_id
            )
        url_rekordu = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
            args=[obj.pk],
        )
        if obj.deleted_at is None:
            self.message_user(
                request, f"„{obj}” nie jest w koszu.", level=messages.WARNING
            )
            return HttpResponseRedirect(url_rekordu)
        with self._soft_delete_user_context(request):
            if self._przywroc_jeden(request, obj):
                self.message_user(
                    request,
                    f"♻️ Przywrócono z kosza: „{obj}”.",
                    level=messages.SUCCESS,
                )
        return HttpResponseRedirect(url_rekordu)

    #: Ile rekordów wypisać na stronie pośredniej z powodem.
    LIMIT_PODGLADU_KOSZA = 50

    @admin.action(description="🗑️ Usuń do kosza (z powodem)", permissions=["delete"])
    def usun_do_kosza(self, request, queryset):
        """Kosz z powodem podanym na stronie pośredniej (``SoftDeleteLog.powod``).

        Strona pośrednia pokazuje też, które rekordy zostaną wycofane
        z PBN i które są zablokowane (np. w kolejce PBN).
        """
        if request.POST.get("powod_potwierdzony"):
            with self._soft_delete_user_context(request):
                powod = self._powod_z_requestu(request)
                usunieto = 0
                for obj in queryset:
                    if self._soft_delete_jeden(request, obj, powod):
                        usunieto += 1
            if usunieto:
                self.message_user(
                    request,
                    f"Przeniesiono do kosza: {usunieto}.",
                    level=messages.SUCCESS,
                )
            return None

        ile = queryset.count()
        podglad = list(queryset[: self.LIMIT_PODGLADU_KOSZA])
        wiersze = [
            {
                "obj": obj,
                "blokada": (
                    None
                    if self.has_delete_permission(request, obj)
                    else "brak uprawnień" + self._dlaczego_nie_mozna_usunac(obj)
                )
                or self.blokada_kosza(obj),
                "pbn": self.stan_pbn_przed_koszem(obj),
            }
            for obj in podglad
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": "Usuń do kosza",
            "wiersze": wiersze,
            "ile_obiektow": ile,
            "ile_ukrytych": max(0, ile - len(podglad)),
            "wybrane_pk": request.POST.getlist(admin_helpers.ACTION_CHECKBOX_NAME),
            "opts": self.model._meta,
            "action_checkbox_name": admin_helpers.ACTION_CHECKBOX_NAME,
            "action_index": request.POST.get("index", 0),
            "select_across": request.POST.get("select_across", "0"),
        }
        return TemplateResponse(request, "admin/bpp/soft_delete_powod.html", context)

    def get_actions(self, request):
        """Dokłada akcje kosza — WYŁĄCZNIE gdy user ma do nich uprawnienia.

        ``ModelAdmin.get_actions`` filtruje akcje po ``permissions`` tylko
        dla tych, które sam zebrał; akcje dopisane tutaj filtrujemy sami.
        """
        actions = super().get_actions(request)
        if self.has_delete_permission(request):
            actions["usun_do_kosza"] = self.get_action("usun_do_kosza")
            if self.moze_przywracac(request):
                actions["przywroc_zaznaczone"] = self.get_action("przywroc_zaznaczone")
            else:
                actions.pop("przywroc_zaznaczone", None)
        else:
            actions.pop("usun_do_kosza", None)
            actions.pop("przywroc_zaznaczone", None)
        # Trwałe usuwanie z kosza jest WYŁĄCZONE (decyzja właściciela,
        # listopad 2026) — patrz docs/deweloper/soft-delete.md.
        actions.pop("usun_trwale_zaznaczone", None)
        return actions
