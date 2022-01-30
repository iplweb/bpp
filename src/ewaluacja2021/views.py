# Create your views here.
from datetime import timedelta

from braces.views import GroupRequiredMixin
from denorm.models import DirtyInstance
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views import generic

from ewaluacja2021.forms import ImportMaksymalnychSlotowForm, ZamowienieNaRaportForm
from ewaluacja2021.models import ImportMaksymalnychSlotow, ZamowienieNaRaport
from ewaluacja2021.tasks import generuj_algorytm, suma_odpietych_dyscyplin
from long_running.tasks import perform_generic_long_running_task

from django.utils import timezone

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


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

    def get(self, request, *args, **kwargs):

        if request.GET.get("resetuj") == "1" and request.user.is_staff:
            with transaction.atomic():
                for klass in (
                    Wydawnictwo_Ciagle_Autor,
                    Wydawnictwo_Zwarte_Autor,
                    Patent_Autor,
                ):
                    klass.objects.exclude(dyscyplina_naukowa=None).filter(
                        przypieta=False
                    ).update(przypieta=True)

            return HttpResponseRedirect(".")

        tydzien_temu = timezone.now() - timedelta(days=5)
        ZamowienieNaRaport.objects.filter(
            ostatnio_zmodyfikowany__lte=tydzien_temu
        ).delete()

        return super().get(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        return super().get_context_data(
            object_list=object_list,
            ilosc_odpietych_dyscyplin=suma_odpietych_dyscyplin(),
            ilosc_elementow_w_kolejce=DirtyInstance.objects.count(),
            **kwargs,
        )


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
