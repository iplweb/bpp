from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field

from django.contrib import admin

from bpp.admin.core import BaseBppAdmin
from bpp.models import Autor_Dyscyplina


class Autor_DyscyplinaResource(resources.ModelResource):
    def get_queryset(self):

        return (
            super(Autor_DyscyplinaResource, self)
            .get_queryset()
            .select_related("autor")
            .prefetch_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
        )

    rodzaj_autora = Field()

    def dehydrate_rodzaj_autora(self, ad):
        return Autor_Dyscyplina.RODZAJE_AUTORA[ad.rodzaj_autora]

    class Meta:

        model = Autor_Dyscyplina

        fields = (
            "autor__nazwisko",
            "autor__imiona",
            "rok",
            "rodzaj_autora",
            "dyscyplina_naukowa__nazwa",
            "dyscyplina_naukowa__kod",
            "procent_dyscypliny",
            "subdyscyplina_naukowa__nazwa",
            "subdyscyplina_naukowa__kod",
            "procent_subdyscypliny",
        )
        export_order = fields


class Autor_DyscyplinaAdmin(ExportMixin, BaseBppAdmin):
    resource_class = Autor_DyscyplinaResource

    list_filter = [
        "rok",
        "dyscyplina_naukowa",
        "subdyscyplina_naukowa",
        "rodzaj_autora",
        "wymiar_etatu",
    ]
    list_display = [
        "autor",
        "rok",
        "rodzaj_autora",
        "wymiar_etatu",
        "dyscyplina_naukowa",
        "procent_dyscypliny",
        "subdyscyplina_naukowa",
        "procent_subdyscypliny",
    ]
    ordering = ("autor", "rok")


admin.site.register(Autor_Dyscyplina, Autor_DyscyplinaAdmin)
