from django import forms
from django.urls import reverse
from django_softdelete.filters import SoftDeleteFilter

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

        uczelnia = Uczelnia.objects.get_for_request(request)
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


class RestrictDeletionWhenPBNUIDSetMixin:
    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            if obj.pbn_uid_id is not None:
                return False
        return super().has_delete_permission(request, obj)


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

    title = "Kosz"

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
    """Kosz w adminie dla modeli soft-delete (5 publikacji + ``Autor``).

    Daje: changelistę nad ``global_objects`` z filtrem kosza, akcje
    „przywróć" / „usuń do kosza (z powodem)" / „usuń trwale"
    (superuser-only) oraz JEDEN punkt wstrzyknięcia ``request.user``.

    ⚠️ MIEJSCE W LIŚCIE BAZ: **OSTATNIE**, tuż przed terminalnym
    ``admin.ModelAdmin`` (albo przed konkretną klasą bazową admina, np.
    ``Wydawnictwo_ZwarteAdmin_Baza``). NIE pierwsze.

    Plan fazy 07 kazał wpinać mixin jako PIERWSZY — to był błąd i wpiąłby
    lukę wielotenantową. ``get_queryset`` poniżej nie woła ``super()``
    (nie ma jak: musi podmienić manager bazowy na ``global_objects``),
    więc postawiony na początku MRO uciąłby cały łańcuch — w tym
    ``SiteFilteredAdminMixin.get_queryset`` w ``AutorAdmin``, które zawęża
    widok nie-superusera do jego uczelni (FD#390). Personel uczelni A
    zobaczyłby i skasował autorów uczelni B.

    Na końcu łańcucha ``get_queryset`` tego mixinu jest jego PODSTAWĄ:
    zwraca ``global_objects``, a wszystkie mixiny stojące wyżej nakładają
    na to swoje filtry normalnie. Pozostałe nadpisane metody
    (``get_actions``, ``get_list_filter``) działają z tej pozycji tak samo,
    bo tamte implementacje w łańcuchu wołają ``super()`` i tylko DOKŁADAJĄ
    pozycje. Strażnikiem tej decyzji jest
    ``test_admin.py::test_staff_widzi_tylko_autorow_swojej_uczelni``.
    """

    def get_queryset(self, request):
        """Podstawa łańcucha: ``global_objects`` (żywe + kosz).

        Skasowanego rekordu nie da się inaczej ani otworzyć, ani
        przywrócić — changeform szuka obiektu w tym samym querysecie.
        Kosz chowa dopiero ``PokazSkasowaneFilter``, więc domyślny widok
        listy się nie zmienia.
        """
        qs = self.model.global_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request) or [])
        if PokazSkasowaneFilter not in list_filter:
            list_filter.insert(0, PokazSkasowaneFilter)
        return list_filter
