# -*- encoding: utf-8 -*-


from braces.views import LoginRequiredMixin
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit
from django.contrib import messages
from django.http.response import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from sendfile import sendfile
from eksport_pbn.forms import EksportDoPBNForm
from eksport_pbn.models import PlikEksportuPBN
from eksport_pbn.tasks import eksport_pbn


class Generuj(LoginRequiredMixin, TemplateView):
    template_name = "generuj.html"

    def get(self, request, *args, **kwargs):
        rok = kwargs["rok"]

        eksport_pbn.delay(self.request.user.pk, kwargs["rok"])
        messages.info(
            self.request, "Rozpoczęto generowanie eksportu PBN dla roku %s" % rok
        )
        return HttpResponseRedirect("..")


class SerwujPlik(LoginRequiredMixin, DetailView):
    template_name = "generuj.html"
    model = PlikEksportuPBN

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.owner == self.request.user:
            return sendfile(
                self.request,
                self.object.file.path,
                attachment=True,
                attachment_filename=self.object.get_fn() + ".zip",
                mimetype="application/octet-stream",
            )

        return HttpResponseForbidden


class ZamowEksportDoPBN(LoginRequiredMixin, FormView):
    form_class = EksportDoPBNForm
    template_name = "zamow.html"

    def get_context_data(self, **kwargs):
        return super(ZamowEksportDoPBN, self).get_context_data(
            ostatnie_raporty=PlikEksportuPBN.objects.filter(owner=self.request.user)
            .exclude(file="")
            .order_by("-pk")[:10],
        )

    def form_valid(self, form):
        obj = form.instance
        obj.owner = self.request.user
        obj.save()

        eksport_pbn.delay(obj.pk)
        messages.info(
            self.request,
            "Rozpoczęto generowanie eksportu PBN dla %s" % obj.get_rok_string(),
        )

        return HttpResponseRedirect(".")
