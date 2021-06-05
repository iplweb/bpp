# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
from django import forms
from treenode.admin import TreeNodeModelAdmin
from treenode.forms import TreeNodeForm
from treenode.utils import split_pks

from ..models.struktura import Jednostka, Jednostka_Wydzial
from . import CommitedModelAdmin, RestrictDeletionToAdministracjaGroupMixin
from .filters import PBN_UID_IDObecnyFilter
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


class JednostkaForm(TreeNodeForm):
    def __init__(self, *args, **kw):
        super(JednostkaForm, self).__init__(*args, **kw)

        if "tn_parent" not in self.fields:
            return
        exclude_pks = []
        obj = self.instance
        if obj.pk:
            exclude_pks += [obj.pk]
            exclude_pks += split_pks(obj.tn_descendants_pks)
        manager = obj.__class__.objects
        self.fields["tn_parent"].queryset = (
            manager.prefetch_related("tn_children")
            .select_related()
            .exclude(pk__in=exclude_pks)
        )

    class Meta:
        model = Jednostka
        fields = []
        fieldsets = (
            (
                None,
                {
                    "fields": (
                        "nazwa",
                        "skrot",
                        "uczelnia",
                        "wydzial",
                        "tn_parent",
                        # "tn_order",
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


class JednostkaAdmin(
    # SortableAdminMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    CommitedModelAdmin,
    TreeNodeModelAdmin,
):
    treenode_display_mode = TreeNodeModelAdmin.TREENODE_DISPLAY_MODE_ACCORDION
    form = JednostkaForm

    list_display = [
        "nazwa",
        "skrot",
        "wydzial",
        # "kolejnosc",
        "widoczna",
        "wchodzi_do_raportow",
        "skupia_pracownikow",
        # "zarzadzaj_automatycznie",
        # "pbn_id",
        "pbn_uid_pk",
    ]
    list_select_related = [
        "wydzial",
    ]
    list_filter = (
        "wydzial",
        "widoczna",
        "wchodzi_do_raportow",
        "skupia_pracownikow",
        "zarzadzaj_automatycznie",
        PBN_UID_IDObecnyFilter,
    )
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]

    inlines = (
        Jednostka_WydzialInline,
        Autor_JednostkaInline,
    )

    autocomplete_fields = ["pbn_uid"]

    readonly_fields = ["wydzial", "aktualna", "ostatnio_zmieniony"]
    fields = None
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "skrot",
                    "uczelnia",
                    "wydzial",
                    "tn_parent",
                    # "tn_order",
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

    def get_ordering(self, request):
        res = super(JednostkaAdmin, self).get_ordering(request)
        if res:
            return res
        return Jednostka.objects.get_default_ordering()

    def pbn_uid_pk(self, obj):
        return obj.pbn_uid_id

    def get_changeform_initial_data(self, request):
        # Zobacz na komentarz do Jednostka.uczelnia.default
        data = super(JednostkaAdmin, self).get_changeform_initial_data(request)
        if "uczelnia" not in data:
            data["uczelnia"] = Uczelnia.objects.first()
        return data


admin.site.register(Jednostka, JednostkaAdmin)
