from django import forms

from pbn_api.admin.mixins import ReadOnlyListChangeFormAdminMixin
from pbn_api.models.queue import PBN_Export_Queue

from django.contrib import admin

from django.utils.safestring import mark_safe


class RenderHTMLWidget(forms.Textarea):
    def render(self, name, value, renderer, attrs=None):
        return mark_safe((value or "").replace("\n", "<br>"))


@admin.register(PBN_Export_Queue)
class PBN_Export_QueueAdmin(ReadOnlyListChangeFormAdminMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = [
        "rekord_do_wysylki",
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

    def save_form(self, request, form, change):
        return
