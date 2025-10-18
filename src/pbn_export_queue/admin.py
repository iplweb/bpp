from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import PBN_Export_Queue


class RenderHTMLWidget(forms.Textarea):
    def render(self, name, value, renderer, attrs=None):
        return mark_safe((value or "").replace("\n", "<br>"))


@admin.register(PBN_Export_Queue)
class PBN_Export_QueueAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = [
        "rekord_do_wysylki",
        "object_id",
        "zamowil",
        "wysylke_podjeto",
        "wysylke_zakonczono",
        "ilosc_prob",
        "zakonczono_pomyslnie",
        "retry_after_user_authorised",
    ]

    search_fields = ["zamowil__username", "zamowil__email"]

    list_filter = ["zamowil", "zakonczono_pomyslnie", "retry_after_user_authorised"]

    date_hierarchy = "zamowiono"

    readonly_fields = [
        "object_id",
        "content_type",
        "zamowiono",
        "zamowil",
        "wysylke_podjeto",
        "wysylke_zakonczono",
        "ilosc_prob",
        "zakonczono_pomyslnie",
        "retry_after_user_authorised",
    ]

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None and obj.zamowil == request.user:
            return True
        return False

    from django.db import models

    formfield_overrides = {models.TextField: {"widget": RenderHTMLWidget}}

    def _resend_single_item(self, obj: PBN_Export_Queue, user, message_suffix=""):
        """Common logic for resending a single PBN export queue item"""
        obj.prepare_for_resend(user=user, message_suffix=message_suffix)
        obj.sprobuj_wyslac_do_pbn()

    def resend_to_pbn_action(self, request, queryset):
        count = 0
        for obj in queryset:
            self._resend_single_item(obj, request.user, " (akcja masowa)")
            count += 1

        self.message_user(request, f"Ponowiono wysyłkę do PBN dla {count} elementów")

    resend_to_pbn_action.short_description = "Wyślij ponownie"

    actions = [resend_to_pbn_action]

    def save_form(self, request, form, change):
        return form.save(commit=False)

    def response_change(self, request, obj):
        if "_resend_to_pbn" in request.POST:
            self._resend_single_item(obj, request.user)
            self.message_user(request, f"Ponowiono wysyłkę do PBN: {obj}")
            return HttpResponseRedirect(
                reverse(
                    f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                    args=[obj.pk],
                )
            )
        return super().response_change(request, obj)

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        # Uczyń FAKTYCZNIE readonly :-)
        messages.error(
            request,
            "Obiekt NIE został zapisany -- nie można edytować tej części serwisu.",
        )
        return
