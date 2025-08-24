from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse

from pbn_api.models.queue import PBN_Export_Queue
from pbn_api.tasks import task_sprobuj_wyslac_do_pbn

from django.contrib import admin, messages

from django.utils.safestring import mark_safe


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

    def has_delete_permission(self, request, *args, **kw):
        if request.user.is_superuser:
            return True
        if "obj" in kw:
            if kw["obj"].zamowil == request.user:
                return True
        return False

    from django.db import models

    formfield_overrides = {models.TextField: {"widget": RenderHTMLWidget}}

    def _resend_single_item(self, obj, user, message_suffix=""):
        """Common logic for resending a single PBN export queue item"""
        obj.refresh_from_db()
        obj.wysylke_zakonczono = None
        obj.zakonczono_pomyslnie = None
        obj.retry_after_user_authorised = None
        obj.dopisz_komunikat(
            f"Ponownie wysłano przez użytkownika: {user}{message_suffix}"
        )
        obj.save()
        task_sprobuj_wyslac_do_pbn.delay(obj.pk)

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
                    "admin:{}_{}_change".format(
                        obj._meta.app_label, obj._meta.model_name
                    ),
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
