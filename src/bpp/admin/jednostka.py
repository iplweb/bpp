# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin

from bpp.models import Autor_Jednostka, Uczelnia, SORTUJ_ALFABETYCZNIE
from miniblog.admin import SmallerTextarea
from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from .helpers import *
from ..models.struktura import Jednostka, Jednostka_Wydzial


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
    SortableAdminMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    CommitedModelAdmin,
):
    list_display = (
        "nazwa",
        "skrot",
        "wydzial",
        "kolejnosc",
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
                    "aktualna",
                    "pbn_id",
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

    def get_list_display(self, request):
        if Jednostka.objects.get_default_ordering() == SORTUJ_ALFABETYCZNIE:
            ret = self.list_display[:]
            ret.remove("_reorder")
            return ret

        return self.list_display

    def get_changeform_initial_data(self, request):
        # Zobacz na komentarz do Jednostka.uczelnia.default
        data = super(JednostkaAdmin, self).get_changeform_initial_data(request)
        if "uczelnia" not in data:
            data["uczelnia"] = Uczelnia.objects.first()
        return data


admin.site.register(Jednostka, JednostkaAdmin)
