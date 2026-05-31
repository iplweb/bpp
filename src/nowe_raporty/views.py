import os

from django.conf import settings
from django.contrib.auth.mixins import AccessMixin
from django.http import Http404
from django.http.response import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.context import RequestContext
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import urlencode
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import DetailView
from django_tables2.export.export import TableExport
from flexible_reports.adapters.django_tables2 import as_tablib_databook
from flexible_reports.models.report import Report
from formdefaults.helpers import FormDefaultsMixin

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka, Wydzial
from bpp.views.mixins import UczelniaSettingRequiredMixin

from .docx_export import as_docx
from .forms import (
    AutorRaportForm,
    JednostkaRaportForm,
    UczelniaRaportForm,
    WydzialRaportForm,
    form_class_dla,
)
from .models import DefinicjaRaportu
from .poziomy import POZIOMY


def zastosuj_filtry_zaawansowane(queryset, params):
    """Zawęża queryset Rekord wg opcjonalnych filtrów zaawansowanych z GET."""

    def _liczba(nazwa):
        try:
            return float(params[nazwa])
        except (KeyError, TypeError, ValueError):
            return None

    zakresy = [
        ("punkty_mnisw_od", "punkty_kbn__gte"),
        ("punkty_mnisw_do", "punkty_kbn__lte"),
        ("if_od", "impact_factor__gte"),
        ("if_do", "impact_factor__lte"),
        ("punktacja_wewnetrzna_od", "punktacja_wewnetrzna__gte"),
        ("punktacja_wewnetrzna_do", "punktacja_wewnetrzna__lte"),
    ]
    for param, lookup in zakresy:
        wartosc = _liczba(param)
        if wartosc is not None:
            queryset = queryset.filter(**{lookup: wartosc})

    if params.get("tylko_punktowane") in ("True", "true", "on", "1"):
        queryset = queryset.filter(punkty_kbn__gt=0)
    return queryset


def _redirect_do_generuj(cleaned_data, pola_zaawansowane):
    """Buduje redirect z formularza do widoku generuj (z parametrami)."""
    params = {
        "_export": cleaned_data["_export"],
        "_tzju": cleaned_data.get("tylko_z_jednostek_uczelni", True),
    }
    for pole in pola_zaawansowane:
        wartosc = cleaned_data.get(pole)
        if wartosc not in (None, "", False):
            params[pole] = wartosc
    querystring = urlencode(params)

    obiekt = cleaned_data.get("obiekt")
    if obiekt is not None:
        prefiks = f"./{obiekt.pk}/{cleaned_data['od_roku']}/{cleaned_data['do_roku']}/"
    else:
        prefiks = f"./{cleaned_data['od_roku']}/{cleaned_data['do_roku']}/"
    return HttpResponseRedirect(f"{prefiks}?{querystring}")


class BaseFormView(FormDefaultsMixin, FormView):
    template_name = "nowe_raporty/formularz.html"
    title = "Raporty"

    def form_valid(self, form):
        return _redirect_do_generuj(
            form.cleaned_data, getattr(form, "POLA_ZAAWANSOWANE", [])
        )

    def get_context_data(self, **kwargs):
        kwargs["title"] = self.title
        try:
            kwargs["report"] = Report.objects.get(slug=self.report_slug)
        except Report.DoesNotExist:
            # Brak definicji raportu nie jest bledem HTTP - szablon pokaze
            # przyjazny komunikat (a redaktorowi link do modulu redagowania).
            kwargs["report"] = None
        kwargs["report_slug"] = self.report_slug
        kwargs["report_title"] = self.title
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


class JednostkaRaportFormView(JednostkaRaportAuthMixin, BaseFormView):
    report_slug = "raport-jednostek"
    form_class = JednostkaRaportForm
    title = "Raport jednostek"


class UczelniaRaportFormView(UczelniaRaportAuthMixin, BaseFormView):
    report_slug = "raport-uczelni"
    form_class = UczelniaRaportForm
    title = "Raport uczelni"


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
        return f"Raport dla {self.object} za {self.okres}"

    def get_report(self):
        """Definicja flexible_reports.Report. Generyczny widok nadpisuje."""
        return Report.objects.filter(slug=self.report_slug).first()

    def get_form_link_url(self):
        """URL do formularza raportu (breadcrumb). Generyczny widok nadpisuje."""
        return reverse(self.form_link)

    def get_context_data(self, **kwargs):
        report = self.get_report()

        if report:
            base_queryset = self.get_base_queryset()

            base_queryset = base_queryset.filter(
                rok__gte=self.kwargs["od_roku"], rok__lte=self.kwargs["do_roku"]
            )

            base_queryset = zastosuj_filtry_zaawansowane(
                base_queryset, self.request.GET
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
        kwargs["form_link_url"] = self.get_form_link_url()
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

        # Bez definicji raportu nie ma czego eksportowac - pokaz strone z
        # komunikatem (jak temat 1) zamiast wywalac sie 500 w as_*_response(None).
        if _export in ("docx", "xlsx") and context.get("report") is not None:
            context["request"] = self.request
            parent_context = RequestContext(self.request, context)
            fun = getattr(self, f"as_{_export}_response")
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


# --- Generyczne widoki (data-driven, per DefinicjaRaportu) ------------------


class RaportDostepMixin(AccessMixin):
    """Autoryzacja generycznych widoków przez ``DefinicjaRaportu.widoczny_dla``."""

    @cached_property
    def definicja(self):
        return get_object_or_404(DefinicjaRaportu, slug=self.kwargs["slug"])

    def dispatch(self, request, *args, **kwargs):
        if not self.definicja.widoczny_dla(request):
            if request.user.is_authenticated:
                raise Http404
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class RaportFormView(RaportDostepMixin, FormDefaultsMixin, FormView):
    template_name = "nowe_raporty/formularz.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # formdefaults czyta self.form_class() - dynamiczna klasa per definicja
        self.form_class = form_class_dla(self.definicja)

    def get_form_title(self):
        return self.definicja.nazwa

    def get_initial(self):
        initial = super().get_initial()
        cfg = POZIOMY[self.definicja.poziom]
        if cfg.ma_pk and not initial.get("obiekt"):
            queryset = cfg.model.objects.all()
            if queryset.count() == 1:
                initial["obiekt"] = queryset.first()
        return initial

    def form_valid(self, form):
        return _redirect_do_generuj(
            form.cleaned_data, getattr(form, "POLA_ZAAWANSOWANE", [])
        )

    def get_context_data(self, **kwargs):
        kwargs["title"] = self.definicja.nazwa
        kwargs["report"] = self.definicja.report
        kwargs["report_slug"] = self.definicja.report.slug
        kwargs["report_title"] = self.definicja.nazwa
        return super().get_context_data(**kwargs)


class RaportGenerujView(RaportDostepMixin, GenerujRaportBase):
    def get_report(self):
        return self.definicja.report

    @property
    def form_title(self):
        return self.definicja.nazwa

    def get_form_link_url(self):
        return reverse("nowe_raporty:raport_form", args=[self.definicja.slug])

    def get_object(self, queryset=None):
        cfg = POZIOMY[self.definicja.poziom]
        if cfg.ma_pk:
            return get_object_or_404(cfg.model, pk=self.kwargs["pk"])
        return Uczelnia.objects.get_for_request(self.request)

    def get_base_queryset(self):
        cfg = POZIOMY[self.definicja.poziom]
        tylko = self.request.GET.get("_tzju", "True") == "True"
        return cfg.base_queryset(self.object, tylko)
