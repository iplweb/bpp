# Create your views here.
from braces.views import GroupRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views import generic

from ewaluacja2021.forms import ImportMaksymalnychSlotowForm
from ewaluacja2021.models import ImportMaksymalnychSlotow
from long_running.tasks import perform_generic_long_running_task

from bpp.models.const import GR_WPROWADZANIE_DANYCH


class NowyImport(GroupRequiredMixin, generic.CreateView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ImportMaksymalnychSlotow
    form_class = ImportMaksymalnychSlotowForm

    def form_valid(self, form):
        self.object = form.save()
        transaction.on_commit(
            lambda: perform_generic_long_running_task.delay(
                "ewaluacja2021", "ImportMaksymalnychSlotow".lower(), self.object.pk
            )
        )
        return HttpResponseRedirect(self.get_success_url())


class SzczegolyImportu(GroupRequiredMixin, generic.DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ImportMaksymalnychSlotow


class ListaImportow(GroupRequiredMixin, generic.ListView):
    group_required = GR_WPROWADZANIE_DANYCH

    model = ImportMaksymalnychSlotow
