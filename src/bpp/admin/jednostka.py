# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
from django import forms
from mptt.admin import DraggableMPTTAdmin

from ..models.struktura import Jednostka, Jednostka_Wydzial
from .core import CommitedModelAdmin, RestrictDeletionToAdministracjaGroupMixin
from .helpers import ADNOTACJE_FIELDSET, LimitingFormset, ZapiszZAdnotacjaMixin

from django.contrib import admin

from bpp.models import Autor_Jednostka, Uczelnia


class Jednostka_WydzialInline(admin.TabularInline):
    model = Jednostka_Wydzial
    extra = 1


class Autor_JednostkaForm(forms.ModelForm):
    model = Autor_Jednostka

    class Meta:
        fields = ["autor", "rozpoczal_prace", "zakonczyl_prace", "funkcja"]


class Autor_JednostkaInline(admin.TabularInline):
    form = Autor_JednostkaForm
    model = Autor_Jednostka
    readonly_fields = ["autor"]
    formset = LimitingFormset
    extra = 0


class JednostkaAdmin(
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    CommitedModelAdmin,
    DraggableMPTTAdmin,
):

    change_list_template = "admin/grappelli_mptt_change_list.html"

    list_display_links = ["nazwa"]

    list_display = (
        "tree_actions",
        "nazwa",
        "skrot",
        "wydzial",
        "widoczna",
        "wchodzi_do_raportow",
        "skupia_pracownikow",
        "zarzadzaj_automatycznie",
        "pbn_id",
    )
    list_select_related = [
        "wydzial",
    ]
    fields = None
    list_filter = (
        "wydzial",
        "widoczna",
        "wchodzi_do_raportow",
        "skupia_pracownikow",
        "zarzadzaj_automatycznie",
    )
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]

    inlines = (
        Jednostka_WydzialInline,
        Autor_JednostkaInline,
    )

    autocomplete_fields = ["pbn_uid"]

    readonly_fields = ["wydzial", "aktualna", "ostatnio_zmieniony"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "skrot",
                    "uczelnia",
                    "wydzial",
                    "parent",
                    "aktualna",
                    "pbn_id",
                    "pbn_uid",
                    "opis",
                    "widoczna",
                    "wchodzi_do_raportow",
                    "skupia_pracownikow",
                    "zarzadzaj_automatycznie",
                    "email",
                    "www",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )

    def get_changeform_initial_data(self, request):
        # Zobacz na komentarz do Jednostka.uczelnia.default
        data = super(JednostkaAdmin, self).get_changeform_initial_data(request)
        if "uczelnia" not in data:
            data["uczelnia"] = Uczelnia.objects.first()
        return data


admin.site.register(Jednostka, JednostkaAdmin)
