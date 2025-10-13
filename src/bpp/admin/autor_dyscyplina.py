from dal import autocomplete
from djangoql.admin import DjangoQLSearchMixin
from import_export import resources
from import_export.fields import Field

from django.contrib import admin

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


from django import forms


class Autor_DyscyplinaForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-autocomplete"),
    )

    class Meta:
        model = Autor_Dyscyplina
        fields = "__all__"


class Autor_DyscyplinaAdmin(DjangoQLSearchMixin, EksportDanychMixin, admin.ModelAdmin):
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
