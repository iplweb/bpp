from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView
from django_tables2 import MultiTableMixin, SingleTableMixin

from bpp.views.mixins import UczelniaSettingRequiredMixin
from django_bpp.version import VERSION
from raport_slotow.forms import ParametryRaportSlotowEwaluacjaForm
from raport_slotow.models import RaportUczelniaEwaluacjaView
from raport_slotow.tables import RaportSlotowEwaluacjaTable
from raport_slotow.util import (
    MyExportMixin,
    MyTableExport,
)


class ParametryRaportSlotowEwaluacja(UczelniaSettingRequiredMixin, FormView):
    template_name = "raport_slotow/index.html"
    form_class = ParametryRaportSlotowEwaluacjaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Wybór roku"
        return context

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse("raport_slotow:raport-ewaluacja",)
            + "?"
            + urlencode(form.cleaned_data)
        )


class RaportSlotowEwaluacja(
    UczelniaSettingRequiredMixin, MyExportMixin, SingleTableMixin, TemplateView
):
    template_name = "raport_slotow/raport_slotow_ewaluacja.html"
    table_class = RaportSlotowEwaluacjaTable
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]

    def get_form(self, dct):
        return ParametryRaportSlotowEwaluacjaForm(dct)

    def get(self, request, *args, **kw):
        form = self.get_form(request.GET)

        if form.is_valid():
            self.data = form.cleaned_data
            return super(RaportSlotowEwaluacja, self).get(self.request, *args, **kw)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        return HttpResponseRedirect("..")

    def get_export_description(self):
        return [
            ("Nazwa raportu:", "raport slotów - ewaluacja"),
            (f"Od roku:", self.data["od_roku"]),
            (f"Do roku:", self.data["do_roku"]),
            ("Wygenerowano:", timezone.now()),
            ("Wersja oprogramowania BPP", VERSION),
        ]

    def get_queryset(self):
        return RaportUczelniaEwaluacjaView.objects.filter(
            rekord__rok__gte=self.data["od_roku"],
            rekord__rok__lte=self.data["do_roku"],
        ).select_related(
            "rekord",
            "rekord__zrodlo",
            "autorzy",
            "autor_dyscyplina__dyscyplina_naukowa",
            "autor_dyscyplina__subdyscyplina_naukowa",
            "autorzy__dyscyplina_naukowa",
            "rekord__charakter_formalny",
            "autorzy__autor",
            "autorzy__autor__tytul",
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(RaportSlotowEwaluacja, self).get_context_data(**kwargs)
        context["od_roku"] = self.data["od_roku"]
        context["do_roku"] = self.data["do_roku"]
        return context

    def get_export_filename(self, export_format):
        return f"raport_slotow_ewaluacja_{self.data['od_roku']}-{self.data['do_roku']}.{export_format}"
