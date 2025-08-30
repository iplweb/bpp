from import_export import resources
from import_export.admin import ImportExportMixin

from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin
from .models import (
    DyscyplinaNieRaportowana_2022_2025,
    IloscUdzialowDlaAutora_2022_2025,
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni_2022_2025,
)

from django.contrib import admin

from bpp.admin.xlsx_export.mixins import EksportDanychMixin


class IloscUdzialowDlaAutora_2022_2025Resource(resources.ModelResource):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("autor")
            .prefetch_related("dyscyplina_naukowa")
        )

    def dehydrate_autor__pbn_uid_id(self, ad):
        if ad.autor.pbn_uid_id:
            return str(ad.autor.pbn_uid_id)
        return None

    class Meta:
        model = IloscUdzialowDlaAutora_2022_2025
        fields = (
            "autor__nazwisko",
            "autor__imiona",
            "autor__pbn_uid_id",
            "autor__orcid",
            "autor__system_kadrowy_id",
            "dyscyplina_naukowa__nazwa",
            "dyscyplina_naukowa__kod",
            "ilosc_udzialow",
            "ilosc_udzialow_monografie",
        )
        export_order = fields


class IloscUdzialowDlaAutoraZaRokResource(resources.ModelResource):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("autor")
            .prefetch_related("dyscyplina_naukowa")
        )

    def dehydrate_autor__pbn_uid_id(self, ad):
        if ad.autor.pbn_uid_id:
            return str(ad.autor.pbn_uid_id)
        return None

    class Meta:
        model = IloscUdzialowDlaAutoraZaRok
        fields = (
            "autor__nazwisko",
            "autor__imiona",
            "autor__pbn_uid_id",
            "autor__orcid",
            "autor__system_kadrowy_id",
            "dyscyplina_naukowa__nazwa",
            "dyscyplina_naukowa__kod",
            "rok",
            "ilosc_udzialow",
            "ilosc_udzialow_monografie",
        )
        export_order = fields


class LiczbaNDlaUczelni_2022_2025Resource(resources.ModelResource):
    class Meta:
        model = LiczbaNDlaUczelni_2022_2025
        fields = (
            "uczelnia__nazwa",
            "dyscyplina_naukowa__nazwa",
            "dyscyplina_naukowa__kod",
            "liczba_n",
        )
        export_order = fields


@admin.register(IloscUdzialowDlaAutora_2022_2025)
class IloscUdzialowDlaAutora_2022_2025_Admin(
    EksportDanychMixin, ReadonlyAdminMixin, admin.ModelAdmin
):
    resource_class = IloscUdzialowDlaAutora_2022_2025Resource
    list_display = [
        "autor",
        "dyscyplina_naukowa",
        "ilosc_udzialow",
        "ilosc_udzialow_monografie",
    ]
    list_select_related = ["autor", "autor__tytul", "dyscyplina_naukowa"]
    search_fields = [
        "autor__nazwisko",
        "dyscyplina_naukowa__kod",
        "dyscyplina_naukowa__nazwa",
    ]
    list_filter = ["dyscyplina_naukowa", "ilosc_udzialow"]
    ordering = ("autor__nazwisko", "autor__imiona", "dyscyplina_naukowa__nazwa")


@admin.register(IloscUdzialowDlaAutoraZaRok)
class IloscUdzialowDlaAutoraZaRokAdmin(
    EksportDanychMixin, ReadonlyAdminMixin, admin.ModelAdmin
):
    resource_class = IloscUdzialowDlaAutoraZaRokResource
    list_display = [
        "autor",
        "dyscyplina_naukowa",
        "rok",
        "ilosc_udzialow",
        "ilosc_udzialow_monografie",
    ]
    list_select_related = ["autor", "autor__tytul", "dyscyplina_naukowa"]
    search_fields = [
        "autor__nazwisko",
        "rok",
        "dyscyplina_naukowa__kod",
        "dyscyplina_naukowa__nazwa",
    ]
    list_filter = ["dyscyplina_naukowa", "rok", "ilosc_udzialow"]
    ordering = ("autor__nazwisko", "autor__imiona", "dyscyplina_naukowa__nazwa", "rok")


@admin.register(LiczbaNDlaUczelni_2022_2025)
class LiczbaNDlaUczelni_2022_2025Admin(
    ImportExportMixin,
    admin.ModelAdmin,
):
    resource_class = LiczbaNDlaUczelni_2022_2025Resource

    list_display = [
        "uczelnia",
        "dyscyplina_naukowa",
        "liczba_n",
    ]

    list_filter = ["dyscyplina_naukowa"]

    raw_id_fields = ["uczelnia", "dyscyplina_naukowa"]


@admin.register(DyscyplinaNieRaportowana_2022_2025)
class DyscyplinaNieRaportowana_2022_2025Admin(admin.ModelAdmin):
    list_display = [
        "uczelnia",
        "dyscyplina_naukowa",
    ]

    list_filter = ["dyscyplina_naukowa"]

    raw_id_fields = ["uczelnia", "dyscyplina_naukowa"]
