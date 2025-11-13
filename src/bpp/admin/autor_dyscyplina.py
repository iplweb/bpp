from decimal import Decimal

from dal import autocomplete
from django import forms
from django.contrib import admin
from django.db.models import DecimalField, ExpressionWrapper, F, Value
from django.db.models.functions import Coalesce
from djangoql.admin import DjangoQLSearchMixin
from import_export import resources
from import_export.fields import Field

from bpp.admin.core import DynamicAdminFilterMixin
from bpp.admin.filters import (
    OrcidAutoraDyscyplinyObecnyFilter,
    PBN_UID_IDAutoraObecnyFilter,
)
from bpp.admin.xlsx_export.mixins import EksportDanychMixin
from bpp.models import Autor, Autor_Dyscyplina


class Autor_DyscyplinaResource(resources.ModelResource):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("autor")
            .prefetch_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
        )

    rodzaj_autora = Field()

    def dehydrate_rodzaj_autora(self, ad):
        if ad.rodzaj_autora_id is not None:
            return ad.rodzaj_autora.skrot
        return ""

    def dehydrate_autor__pbn_uid_id(self, ad):
        if ad.autor.pbn_uid_id:
            return str(ad.autor.pbn_uid_id)
        return None

    class Meta:
        model = Autor_Dyscyplina

        fields = (
            "autor__nazwisko",
            "autor__imiona",
            "rok",
            "rodzaj_autora__skrot",
            "wymiar_etatu",
            "autor__pbn_uid_id",
            "autor__orcid",
            "autor__system_kadrowy_id",
            "dyscyplina_naukowa__nazwa",
            "dyscyplina_naukowa__kod",
            "procent_dyscypliny",
            "subdyscyplina_naukowa__nazwa",
            "subdyscyplina_naukowa__kod",
            "procent_subdyscypliny",
        )
        export_order = fields


class SumaProcentowFilter(admin.SimpleListFilter):
    """Custom filtr dla weryfikacji sumy procentów dyscypliny i subdyscypliny."""

    title = "suma procentów"
    parameter_name = "suma_procent"

    def lookups(self, request, model_admin):
        return (
            ("nieprawidlowa", "Suma != 100%"),
            ("prawidlowa", "Suma = 100%"),
            ("zero", "Suma = 0%"),
        )

    def queryset(self, request, queryset):
        from django.db.models import Q

        # Jeśli filtr nie jest aktywny, zwróć oryginalny queryset
        if self.value() is None:
            return queryset

        # Filtruj tylko autorów z jest_w_n=True LUB licz_sloty=True
        queryset = queryset.filter(
            Q(rodzaj_autora__jest_w_n=True) | Q(rodzaj_autora__licz_sloty=True)
        )

        # Annotate queryset z sumą procentów używając COALESCE dla NULL wartości
        qs = queryset.annotate(
            suma_procent=ExpressionWrapper(
                Coalesce(F("procent_dyscypliny"), Value(Decimal("0")))
                + Coalesce(F("procent_subdyscypliny"), Value(Decimal("0"))),
                output_field=DecimalField(),
            )
        )

        if self.value() == "nieprawidlowa":
            # Suma != 100 (z tolerancją 0.01 dla zaokrągleń)
            return qs.exclude(
                suma_procent__gte=Decimal("99.99"), suma_procent__lte=Decimal("100.01")
            )
        elif self.value() == "prawidlowa":
            # Suma = 100 (z tolerancją 0.01)
            return qs.filter(
                suma_procent__gte=Decimal("99.99"), suma_procent__lte=Decimal("100.01")
            )
        elif self.value() == "zero":
            # Suma = 0
            return qs.filter(suma_procent=Decimal("0"))

        return queryset


class Autor_DyscyplinaForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-autocomplete"),
    )

    class Meta:
        model = Autor_Dyscyplina
        fields = [
            "rok",
            "autor",
            "rodzaj_autora",
            "wymiar_etatu",
            "dyscyplina_naukowa",
            "procent_dyscypliny",
            "subdyscyplina_naukowa",
            "procent_subdyscypliny",
            "zatrudnienie_od",
            "zatrudnienie_do",
        ]


class Autor_DyscyplinaAdmin(
    DynamicAdminFilterMixin, DjangoQLSearchMixin, EksportDanychMixin, admin.ModelAdmin
):
    djangoql_completion_enabled_by_default = True
    djangoql_completion = True

    max_allowed_export_items = 10000

    resource_class = Autor_DyscyplinaResource
    form = Autor_DyscyplinaForm

    list_filter = [
        "rok",
        "dyscyplina_naukowa",
        "subdyscyplina_naukowa",
        "rodzaj_autora",
        "wymiar_etatu",
        SumaProcentowFilter,
        OrcidAutoraDyscyplinyObecnyFilter,
        PBN_UID_IDAutoraObecnyFilter,
    ]
    list_display = [
        "autor",
        "rok",
        "rodzaj_autora",
        "wymiar_etatu",
        "pbn_uid_id",
        "orcid",
        "dyscyplina_naukowa",
        "procent_dyscypliny",
        "subdyscyplina_naukowa",
        "procent_subdyscypliny",
    ]
    ordering = ("autor", "rok")

    def orcid(self, obj):
        return obj.autor.orcid

    orcid.admin_order_field = "autor__orcid"

    def pbn_uid_id(self, obj):
        return obj.autor.pbn_uid_id

    pbn_uid_id.admin_order_field = "autor__pbn_uid_id"
    pbn_uid_id.short_description = "PBN UID autora"


admin.site.register(Autor_Dyscyplina, Autor_DyscyplinaAdmin)
