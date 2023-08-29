import urllib
from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from formdefaults.helpers import FormDefaultsMixin
from nowe_raporty.views import BaseRaportAuthMixin
from raport_slotow.filters import RaportSlotowUczelniaEwaluacjaFilter
from raport_slotow.forms.ewaluacja import ParametryRaportSlotowEwaluacjaForm
from raport_slotow.models import RaportEwaluacjaUpowaznieniaView
from raport_slotow.tables import RaportEwaluacjaUpowaznieniaTable
from raport_slotow.util import MyExportMixin

from django.utils import timezone

from django_bpp.version import VERSION


class ParametryRaportEwaluacjaUpowaznienia(
    BaseRaportAuthMixin,
    FormDefaultsMixin,
    FormView,
):
    template_name = "raport_slotow/index.html"
    form_class = ParametryRaportSlotowEwaluacjaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport ewaluacja upoważnienia"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse(
                "raport_slotow:raport-ewaluacja-upowaznienia",
            )
            + "?"
            + urlencode(form.cleaned_data)
        )


class RaportEwaluacjaUpowaznienia(
    BaseRaportAuthMixin, MyExportMixin, SingleTableMixin, FilterView
):
    template_name = "raport_slotow/raport_ewaluacja_upowaznienia.html"
    table_class = RaportEwaluacjaUpowaznieniaTable
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    export_formats = ["html", "xlsx"]
    filterset_class = RaportSlotowUczelniaEwaluacjaFilter

    def get_form(self, dct):
        return ParametryRaportSlotowEwaluacjaForm(dct)

    def get(self, request, *args, **kw):
        form = self.get_form(request.GET)

        if form.is_valid():
            self.data = form.cleaned_data
            if self.data["upowaznienie_pbn"] == "":
                self.data["upowaznienie_pbn"] = None

            return super().get(self.request, *args, **kw)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        return HttpResponseRedirect("..")

    def get_export_description(self):
        return [
            ("Nazwa raportu:", "raport ewaluacja upoważnienia"),
            ("Od roku:", self.data["od_roku"]),
            ("Do roku:", self.data["do_roku"]),
            ("Upoważnienie PBN:", self.data["upowaznienie_pbn"]),
            ("Wygenerowano:", str(timezone.make_naive(timezone.now()))),
            ("Wersja oprogramowania BPP", VERSION),
        ]

    def get_queryset(self):
        upowaznienie_kw = {}
        if self.data.get("upowaznienie_pbn") is not None:
            upowaznienie_kw["autorzy__upowaznienie_pbn"] = self.data["upowaznienie_pbn"]

        return RaportEwaluacjaUpowaznieniaView.objects.filter(
            rekord__rok__gte=self.data["od_roku"],
            rekord__rok__lte=self.data["do_roku"],
            **upowaznienie_kw,
        ).select_related(
            "autorzy",
            "rekord",
            "autorzy__dyscyplina_naukowa",
            "autorzy__autor__aktualna_jednostka",
            "autorzy__autor__tytul",
            "rekord__charakter_formalny",
            "rekord__typ_kbn",
            "autorzy__autor__aktualna_jednostka__wydzial",
            "rekord__zrodlo",
            "rekord__wydawnictwo_nadrzedne",
            "autor_dyscyplina",
            "rekord__charakter_formalny",
            "autorzy__autor",
            "autor_dyscyplina__dyscyplina_naukowa",
            "autor_dyscyplina__subdyscyplina_naukowa",
        )

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["od_roku"] = self.data["od_roku"]
        context["do_roku"] = self.data["do_roku"]
        context["export_link"] = urllib.parse.urlencode(
            dict(
                self.request.GET,
                **{
                    "_export": "xlsx",
                    "od_roku": self.data["od_roku"],
                    "do_roku": self.data["do_roku"],
                    "upowaznienie_pbn": self.data["upowaznienie_pbn"],
                },
            ),
            doseq=True,
        )

        return context

    def get_export_filename(self, export_format):
        return f"raport_ewaluacjA_upowaznienia_{self.data['od_roku']}-{self.data['do_roku']}.{export_format}"
