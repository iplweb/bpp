import urllib

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django_tables2 import RequestConfig, SingleTableMixin

from bpp.views.mixins import UczelniaSettingRequiredMixin
from django_bpp.version import VERSION
from formdefaults.helpers import FormDefaultsMixin
from long_running.tasks import perform_generic_long_running_task
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)
from raport_slotow.filters import (
    RaportSlotowUczelniaBezJednostekIWydzialowFilter,
    RaportSlotowUczelniaFilter,
)
from raport_slotow.forms import UtworzRaportSlotowUczelniaForm
from raport_slotow.models.uczelnia import RaportSlotowUczelnia
from raport_slotow.tables import (
    RaportSlotowUczelniaBezJednostekIWydzialowTable,
    RaportSlotowUczelniaTable,
)
from raport_slotow.util import MyExportMixin


class ListaRaportSlotowUczelnia(
    UczelniaSettingRequiredMixin, FormDefaultsMixin, LongRunningOperationsView
):
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - uczelnia"
    model = RaportSlotowUczelnia

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class UtworzRaportSlotowUczelnia(
    UczelniaSettingRequiredMixin,
    FormDefaultsMixin,
    CreateLongRunningOperationView,
):
    template_name = "raport_slotow/index.html"
    form_class = UtworzRaportSlotowUczelniaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - uczelnia"
    model = RaportSlotowUczelnia
    task = perform_generic_long_running_task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class RouterRaportuSlotowUczelnia(UczelniaSettingRequiredMixin, LongRunningRouterView):
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    model = RaportSlotowUczelnia


class SzczegolyRaportSlotowUczelnia(
    UczelniaSettingRequiredMixin, LongRunningDetailsView
):
    # template_name = "raport_slotow/raport_slotow_uczelnia_szcz.html"
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]
    # filterset_class = RaportSlotowUczelniaFilter
    model = RaportSlotowUczelnia


class WygenerujPonownieRaportSlotowUczelnia(
    UczelniaSettingRequiredMixin, RestartLongRunningOperationView
):
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    model = RaportSlotowUczelnia


class SzczegolyRaportSlotowUczelniaListaRekordow(
    UczelniaSettingRequiredMixin,
    LoginRequiredMixin,
    MyExportMixin,
    SingleTableMixin,
    LongRunningResultsView,
):
    template_name = "raport_slotow/raport_slotow_uczelnia.html"
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]
    filterset_class = RaportSlotowUczelniaFilter
    model = RaportSlotowUczelnia

    def get_table_class(self):
        if self.parent_object.dziel_na_jednostki_i_wydzialy:
            return RaportSlotowUczelniaTable
        return RaportSlotowUczelniaBezJednostekIWydzialowTable

    def get_filterset_class(self):
        if self.parent_object.dziel_na_jednostki_i_wydzialy:
            return RaportSlotowUczelniaFilter
        return RaportSlotowUczelniaBezJednostekIWydzialowFilter

    def get_table(self, **kwargs):
        table_class = self.get_table_class()
        table = table_class(
            data=self.get_table_data(),
            od_roku=self.parent_object.od_roku,
            do_roku=self.parent_object.do_roku,
            slot=self.parent_object.slot,
            **kwargs,
        )
        RequestConfig(
            self.request, paginate=self.get_table_pagination(table)
        ).configure(table)
        return table

    def get_export_description(self):
        return [
            ("Nazwa raportu:", "raport slotów - uczelnia"),
            ("Od roku:", self.parent_object.od_roku),
            ("Do roku:", self.parent_object.do_roku),
            ("Maksymalny slot:", self.parent_object.slot),
            (
                "Dziel na jednostki:",
                "tak" if self.parent_object.dziel_na_jednostki_i_wydzialy else "nie",
            ),
            ("Wygenerowano:", self.parent_object.finished_on),
            ("Wersja oprogramowania BPP", VERSION),
        ]

    def get_context_data(self, *args, **kwargs):
        context = super(
            SzczegolyRaportSlotowUczelniaListaRekordow, self
        ).get_context_data(**kwargs)
        context["object"] = self.parent_object
        context["export_link"] = urllib.parse.urlencode(
            dict(self.request.GET, **{"_export": "xlsx"}), doseq=True
        )
        return context

    def get_export_filename(self, export_format):
        stamp = timezone.now().strftime("%Y%m%d-%H%M")
        return f"raport_dyscyplin_{self.parent_object.od_roku}-{self.parent_object.do_roku}_{stamp}.{export_format}"
