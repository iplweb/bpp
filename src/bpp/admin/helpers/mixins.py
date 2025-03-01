from django import forms
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

        uczelnia = Uczelnia.objects.get_default()
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
