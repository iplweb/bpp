# -*- encoding: utf-8 -*-


from braces.views import LoginRequiredMixin
from django.contrib import messages
from django.http.response import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from sendfile import sendfile
from bpp.models.struktura import Wydzial
from eksport_pbn.models import PlikEksportuPBN
from eksport_pbn.tasks import eksport_pbn


class Generuj(LoginRequiredMixin, TemplateView):
    template_name = "generuj.html"

    def get(self, request, *args, **kwargs):
        wydzial = Wydzial.objects.get(pk=kwargs['wydzial'])
        rok = kwargs['rok']

        eksport_pbn.delay(self.request.user.pk, kwargs['wydzial'], kwargs['rok'])
        messages.info(self.request, u"Rozpoczęto generowanie eksportu PBN dla %s, rok %s" % (wydzial.nazwa, rok))
        return HttpResponseRedirect("..")


class SerwujPlik(LoginRequiredMixin, DetailView):
    template_name = "generuj.html"
    model = PlikEksportuPBN

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.owner == self.request.user:
            return sendfile(self.request,
                            self.object.file.path,
                            attachment=True,
                            attachment_filename="XML-%s-%s.zip" % (
                                self.object.wydzial.skrot, self.object.rok),
                            mimetype="application/octet-stream")

        return HttpResponseForbidden


class WyborWydzialu(LoginRequiredMixin, ListView):
    model = Wydzial
    template_name = "wydzial_list.html"

    def get_context_data(self, **kwargs):
        return super(WyborWydzialu, self).get_context_data(**{
            'lata': [2013, 2014, 2015],
            'ostatnie_raporty': PlikEksportuPBN.objects.filter(owner=self.request.user).order_by('-pk')[:10]
        })
