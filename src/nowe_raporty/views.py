import os

from django.conf import settings
from django.http.response import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import DetailView
from django_tables2.export.export import TableExport
from flexible_reports.adapters.django_tables2 import as_docx, as_tablib_databook
from flexible_reports.models.report import Report

from formdefaults.helpers import FormDefaultsMixin
from .forms import (
    AutorRaportForm,
    JednostkaRaportForm,
    UczelniaRaportForm,
    WydzialRaportForm,
)

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka, Wydzial
from bpp.views.mixins import UczelniaSettingRequiredMixin


class BaseFormView(FormDefaultsMixin, FormView):
    template_name = "nowe_raporty/formularz.html"
    title = "Raporty"

    def form_valid(self, form):
        d = form.cleaned_data
        return HttpResponseRedirect(
            f"./{ d['obiekt'].pk }/{ d['od_roku'] }/{ d['do_roku'] }/?"
            f"_export={ d['_export'] }&"
            f"_tzju={d['tylko_z_jednostek_uczelni']}"
        )

    def get_context_data(self, **kwargs):
        kwargs["title"] = self.title
        kwargs["report"] = get_object_or_404(Report, slug=self.report_slug)
        return super().get_context_data(**kwargs)


class BaseRaportAuthMixin(UczelniaSettingRequiredMixin):
    """Wspólny mixin - bazowa klasa autoryzująca dostęp do raportów.

    Wymaga ustawienia obiektu uczelnia ``pokazuj_raport_x`` oraz wymaga
    odpowiedniej grupy czyli ``generowanie_raportow``.

    """

    group_required = GR_RAPORTY_WYSWIETLANIE


class AutorRaportAuthMixin(BaseRaportAuthMixin):
    uczelnia_attr = "pokazuj_raport_autorow"


class JednostkaRaportAuthMixin(BaseRaportAuthMixin):
    uczelnia_attr = "pokazuj_raport_jednostek"


class WydzialRaportAuthMixin(BaseRaportAuthMixin):
    uczelnia_attr = "pokazuj_raport_wydzialow"


class UczelniaRaportAuthMixin(BaseRaportAuthMixin):
    uczelnia_attr = "pokazuj_raport_uczelni"


class AutorRaportFormView(AutorRaportAuthMixin, BaseFormView):
    form_class = AutorRaportForm
    title = "Raport autorów"
    report_slug = "raport-autorow"

    def form_valid(self, form):
        d = form.cleaned_data
        return HttpResponseRedirect(
            f"./{ d['obiekt'].pk }/{ d['od_roku'] }/{ d['do_roku'] }/?"
            f"_export={ d['_export'] }&"
            f"_tzju={ d['tylko_z_jednostek_uczelni'] }"
        )


class JednostkaRaportFormView(JednostkaRaportAuthMixin, BaseFormView):
    report_slug = "raport-jednostek"
    form_class = JednostkaRaportForm
    title = "Raport jednostek"


class UczelniaRaportFormView(UczelniaRaportAuthMixin, BaseFormView):
    report_slug = "raport-uczelni"
    form_class = UczelniaRaportForm
    title = "Raport uczelni"

    def form_valid(self, form):
        d = form.cleaned_data
        return HttpResponseRedirect(
            f"./{ d['od_roku'] }/{ d['do_roku'] }/?"
            f"_export={ d['_export'] }&"
            f"_tzju={d['tylko_z_jednostek_uczelni']}"
        )


class WydzialRaportFormView(WydzialRaportAuthMixin, BaseFormView):
    report_slug = "raport-wydzialow"
    form_class = WydzialRaportForm
    title = "Raport wydziałów"


class BaseGenerujView(TemplateView):
    def get_context_data(self, **kwargs):
        return kwargs


