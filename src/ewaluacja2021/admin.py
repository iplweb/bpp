# Register your models here.
from import_export import resources

from ewaluacja2021.models import IloscUdzialowDlaAutora_2022_2025

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


@admin.register(IloscUdzialowDlaAutora_2022_2025)
class IloscUdzialowDlaAutora_2022_2025_Admin(EksportDanychMixin, admin.ModelAdmin):
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
    list_filter = ["dyscyplina_naukowa"]
    ordering = ("autor__nazwisko", "autor__imiona", "dyscyplina_naukowa__nazwa")
