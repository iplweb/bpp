# -*- encoding: utf-8 -*-

"""W tym pakiecie znajdują się procedury generujące raporty, które są dostępne
"od ręki" -- generowane za pomocą WWW"""
from django.contrib import messages
from django.db.models import Max
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import BaseDeleteView
from django_transaction_signals import defer
from sendfile import sendfile
from bpp.views.raporty.forms import KronikaUczelniForm, RaportOPI2012Form, \
    RaportJednostekForm, RaportDlaKomisjiCentralnejForm

from celeryui.interfaces import IWebTask
from celeryui.models import Report
from .ranking_autorow import *
from .raport_jednostek_2012 import *
from bpp.models import Rekord


class PobranieRaportu(View):
    """Domyślnie dajemy wszystkim zalogowanym, którzy znają link,
    możliwość pobrania raportu."""

    def get(self, request, uid, *args, **kwargs):
        try:
            raport = Report.objects.filter(
                uid=uid).exclude(finished_on=None)[0]
        except IndexError:
            raise Http404

        return sendfile(request, raport.file.path, attachment=True)


class PodgladRaportu(DetailView):
    """Domyślnie dajemy wszystkim zalogowanym, którzy znają link,
    możliwość podejrzenia raportu."""

    template_name = "raporty/podglad_raportu.html"

    def get_object(self, queryset=None):
        try:
            raport = Report.objects.get(uid=self.kwargs['uid'])
        except Report.DoesNotExist:
            raise Http404

        return raport


class KasowanieRaportu(BaseDeleteView):
    slug_field = "uid"
    success_url = '../../..'

    def get_object(self):
        try:
            return Report.objects.get(
                uid=self.kwargs['uid'],
                ordered_by=self.request.user)
        except Report.DoesNotExist:
            raise Http404

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        path = None
        try:
            path = obj.file.path
        except ValueError:
            pass

        response = BaseDeleteView.delete(self, request, *args, **kwargs)

        if path:
            from bpp.tasks import remove_file
            defer(remove_file.delay, obj.file.path)

        messages.add_message(request, messages.INFO, u'Raport został usunięty.')
        return response

    def render_to_response(self, *args, **kwargs):
        return self.delete(self.request, *args, **kwargs)


class RaportSelector(TemplateView):
    template_name = "raporty/selector.html"

    form_mapping = {
        'kronika-uczelni': KronikaUczelniForm,
        'raport-opi-2012': RaportOPI2012Form,
        'raport-jednostek': RaportJednostekForm,
        'raport-dla-komisji-centralnej': RaportDlaKomisjiCentralnejForm
    }

    def get_lata(self):
        return Rekord.objects.all().values_list(
            'rok', flat=True).order_by('rok').distinct()

    def get_ost_rok(self):
        return Rekord.objects.all().aggregate(Max('rok'))['rok__max']

    def get_post_form_name(self):
        return self.request.POST['report']


    def get_post_form(self):
        f = self.form_mapping.get(self.get_post_form_name())
        form = f(data=self.request.POST, lata=self.get_lata())
        return form

    def post(self, request, *args, **kwargs):
        form = self.get_post_form()
        if form.is_valid():
            if request.POST['report'] == 'raport-jednostek':
                # Przekieruj na odpowiednią stronę dla tego raportu
                rok_min = form.cleaned_data['od_roku']
                rok_max = form.cleaned_data['do_roku']
                jednostka = form.cleaned_data['jednostka'].pk

                if rok_min != rok_max:
                    return HttpResponseRedirect(
                        reverse(
                            "bpp:raport-jednostek-rok-min-max",
                            args=(jednostka, rok_min, rok_max)))

                return HttpResponseRedirect(
                    reverse("bpp:raport-jednostek", args=(jednostka, rok_min)))


            arguments = dict(
                [(x, request.POST[x])
                 for x in request.POST.keys() if x not in [
                    'do_not_call_celery', 'report']])

            if request.POST['report'] == "raport-opi-2012":
                arguments['wydzial'] = request.POST.getlist('wydzial')

            r = Report.objects.create(
                ordered_by=request.user,
                function=request.POST['report'],
                arguments=arguments)

            if request.POST.get('do_not_call_celery') != '1':
                from bpp.tasks import make_report
                defer(make_report.delay, r.uid)

            messages.add_message(
                request, messages.INFO,
                "Zamówienie raportu zostało złożone. Zostaniesz poinformowany/a "
                "na bieżąco o zakończeniu jego genrowania.")

        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        lata = self.get_lata()
        ost_rok = self.get_ost_rok()

        request = self.request

        render_mapping = {}

        if request.method == 'POST':
            render_mapping[self.get_post_form_name().replace("-", "_") + "_form"] = \
                self.get_post_form()

        for name, klass in self.form_mapping.items():
            if name.replace("-", "_") + "_form" in render_mapping:
                continue
            render_mapping[name.replace("-", "_") + "_form"] = klass(lata=lata)

        raporty = Report.objects.filter(ordered_by=self.request.user)
        for raport in raporty:
            raport.adapted = IWebTask(raport)

        ctx = dict(
            lata=lata,
            ost_rok=ost_rok,
            raporty=raporty)
        ctx.update(render_mapping)
        ctx.update(kwargs)

        return super(TemplateView, self).get_context_data(**ctx)


