import functools
import ssl
from copy import copy

from django.http import HttpResponse, HttpResponseRedirect
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.views.generic import FormView, TemplateView
from django_tables2 import MultiTableMixin, RequestConfig
from django_weasyprint.utils import django_url_fetcher

from formdefaults.helpers import FormDefaultsMixin
from nowe_raporty.views import BaseRaportAuthMixin
from raport_slotow.forms.autor import AutorRaportSlotowForm
from raport_slotow.tables import RaportSlotowAutorTable
from raport_slotow.util import InitialValuesFromGETMixin, MyExportMixin, MyTableExport
from .. import const

from django.utils import timezone
from django.utils.functional import cached_property

from bpp.models import Cache_Punktacja_Autora_Query_View, Dyscyplina_Naukowa

from django_bpp.version import VERSION

SESSION_KEY = "raport_slotow_data"


class WyborOsoby(
    BaseRaportAuthMixin, InitialValuesFromGETMixin, FormDefaultsMixin, FormView
):
    template_name = "raport_slotow/wybor_osoby.html"
    form_class = AutorRaportSlotowForm
    uczelnia_attr = "pokazuj_raport_slotow_autor"
    title = "Raport slotów - autor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Wybór autora"
        return context

    def form_valid(self, form):
        form.cleaned_data["obiekt"] = form.cleaned_data["obiekt"].pk
        self.request.session[SESSION_KEY] = form.cleaned_data
        return HttpResponseRedirect(
            reverse("raport_slotow:raport") + "?_export=" + form.cleaned_data["_export"]
        )


