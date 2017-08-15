from django.http.response import HttpResponseRedirect
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import DetailView

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Wydzial, Jednostka
from .forms import AutorRaportForm
from .forms import JednostkaRaportForm, WydzialRaportForm


class BaseFormView(FormView):
    template_name = "nowe_raporty/formularz.html"

    def form_valid(self, form):
        d = form.cleaned_data
        return HttpResponseRedirect(f"./{ d['obiekt'].pk }/{ d['rok'] }/")


class AutorRaportFormView(BaseFormView):
    form_class = AutorRaportForm


class JednostkaRaportFormView(BaseFormView):
    form_class = JednostkaRaportForm


class WydzialRaportFormView(BaseFormView):
    form_class = WydzialRaportForm


class BaseGenerujView(TemplateView):
    def get_context_data(self, **kwargs):
        return kwargs


class GenerujRaportBase(DetailView):
    template_name = "nowe_raporty/generuj.html"

    def get_context_data(self, **kwargs):
        from flexible_reports.models import Report
        try:
            report = Report.objects.get(slug=self.report_slug)
        except Report.DoesNotExist:
            report = None

        if report:
            report.set_base_queryset(
                self.get_base_queryset().filter(rok=self.kwargs['rok'])
            )

        kwargs['report'] = report
        kwargs['rok'] = self.kwargs['rok']
        return super(GenerujRaportBase, self).get_context_data(**kwargs)


class GenerujRaportDlaAutora(GenerujRaportBase):
    report_slug = 'raport-autorow'
    model = Autor

    def get_base_queryset(self):
        return Rekord.objects.prace_autora(self.object)


class GenerujRaportDlaJednostki(GenerujRaportBase):
    report_slug = 'raport-jednostek'
    model = Jednostka

    def get_base_queryset(self):
        return Rekord.objects.prace_jednostki(self.object)


class GenerujRaportDlaWydzialu(GenerujRaportBase):
    report_slug = 'raport-wydzialow'
    model = Wydzial

    def get_base_queryset(self):
        return Rekord.objects.prace_wydzialu(self.object)
