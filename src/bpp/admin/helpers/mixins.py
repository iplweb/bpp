from django import forms
from django.contrib.admin.options import TO_FIELD_VAR
from django.contrib.admin.utils import unquote
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.urls import reverse

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
