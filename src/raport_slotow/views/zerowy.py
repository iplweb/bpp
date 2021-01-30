import urllib

from django.contrib.postgres.aggregates.general import StringAgg
from django.db import connection
from django.db.models.fields import TextField
from django.db.models.functions import Cast
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from bpp.views.mixins import UczelniaSettingRequiredMixin
from raport_slotow.core import autorzy_zerowi
from raport_slotow.filters import RaportZerowyFilter
from raport_slotow.models import RaportZerowyEntry
from raport_slotow.tables import RaportSlotowZerowyTable
from raport_slotow.util import MyExportMixin, create_temporary_table_as


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

    min_pk = None

    def get_context_data(self, *args, **kwargs):
        context = super(RaportSlotowZerowy, self).get_context_data(**kwargs)
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        context["min_pk"] = self.min_pk
        return context

    def get_queryset(self):
        res = autorzy_zerowi(min_pk=self.min_pk)

        create_temporary_table_as("raport_slotow_raportzerowyentry", res)
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE raport_slotow_raportzerowyentry ADD COLUMN id SERIAL"
            )

        qset = RaportZerowyEntry.objects.group_by(
            "autor", "dyscyplina_naukowa"
        ).annotate(lata=StringAgg(Cast("rok", TextField()), ", ", ordering=("rok")))

        return qset