class GenerujRaportBase(DetailView):
    template_name = "nowe_raporty/generuj.html"

    @property
    def okres(self):
        if self.kwargs["od_roku"] == self.kwargs["do_roku"]:
            return self.kwargs["od_roku"]
        else:
            return "{}-{}".format(self.kwargs["od_roku"], self.kwargs["do_roku"])

    @property
    def title(self):
        return f"Raport dla { self.object } za { self.okres }"

    def get_context_data(self, **kwargs):
        from flexible_reports.models import Report

        try:
            report = Report.objects.get(slug=self.report_slug)
        except Report.DoesNotExist:
            report = None

        if report:
            base_queryset = self.get_base_queryset()

            base_queryset = base_queryset.filter(
                rok__gte=self.kwargs["od_roku"], rok__lte=self.kwargs["do_roku"]
            )

            uczelnia = Uczelnia.objects.get_for_request(self.request)
            if uczelnia is not None:
                ukryte_statusy = uczelnia.ukryte_statusy("raporty")
                if ukryte_statusy:
                    base_queryset = base_queryset.exclude(
                        status_korekty_id__in=ukryte_statusy
                    )

            base_queryset = base_queryset.select_related(
                "typ_kbn", "charakter_formalny"
            )

            report.set_base_queryset(base_queryset)

            report.set_context(
                {
                    "obiekt": self.object,
                    "punktuj_monografie": settings.PUNKTUJ_MONOGRAFIE,
                }
            )

        kwargs["report"] = report
        kwargs["od_roku"] = self.kwargs["od_roku"]
        kwargs["do_roku"] = self.kwargs["do_roku"]
        kwargs["title"] = self.title
        kwargs["form_link"] = self.form_link
        kwargs["form_title"] = self.form_title
        return super().get_context_data(**kwargs)

    def as_docx_response(self, report, parent_context, filename=None):
        data = as_docx(report, parent_context)

        response = FileResponse(
            data,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        if filename is None:
            filename = report.title + ".docx"

        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        response["Content-Length"] = os.stat(data.name).st_size
        return response

    def as_xlsx_response(self, report, parent_context, filename=None):
        response = HttpResponse(content_type=TableExport.FORMATS[TableExport.XLSX])
        if filename is None:
            filename = report.title + ".xlsx"

        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        xlsx = as_tablib_databook(report, parent_context)

        # Patch dla błędu "Invlaid character / found in sheet title"
        for sheet in xlsx.sheets():
            sheet.title = sheet.title.replace("/", "-")

        data = xlsx.export(TableExport.XLSX)
        response["Content-Length"] = len(data)
        response.write(data)
        return response

    def render_to_response(self, context, **response_kwargs):
        _export = self.request.GET.get("_export")

        if _export in ("docx", "xlsx"):
            context["request"] = self.request
            parent_context = RequestContext(self.request, context)
            fun = getattr(self, "as_%s_response" % _export)
            return fun(
                context["report"], parent_context, filename=self.title + "." + _export
            )

        return super().render_to_response(context, **response_kwargs)


class GenerujRaportDlaAutora(AutorRaportAuthMixin, GenerujRaportBase):
    report_slug = "raport-autorow"
    form_link = "nowe_raporty:autor_form"
    form_title = "Raport autorów"
    model = Autor

    def get_base_queryset(self):
        if self.request.GET.get("_tzju", "True") == "True":
            return Rekord.objects.prace_autora_z_afiliowanych_jednostek(self.object)

        return Rekord.objects.prace_autora(self.object)


class GenerujRaportDlaJednostki(JednostkaRaportAuthMixin, GenerujRaportBase):
    report_slug = "raport-jednostek"
    form_link = "nowe_raporty:jednostka_form"
    form_title = "Raport jednostek"
    model = Jednostka

    def get_base_queryset(self):
        if self.request.GET.get("_tzju", "True") == "True":
            return Rekord.objects.prace_jednostki(self.object, afiliowane=True)
        return Rekord.objects.prace_jednostki(self.object)


class GenerujRaportDlaWydzialu(WydzialRaportAuthMixin, GenerujRaportBase):
    report_slug = "raport-wydzialow"
    form_link = "nowe_raporty:wydzial_form"
    form_title = "Raport wydziałów"
    model = Wydzial

    def get_base_queryset(self):
        if self.request.GET.get("_tzju", "True") == "True":
            return Rekord.objects.prace_wydzialu(self.object, afiliowane=True)
        return Rekord.objects.prace_wydzialu(self.object)


class GenerujRaportDlaUczelni(UczelniaRaportAuthMixin, GenerujRaportBase):
    report_slug = "raport-uczelni"
    form_link = "nowe_raporty:uczelnia_form"
    form_title = "Raport uczelni"
    model = Uczelnia

    def get_object(self, queryset=None):
        return Uczelnia.objects.get_for_request(self.request)

    def get_base_queryset(self):
        if self.request.GET.get("_tzju", "True") == "True":
            return Rekord.objects.filter(autorzy__afiliuje=True)
        return Rekord.objects.all()
