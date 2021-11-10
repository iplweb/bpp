# Create your views here.

from braces.views import GroupRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views import generic

from ewaluacja2021.forms import ImportMaksymalnychSlotowForm, ZamowienieNaRaportForm
from ewaluacja2021.models import ImportMaksymalnychSlotow, ZamowienieNaRaport
from ewaluacja2021.tasks import generuj_algorytm
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


class NowyRaport3N(GroupRequiredMixin, generic.CreateView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ZamowienieNaRaport
    form_class = ZamowienieNaRaportForm

    def form_valid(self, form):
        self.object = form.save()
        transaction.on_commit(lambda pk=self.object.pk: generuj_algorytm.delay(pk))
        return HttpResponseRedirect(self.get_success_url())


class SzczegolyRaportu3N(GroupRequiredMixin, generic.DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ZamowienieNaRaport


class ListaRaporto3N(GroupRequiredMixin, generic.ListView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ZamowienieNaRaport


class PlikRaportu3N(GroupRequiredMixin, generic.DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ZamowienieNaRaport

    def get(self, request, *args, **kw):
        from sendfile import sendfile

        self.object = self.get_object()
        return sendfile(
            request,
            self.object.plik_wyjsciowy.path,
            attachment=True,
            attachment_filename=self.object.plik_wyjsciowy.name,
        )


class WykresRaportu3N(GroupRequiredMixin, generic.DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = ZamowienieNaRaport

    def get(self, request, *args, **kw):
        from sendfile import sendfile

        self.object = self.get_object()
        return sendfile(
            request,
            self.object.wykres_wyjsciowy.path,
            attachment=True,
            attachment_filename=self.object.wykres_wyjsciowy.name,
        )
