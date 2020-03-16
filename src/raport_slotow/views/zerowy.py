import urllib
from urllib.parse import urlencode

from django.contrib.postgres.aggregates.general import StringAgg
from django.db import connection
from django.db.models.fields import TextField
from django.db.models.functions import Cast
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from bpp.models import Cache_Punktacja_Autora_Query_View
from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
from bpp.views.mixins import UczelniaSettingRequiredMixin
from raport_slotow.filters import RaportZerowyFilter
from raport_slotow.models import RaportZerowyEntry
from raport_slotow.tables import RaportSlotowZerowyTable
from raport_slotow.util import (
    MyExportMixin,
    create_temporary_table_as,
)


class RaportSlotowZerowy(
    UczelniaSettingRequiredMixin, MyExportMixin, SingleTableMixin, FilterView
):
    """Pokazuje listę wszystkich autorów, którzy mają zadeklarowane dziedziny naukowe
    ale nie posiadają slotów za konkretny rok.
    """

    template_name = "raport_slotow/raport_slotow_zerowy.html"
    uczelnia_attr = "pokazuj_raport_slotow_zerowy"
    filterset_class = RaportZerowyFilter
    table_class = RaportSlotowZerowyTable

    def get_context_data(self, *args, **kwargs):
        context = super(RaportSlotowZerowy, self).get_context_data(**kwargs)
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        return context

    def get_queryset(self):
        # wartośći zadeklarowane w bazie danych
        defined = (
            Autor_Dyscyplina.objects.values("autor_id", "rok", "dyscyplina_naukowa_id")
            .exclude(dyscyplina_naukowa_id=None)
            .union(
                Autor_Dyscyplina.objects.values(
                    "autor_id", "rok", "subdyscyplina_naukowa_id"
                ).exclude(subdyscyplina_naukowa_id=None)
            )
        )

        # zestawy autor/rok/dyscyplina z całej bazy danych
        existent = Cache_Punktacja_Autora_Query_View.objects.all().values(
            "autor_id", "rekord__rok", "dyscyplina_id"
        )

        res = defined.difference(existent)
        create_temporary_table_as("raport_slotow_raportzerowyentry", res)
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE raport_slotow_raportzerowyentry ADD COLUMN id SERIAL"
            )

        qset = RaportZerowyEntry.objects.group_by(
            "autor", "dyscyplina_naukowa"
        ).annotate(lata=StringAgg(Cast("rok", TextField()), ", ", ordering=("rok")))

        return qset
