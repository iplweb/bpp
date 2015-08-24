# -*- encoding: utf-8 -*-
from braces.views import GroupRequiredMixin

from django.contrib import messages
from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from integrator.forms import DodajPlik

from integrator.models import AutorIntegrationFile

from integrator.tasks import analyze_file


class FileListView(GroupRequiredMixin, ListView):
    model = AutorIntegrationFile
    paginate_by = 20

    group_required = "wprowadzanie danych"

    def get_queryset(self):
        return self.model.objects.all().filter(owner=self.request.user)


class FileUploadView(GroupRequiredMixin, FormView):
    form_class = DodajPlik
    success_url = '..'
    group_required = "wprowadzanie danych"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.save()
        analyze_file.apply_async((form.instance.pk,), countdown=1)
        messages.info(self.request,
                      "Plik został dodany. Będzie on przetwarzany. Zostaniesz poinformowany/a o rezultacie.")
        return super(FileUploadView, self).form_valid(form)


class AutorIntegrationFileDetail(GroupRequiredMixin, DetailView):
    model = AutorIntegrationFile
    group_required = "wprowadzanie danych"
