import sys

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from import_export.admin import ImportMixin
from mptt.admin import DraggableMPTTAdmin

from bpp.admin.helpers.djangoql import BppDjangoQLSearchMixin
from bpp.models import Autor_Jednostka, Uczelnia

from ..models.struktura import Jednostka, Jednostka_Rodzic
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .filters import JednostkaNadrzednaFilter, PBN_UID_IDObecnyFilter, WydzialFilter
from .helpers import LimitingFormset
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.site_filtered import SiteFilteredAdminMixin
from .jednostka_import import JednostkaImportResource
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin


class Jednostka_RodzicInline(admin.TabularInline):
    model = Jednostka_Rodzic
    # Jednostka_Rodzic ma DWA FK do Jednostka (jednostka, parent) — inline na
    # JednostkaAdmin musi jawnie wskazać po którym się wiąże.
    fk_name = "jednostka"
    extra = 1


class PodjednostkiInline(admin.TabularInline):
    """Read-only lista jednostek PODRZĘDNYCH (bezpośrednich dzieci, ``parent=
    self``) w formularzu JednostkaAdmin -- pokazywana NAD inlinem
    autor-jednostka (Faza B, #438, issue 4).

    W adminie edytujemy jeden poziom drzewa naraz, więc pokazujemy tylko
    bezpośrednie dzieci (nie całe poddrzewo). Inline jest wyłącznie do
    podglądu: bez dodawania/kasowania, pola tylko-do-odczytu, z linkiem do
    formularza zmiany każdej podjednostki. ``fk_name`` jawnie wskazuje
    self-FK ``parent`` (Jednostka ma DWA odwołania do samej siebie:
    ``parent`` w drzewie i denorm ``wydzial``)."""

    model = Jednostka
    fk_name = "parent"
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = "jednostka podrzędna"
    verbose_name_plural = "jednostki podrzędne (bezpośrednie)"
    fields = ("nazwa_link", "skrot", "rodzaj", "aktualna", "widoczna")
    readonly_fields = ("nazwa_link", "skrot", "rodzaj", "aktualna", "widoczna")

    def has_add_permission(self, request, obj=None):
        return False

    def nazwa_link(self, instance):
        if instance.pk is None:
            return ""
        url = reverse("admin:bpp_jednostka_change", args=(instance.pk,))
        return format_html('<a href="{}">{}</a>', url, instance.nazwa)

    nazwa_link.short_description = "Nazwa jednostki"


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
    ImportMixin,
    SiteFilteredAdminMixin,
    BppDjangoQLSearchMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    EksportDanychMixin,
    BaseBppAdminMixin,
    DraggableMPTTAdmin,
):
    uczelnia_field_path = "uczelnia"
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True
    # Eksport (EksportDanychMixin/ExportMixin) bierze resource_classes;
    # import (ImportMixin) dostaje dedykowany resource przez override nizej —
    # oba mixiny domyslnie czytaja TEN SAM atrybut resource_classes.
    resource_classes = [resources.JednostkaResource]

    def get_import_resource_classes(self, request):
        resource_classes = [JednostkaImportResource]
        self.check_resource_classes(resource_classes)
        return resource_classes

    change_list_template = "admin/grappelli_mptt_change_list.html"
    # ImportMixin + EksportDanychMixin (ExportMixin) jednoczesnie: import_export
    # wybiera `import_export_change_list_template` po MRO, a ImportMixin jest
    # przed ExportMixin -> bez tego renderuje sie szablon TYLKO z importem
    # (przycisk "Eksport" znika). Wymuszamy polaczony szablon import+export;
    # rozszerza on `change_list_template` (grappelli_mptt) jako bazowy, wiec
    # draggable MPTT zostaje zachowany.
    import_export_change_list_template = (
        "admin/import_export/change_list_import_export.html"
    )

    list_display_links = ["indented_title"]

    list_display = [
        "tree_actions",
        "indented_title",
        "skrot",
        "parent_nazwa",
        "uczelnia_skrot",
        "wydzial_skrot",
        "widoczna",
        "rodzaj",
        "wchodzi_do_rankingu_autorow",
        "skupia_pracownikow",
        "pbn_uid_id",
    ]

    list_select_related = [
        "wydzial",
        "rodzaj",
        "uczelnia",
    ]
    fields = None
    list_filter = (
        WydzialFilter,
        JednostkaNadrzednaFilter,
        "widoczna",
        "wchodzi_do_rankingu_autorow",
        "skupia_pracownikow",
        "zarzadzaj_automatycznie",
        "rodzaj",
        "aktualna",
        PBN_UID_IDObecnyFilter,
    )
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]

    inlines = (
        Jednostka_RodzicInline,
        PodjednostkiInline,
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
                    "rodzaj",
                    "opis",
                    "widoczna",
                    "wchodzi_do_rankingu_autorow",
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
            data["uczelnia"] = Uczelnia.objects.get_for_request(request)
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

    def uczelnia_skrot(self, item):
        if item.uczelnia_id:
            return item.uczelnia.skrot

    uczelnia_skrot.short_description = "Uczelnia"

    def parent_nazwa(self, item):
        if item.parent_id:
            return item.parent.nazwa

    parent_nazwa.short_description = "Jednostka nadrzędna"

    def get_list_display(self, request):
        if request.GET.keys():
            return self.list_display[1:]
        return self.list_display

    def get_list_per_page(self):
        from django.db import DatabaseError, connection

        # Django evaluates `ModelAdmin.list_per_page` during app-ready
        # system checks (`apps.populate()`), które `manage.py migrate`
        # uruchamia PRZED zastosowaniem migracji. W tym oknie schemat bazy
        # potrafi być starszy niż kod — bail out do wartości domyślnej w
        # każdym takim „schema-lags-code":
        #   * DB nieosiągalna (OperationalError) — fresh clone / CI bez PG,
        #   * tabela `bpp_uczelnia` jeszcze nie istnieje (świeża baza),
        #   * tabela istnieje, ale świeżo dodana, nie-zmigrowana kolumna
        #     (np. `site_id` z multi-hosted) — istniejąca instalacja w
        #     trakcie upgrade'u. Zapytanie rzuca wtedy ProgrammingError;
        #     bez tego guarda `migrate` padał, więc nie dało się zastosować
        #     migracji dodającej kolumnę (deadlock upgrade'u).
        # `DatabaseError` to wspólny rodzic OperationalError/ProgrammingError.
        req = getattr(self, "request", None)
        try:
            if "bpp_uczelnia" not in connection.introspection.table_names():
                return BaseBppAdminMixin.list_per_page
            uczelnia = Uczelnia.objects.get_for_request(req)
        except DatabaseError:
            return BaseBppAdminMixin.list_per_page

        if uczelnia is None:
            return BaseBppAdminMixin.list_per_page

        if uczelnia.sortuj_jednostki_alfabetycznie:
            return BaseBppAdminMixin.list_per_page

        return sys.maxsize

    list_per_page = property(get_list_per_page)


admin.site.register(Jednostka, JednostkaAdmin)
