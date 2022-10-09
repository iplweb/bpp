import sys

from django import forms
from djangoql.admin import DjangoQLSearchMixin
from mptt.admin import DraggableMPTTAdmin

from ..models.struktura import Jednostka, Jednostka_Wydzial
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .filters import PBN_UID_IDObecnyFilter
from .helpers import ADNOTACJE_FIELDSET, LimitingFormset, ZapiszZAdnotacjaMixin

from django.contrib import admin

from django.utils.html import format_html

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
    DjangoQLSearchMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    BaseBppAdminMixin,
    DraggableMPTTAdmin,
):
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    change_list_template = "admin/grappelli_mptt_change_list.html"

    list_display_links = ["indented_title"]

    list_display = [
        "tree_actions",
        "indented_title",
        "skrot",
        "parent_nazwa",
        "wydzial_skrot",
        "widoczna",
        "rodzaj_jednostki",
        "wchodzi_do_raportow",
        "skupia_pracownikow",
        "pbn_uid_id",
    ]

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
        PBN_UID_IDObecnyFilter,
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
                    "rodzaj_jednostki",
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
        data = super().get_changeform_initial_data(request)
        if "uczelnia" not in data:
            data["uczelnia"] = Uczelnia.objects.first()
        return data

    def changelist_view(self, request, *args, **kwargs):
        self.request = request
        return super().changelist_view(request, *args, **kwargs)

    def indented_title(self, item):
        """
        Generate a short title for an object, indent it depending on
        the object's depth in the hierarchy.
        """

        # Wysuwaj nazwę jednostki wyłacznie w przypadku, gdy nie filtrujemy listy
        if not self.request.GET.keys():
            return super().indented_title(item)

        return format_html(
            "<div>{}</div>",
            item,
        )

    indented_title.short_description = "Nazwa jednostki"

    def wydzial_skrot(self, item):
        if item.wydzial_id:
            return item.wydzial.skrot

    wydzial_skrot.short_description = "Wydział"

    def parent_nazwa(self, item):
        if item.parent_id:
            return item.parent.nazwa

    parent_nazwa.short_description = "Jednostka nadrzędna"

    def get_list_display(self, request):
        if request.GET.keys():
            return self.list_display[1:]
        return self.list_display

    def get_list_per_page(self):
        from django.db import connection

        if "bpp_uczelnia" not in connection.introspection.table_names():
            return BaseBppAdminMixin.list_per_page

        req = None
        if hasattr(self, "request"):
            req = self.request

        uczelnia = Uczelnia.objects.get_for_request(req)

        if uczelnia is None:
            return BaseBppAdminMixin.list_per_page

        if uczelnia.sortuj_jednostki_alfabetycznie:
            return BaseBppAdminMixin.list_per_page

        return sys.maxsize

    list_per_page = property(get_list_per_page)


admin.site.register(Jednostka, JednostkaAdmin)