class RaportSlotow(BaseRaportAuthMixin, MyExportMixin, MultiTableMixin, TemplateView):
    template_name = "raport_slotow/raport_slotow_autor.html"
    table_class = RaportSlotowAutorTable
    uczelnia_attr = "pokazuj_raport_slotow_autor"
    export_formats = ["html", "xlsx", "pdf"]
    export_class = MyTableExport

    def create_export(self, export_format):
        tables = self.get_tables()
        n = int(self.request.GET.get("n", 0))

        dg = []
        dpb = []
        for ad in self.autor.autor_dyscyplina_set.filter(
            rok__range=(self.kwargs["od_roku"], self.kwargs["do_roku"])
        ).order_by("rok"):
            dg.append((ad.rok, ad.dyscyplina_naukowa.nazwa, ad.procent_dyscypliny))
            if ad.subdyscyplina_naukowa is not None:
                dpb.append(
                    (ad.rok, ad.subdyscyplina_naukowa.nazwa, ad.procent_subdyscypliny)
                )

        dg = ", ".join([f"{rok} - {nazwa} ({procent})" for rok, nazwa, procent in dg])
        dpb = ", ".join([f"{rok} - {nazwa} ({procent})" for rok, nazwa, procent in dpb])

        description = [
            ("Nazwa raportu:", "raport slotów - autor"),
            ("Autor:", str(self.autor)),
            ("ORCID:", str(self.autor.orcid or "brak")),
            ("PBN ID:", str(self.autor.pbn_id or "brak")),
            ("Dyscypliny autora:", dg),
            ("Subdyscypliny autora:", dpb or "żadne"),
            ("Dyscyplina tabeli:", str(tables[n].dyscyplina_naukowa or "żadna")),
            ("Opis działania", self.opis_dzialania),
            ("Minimalny PK", self.kwargs["minimalny_pk"]),
            ("Od roku:", self.kwargs["od_roku"]),
            ("Do roku:", self.kwargs["do_roku"]),
            ("Wygenerowano:", str(timezone.make_naive(timezone.now()))),
            ("Wersja oprogramowania BPP", VERSION),
        ]

        exporter = MyTableExport(
            export_format=export_format,
            table=tables[n],
            export_description=description,
        )
        return exporter.response(filename=self.get_export_filename(export_format, n))

    def get_tables(self):
        ret = []
        cpaq = Cache_Punktacja_Autora_Query_View.objects.filter(
            autor=self.autor,
            rekord__rok__gte=self.kwargs["od_roku"],
            rekord__rok__lte=self.kwargs["do_roku"],
            pkdaut__gt=0,
        )

        minimalny_pk = self.kwargs["minimalny_pk"]

        for elem in cpaq.values_list("dyscyplina", flat=True).order_by().distinct():
            table_class = self.table_class

            if self.kwargs["dzialanie"] == const.DZIALANIE_WSZYSTKO:
                data = cpaq.filter(dyscyplina_id=elem)
                if minimalny_pk is not None:
                    data = data.filter(rekord__punkty_kbn__gte=minimalny_pk)
            elif self.kwargs["dzialanie"] == const.DZIALANIE_SLOT:
                max_pkdaut, ids, maks_slot = self.autor.zbieraj_sloty(
                    self.kwargs["slot"],
                    self.kwargs["od_roku"],
                    self.kwargs["do_roku"],
                    dyscyplina_id=elem,
                    minimalny_pk=minimalny_pk,
                )
                data = cpaq.filter(pk__in=ids)
            else:
                raise NotImplementedError()

            table = table_class(
                data.select_related(
                    "rekord",
                    "dyscyplina",
                ).prefetch_related("rekord__zrodlo")
            )
            RequestConfig(
                self.request, paginate=self.get_table_pagination(table)
            ).configure(table)
            table.dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(pk=elem)
            ret.append(table)

        if not ret:
            table_class = self.table_class
            table = table_class(data=cpaq.select_related("rekord", "dyscyplina"))
            RequestConfig(
                self.request, paginate=self.get_table_pagination(table)
            ).configure(table)
            table.dyscyplina_naukowa = None
            ret.append(table)

        return ret

    def get_queryset(self):
        return None

    @cached_property
    def opis_dzialania(self):
        if self.kwargs["dzialanie"] == const.DZIALANIE_WSZYSTKO:
            return "wszystkie rekordy z punktacją dla dyscyplin za dany okres"
        elif self.kwargs["dzialanie"] == const.DZIALANIE_SLOT:
            return f"zbieranie najlepszych prac do {self.kwargs['slot']} slot{pluralize(self.kwargs['slot'], 'u,ów')}"
        else:
            raise NotImplementedError

    def get_context_data(self, *, cleaned_data=None, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["autor"] = self.autor
        context["od_roku"] = self.kwargs["od_roku"]
        context["do_roku"] = self.kwargs["do_roku"]
        context["minimalny_pk"] = self.kwargs["minimalny_pk"]
        context["slot"] = self.kwargs["slot"]
        context["dzialanie"] = self.kwargs["dzialanie"]
        context["opis_dzialania"] = self.opis_dzialania
        return context

    def get_export_filename(self, export_format, n):
        return f"raport_slotow_{self.autor.slug}_{self.kwargs['od_roku']}-{self.kwargs['do_roku']}-{n}.{export_format}"

    def get(self, request, *args, **kwargs):
        # Wczytaj dane z sesji i zwaliduj przez formularz
        data = request.session.get(SESSION_KEY)
        form = AutorRaportSlotowForm(data)
        if form.is_valid():
            self.kwargs.update(form.cleaned_data)

            self.autor = self.kwargs["obiekt"]

            export_format = self.request.GET.get(self.export_trigger_param, None)
            if export_format in ["xlsx", "html", None]:
                context = self.get_context_data(**kwargs)
                return self.render_to_response(context)
            elif export_format == "pdf":
                new_get = copy(self.request.GET)
                new_get["_export"] = "html"
                self.request.GET = new_get
                context = self.get_context_data(**kwargs)
                ret = self.render_to_response(context)

                # UWAGA: jeżeli w wygenerowanej stronie WWW cokolwiek będzie dostępne
                # za hasłem, to może się ona nie wygenerować prawidłowo. Żeby wyrenderować
                # PDFa, serwer wstecznie odpytuje sam siebie - o CSSy, obrazki, fonty itp.
                # Jeżeli nagle będziemy mieli jakis zahasłowany statyczny asset, to będzie
                # trzeba go tutaj udostępnić, żeby WeasyPrint miał ułatwione zadanie.
                # (mpasternak, 17.03.2021)
                from weasyprint import HTML

                # disable host and certificate check
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                url_fetcher = functools.partial(django_url_fetcher, ssl_context=context)

                response = HttpResponse(
                    content=HTML(
                        string=ret.render().content,
                        base_url=self.request.build_absolute_uri(),
                        url_fetcher=url_fetcher,
                    ).write_pdf(),
                    content_type="application/pdf",
                )
                filename = self.get_export_filename("pdf", 0)
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
            else:
                raise NotImplementedError(
                    f"unknown format {export_format}, also this should never happen"
                )
        else:
            return HttpResponseRedirect("..")
