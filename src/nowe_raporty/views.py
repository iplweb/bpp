from django.http.response import HttpResponseRedirect
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import DetailView

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
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

class GenerujRaportDlaAutora(DetailView):
    template_name = "nowe_raporty/generuj.html"
    model = Autor
    
    def get_context_data(self, **kwargs):
        from flexible_reports.models import Report
        report = Report.objects.all().first()

        report.set_base_queryset(
            Rekord.objects.prace_autora(self.object)
                .filter(rok=self.kwargs['rok'])
        )

        kwargs['report'] = report
        kwargs['rok'] = self.kwargs['rok']

        return super(GenerujRaportDlaAutora, self).get_context_data(**kwargs)