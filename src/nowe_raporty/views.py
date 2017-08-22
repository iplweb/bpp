
from django.conf import settings
from django.http.response import HttpResponseRedirect, HttpResponse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import DetailView
from flexible_reports.adapters import django_tables2
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Wydzial, Jednostka
from .forms import AutorRaportForm
from .forms import JednostkaRaportForm, WydzialRaportForm


class BaseFormView(FormView):
    template_name = "nowe_raporty/formularz.html"
    title = "Raporty"

    def form_valid(self, form):
        d = form.cleaned_data
        return HttpResponseRedirect(
            f"./{ d['obiekt'].pk }/{ d['od_roku'] }/{ d['do_roku'] }/?docx={ d['docx'] }")

    def get_context_data(self, **kwargs):
        kwargs['title'] = self.title
        return super(BaseFormView, self).get_context_data(**kwargs)


class AutorRaportFormView(BaseFormView):
    form_class = AutorRaportForm
    title = "Raport autorów"


class JednostkaRaportFormView(BaseFormView):
    form_class = JednostkaRaportForm
    title = "Raport jednostek"


class WydzialRaportFormView(BaseFormView):
    form_class = WydzialRaportForm
    title = "Raport wydziałów"


class BaseGenerujView(TemplateView):
    def get_context_data(self, **kwargs):
        return kwargs


class GenerujRaportBase(DetailView):
    template_name = "nowe_raporty/generuj.html"

    @property
    def okres(self):
        if self.kwargs['od_roku'] == self.kwargs['do_roku']:
            return self.kwargs['od_roku']
        else:
            return self.kwargs['do_roku']

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
            report.set_base_queryset(
                self.get_base_queryset().filter(
                    rok__gte=self.kwargs['od_roku'],
                    rok__lte=self.kwargs['do_roku'])
            )

            report.set_context(
                {'obiekt': self.object,
                 'punktuj_monografie': settings.PUNKTUJ_MONOGRAFIE}
            )

        kwargs['report'] = report
        kwargs['od_roku'] = self.kwargs['od_roku']
        kwargs['do_roku'] = self.kwargs['do_roku']
        kwargs['title'] = self.title
        kwargs['form_link'] = self.form_link
        kwargs['form_title'] = self.form_title
        return super(GenerujRaportBase, self).get_context_data(**kwargs)

    def render_to_response(self, context, **response_kwargs):
        if 'docx' in self.request.GET and self.request.GET['docx'] == "True":
            context['request'] = self.request
            data = django_tables2.report(
                context['report'],
                parent_context=RequestContext(self.request, context)
            )
            response = HttpResponse(
                """<head>
                <meta http-equiv="Content-Type" content="text/html; charset=utf-8" /> 
                </head><body>""" + data + "</body>",
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response[
                'Content-Disposition'] = 'attachment; filename=' + self.title + ".docx"
            response['Content-Length'] = len(data)
            return response

        return super(GenerujRaportBase, self).render_to_response(
            context, **response_kwargs)


class GenerujRaportDlaAutora(GenerujRaportBase):
    report_slug = 'raport-autorow'
    form_link = 'nowe_raporty:autor_form'
    form_title = "Raport autorów"
    model = Autor

    def get_base_queryset(self):
        return Rekord.objects.prace_autora(self.object)


class GenerujRaportDlaJednostki(GenerujRaportBase):
    report_slug = 'raport-jednostek'
    form_link = 'nowe_raporty:jednostka_form'
    form_title = "Raport jednostek"
    model = Jednostka

    def get_base_queryset(self):
        return Rekord.objects.prace_jednostki(self.object)


class GenerujRaportDlaWydzialu(GenerujRaportBase):
    report_slug = 'raport-wydzialow'
    form_link = 'nowe_raporty:wydzial_form'
    form_title = "Raport wydziałów"
    model = Wydzial

    def get_base_queryset(self):
        return Rekord.objects.prace_wydzialu(self.object)
