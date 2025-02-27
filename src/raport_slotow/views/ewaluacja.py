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
from raport_slotow.models import RaportUczelniaEwaluacjaView
from raport_slotow.tables import RaportSlotowEwaluacjaTable
from raport_slotow.util import MyExportMixin

from django.utils import timezone

from django_bpp.version import VERSION


class ParametryRaportSlotowEwaluacja(
    BaseRaportAuthMixin,
    FormDefaultsMixin,
    FormView,
):
    template_name = "raport_slotow/index.html"
    form_class = ParametryRaportSlotowEwaluacjaForm
    uczelnia_attr = "pokazuj_raport_slotow_uczelnia"
    title = "Raport slotów - ewaluacja"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title  # "Wybór roku"
        return context

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse(
                "raport_slotow:raport-ewaluacja",
            )
            + "?"
            + urlencode(form.cleaned_data)
        )


class RaportSlotowEwaluacja(
    BaseRaportAuthMixin, MyExportMixin, SingleTableMixin, FilterView
):
    template_name = "raport_slotow/raport_slotow_ewaluacja.html"
    table_class = RaportSlotowEwaluacjaTable
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
            ("Nazwa raportu:", "raport slotów - ewaluacja"),
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

        return (
            RaportUczelniaEwaluacjaView.objects.filter(
                rekord__rok__gte=self.data["od_roku"],
                rekord__rok__lte=self.data["do_roku"],
                **upowaznienie_kw,
            )
            .select_related(
                "rekord",
                "rekord__zrodlo",
                "rekord__wydawnictwo_nadrzedne",
                "autor_dyscyplina",
                "autorzy",
                "rekord__charakter_formalny",
                "autorzy__autor",
                "autorzy__dyscyplina_naukowa",
                "autorzy__autor__tytul",
                "autor_dyscyplina__dyscyplina_naukowa",
                "autor_dyscyplina__subdyscyplina_naukowa",
            )
            .prefetch_related(
                "autorzy__autor__aktualna_jednostka",
                "autorzy__jednostka",
                "rekord__zrodlo__punktacja_zrodla_set",
            )
            .only(
                "autorzy_z_dyscypliny",
                "pkdaut",
                "slot",
                "rekord__rok",
                "rekord__szczegoly",
                "rekord__id",
                "rekord__tytul_oryginalny",
                "rekord__opis_bibliograficzny_autorzy_cache",
                "rekord__punkty_kbn",
                "rekord__impact_factor",
                "rekord__kwartyl_w_wos",
                "rekord__kwartyl_w_scopus",
                "rekord__informacje",
                "rekord__opis_bibliograficzny_zapisani_autorzy_cache",
                "rekord__wydawnictwo_nadrzedne_id",
                "rekord__wydawnictwo_nadrzedne__id",
                "rekord__wydawnictwo_nadrzedne__tytul_oryginalny",
                "rekord__charakter_formalny",
                "rekord__pbn_uid_id",
                "rekord__zrodlo_id",
                "rekord__zrodlo__id",
                "rekord__zrodlo__nazwa",
                "rekord__zrodlo__punktacja_zrodla",
                "autorzy__autor__nazwisko",
                "autorzy__autor__pseudonim",
                "autorzy__autor__poprzednie_nazwiska",
                "autorzy__autor__pokazuj_poprzednie_nazwiska",
                "autorzy__autor__id",
                "autorzy__autor__pbn_id",
                "autorzy__autor__orcid",
                "autorzy__autor__imiona",
                "autorzy__autor__tytul",
                "autorzy__upowaznienie_pbn",
                "autorzy__profil_orcid",
                "autorzy__jednostka_id",
                "autorzy__jednostka__nazwa",
                "autorzy__autor__aktualna_jednostka_id",
                "autorzy__autor__aktualna_jednostka__nazwa",
                "autor_dyscyplina__dyscyplina_naukowa",
                "autor_dyscyplina__dyscyplina_naukowa__id",
                "autor_dyscyplina__dyscyplina_naukowa__nazwa",
                "autor_dyscyplina__dyscyplina_naukowa__kod",
                "autor_dyscyplina__dyscyplina_naukowa__widoczna",
                "autor_dyscyplina__procent_dyscypliny",
                "autor_dyscyplina__subdyscyplina_naukowa",
                "autor_dyscyplina__subdyscyplina_naukowa__id",
                "autor_dyscyplina__subdyscyplina_naukowa__nazwa",
                "autor_dyscyplina__subdyscyplina_naukowa__kod",
                "autor_dyscyplina__subdyscyplina_naukowa__widoczna",
                "autor_dyscyplina__procent_subdyscypliny",
                "autorzy__dyscyplina_naukowa",
                "autorzy__dyscyplina_naukowa__id",
                "autorzy__dyscyplina_naukowa__nazwa",
                "autorzy__dyscyplina_naukowa__kod",
                "autorzy__dyscyplina_naukowa__widoczna",
                "autorzy__autor",
                "autorzy__autor__tytul",
            )
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
        return f"raport_slotow_ewaluacja_{self.data['od_roku']}-{self.data['do_roku']}.{export_format}"
