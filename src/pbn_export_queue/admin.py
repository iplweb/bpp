from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe

from bpp.admin.core import DynamicAdminFilterMixin

from .models import PBN_Export_Queue

User = get_user_model()


class ZamowilUniqueFilter(admin.SimpleListFilter):
    """Custom filter that shows only users who have ordered PBN exports"""

    title = "zamówił"
    parameter_name = "zamowil"

    def lookups(self, request, model_admin):
        # Get unique user IDs from PBN_Export_Queue
        user_ids = (
            PBN_Export_Queue.objects.values_list("zamowil", flat=True)
            .distinct()
            .order_by("zamowil")
        )

        # Fetch only those users and return as choices
        users = User.objects.filter(id__in=user_ids).order_by("username")
        return [(user.id, str(user)) for user in users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(zamowil=self.value())
        return queryset


class RenderHTMLWidget(forms.Textarea):
    def render(self, name, value, renderer, attrs=None):
        return mark_safe((value or "").replace("\n", "<br>"))


@admin.register(PBN_Export_Queue)
class PBN_Export_QueueAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
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

    list_filter = [
        ZamowilUniqueFilter,
        "zakonczono_pomyslnie",
        "retry_after_user_authorised",
    ]

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
