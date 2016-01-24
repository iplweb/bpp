# -*- encoding: utf-8 -*-
from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from integrator2.tasks import analyze_file

from integrator2.models import IntegrationFile
from integrator_OLD_UNUSED.forms import DodajPlik, DodajPlikListyMinisterialnej


class FileListView(GroupRequiredMixin, ListView):
    model = IntegrationFile
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

class FileListaMinisterialnaUploadView(FileUploadView):
    form_class = DodajPlikListyMinisterialnej


class AutorIntegrationFileDetail(GroupRequiredMixin, DetailView):
    model = IntegrationFile
    group_required = "wprowadzanie danych"
