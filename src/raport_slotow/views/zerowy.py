import urllib

from django.db import connection
from django.db.models import CharField, Count
from django.db.models.functions import Cast
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from nowe_raporty.views import BaseRaportAuthMixin
from raport_slotow.core import autorzy_zerowi
from raport_slotow.filters import RaportZerowyFilter
from raport_slotow.forms.zerowy import RaportSlotowZerowyParametryFormularz
from raport_slotow.models import RaportZerowyEntry
from raport_slotow.tables import RaportSlotowZerowyTable
from raport_slotow.util import MyExportMixin, create_temporary_table_as

from django.contrib import messages
from django.contrib.postgres.aggregates.general import StringAgg


class RaportSlotowZerowyParametry(BaseRaportAuthMixin, FormView):
    form_class = RaportSlotowZerowyParametryFormularz
    uczelnia_attr = "pokazuj_raport_slotow_zerowy"
    template_name = "raport_slotow/raport_slotow_zerowy_zamowienie.html"


class RaportSlotowZerowyWyniki(
    BaseRaportAuthMixin, MyExportMixin, SingleTableMixin, FilterView
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
        context = super().get_context_data(**kwargs)
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        context["min_pk"] = self.form.cleaned_data["min_pk"]
        context["data"] = self.form.cleaned_data

        return context

    def get(self, request, *args, **kwargs):
        # Parse GET data via form
        self.form = RaportSlotowZerowyParametryFormularz(data=request.GET)
        if not self.form.is_valid():
            messages.info(
                request,
                "Podane parametry raportu nie przeszły walidacji. Spróbuj ponownie. ",
            )
            return HttpResponseRedirect(
                reverse("raport_slotow:raport-slotow-zerowy-parametry")
            )

        return super().get(request, *args, **kwargs)

    def render_to_response(self, context, **kwargs):
        # Kod z django_tables2/export/views.py
        if self.request.GET.get("submit") == "Pobierz XLS":
            return self.create_export("xlsx")

        return super().render_to_response(context, **kwargs)

    def get_queryset(self):
        od_roku = self.form.cleaned_data["od_roku"]

        do_roku = self.form.cleaned_data["do_roku"]

        res = autorzy_zerowi(
            min_pk=self.form.cleaned_data["min_pk"],
            od_roku=od_roku,
            do_roku=do_roku,
        )
        create_temporary_table_as("raport_slotow_raportzerowyentry", res)
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE raport_slotow_raportzerowyentry ADD COLUMN id SERIAL"
            )

            for n, cn in enumerate(
                ["autor_id", "rok", "dyscyplina_naukowa_id"], start=1
            ):
                cursor.execute(
                    f"ALTER TABLE raport_slotow_raportzerowyentry RENAME COLUMN col{n} TO {cn}"
                )

        qset = RaportZerowyEntry.objects.group_by(
            "autor", "dyscyplina_naukowa"
        ).annotate(
            lata=StringAgg(Cast("rok", CharField()), ", ", ordering=("rok")),
            ile_lat=Count("rok"),
        )

        if (
            self.form.cleaned_data["rodzaj_raportu"]
            == RaportSlotowZerowyParametryFormularz.RodzajeRaportu.SUMA_LAT
        ):
            qset = qset.filter(ile_lat=do_roku - od_roku + 1)

        return qset
