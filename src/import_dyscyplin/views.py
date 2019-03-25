from braces.views import GroupRequiredMixin, JSONResponseMixin
from celery import uuid
from celery.result import AsyncResult
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.views.generic.detail import BaseDetailView
from django.views.generic.edit import BaseDeleteView

from bpp.models.const import GR_WPROWADZANIE_DANYCH
from import_dyscyplin.forms import Import_Dyscyplin_KolumnaForm, KolumnaFormSet, KolumnaFormSetHelper
from import_dyscyplin.tasks import przeanalizuj_import_dyscyplin, integruj_import_dyscyplin, stworz_kolumny
from .forms import Import_DyscyplinForm
from .models import Import_Dyscyplin


class WprowadzanieDanychRequiredMixin(GroupRequiredMixin):
    group_required = GR_WPROWADZANIE_DANYCH


class TylkoMojeMixin:
    def get_queryset(self):
        return Import_Dyscyplin.objects.filter(owner=self.request.user)


class ListImport_Dyscyplin(GroupRequiredMixin, TylkoMojeMixin, ListView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin


class CreateImport_Dyscyplin(GroupRequiredMixin, CreateView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    form_class = Import_DyscyplinForm

    def get_success_url(self):
        return reverse("import_dyscyplin:detail", args=(self.object.pk,))

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class KolumnyImport_Dyscyplin(GroupRequiredMixin, TylkoMojeMixin, UpdateView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    template_name = "import_dyscyplin/import_dyscyplin_kolumny.html"
    form_class = Import_Dyscyplin_KolumnaForm

    def get_context_data(self, **kwargs):
        data = super(KolumnyImport_Dyscyplin, self).get_context_data(**kwargs)
        if self.request.POST:
            data['kolumny'] = KolumnaFormSet(self.request.POST)
        else:
            data['kolumny'] = KolumnaFormSet()
        return data

    def get_context_data(self, **kwargs):
        context = super(KolumnyImport_Dyscyplin, self).get_context_data(**kwargs)
        if self.request.POST:
            context['kolumny_formset'] = KolumnaFormSet(self.request.POST, instance=self.object)
            context['kolumny_formset'].full_clean()
        else:
            context['kolumny_formset'] = KolumnaFormSet(instance=self.object)
        context['kolumny_formset_helper'] = KolumnaFormSetHelper()
        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data(form=form)
        formset = context['kolumny_formset']
        if formset.is_valid():
            self.object.zatwierdz_kolumny()

            response = super().form_valid(form)

            formset.instance = self.object
            formset.save()
            return response
        else:
            return super().form_invalid(form)

    def get_success_url(self):
        return reverse("import_dyscyplin:detail", args=(self.object.pk,))


class DetailImport_Dyscyplin(GroupRequiredMixin, TylkoMojeMixin, DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin

    def get_context_data(self, **kwargs):
        return super(DetailImport_Dyscyplin, self).get_context_data(
            notification=self.request.GET.get("notification", "0"),
            **kwargs)


class UruchomZadaniePrzetwarzania(GroupRequiredMixin, TylkoMojeMixin, DetailView, JSONResponseMixin):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    task = None
    stan = None

    def get_queryset(self):
        return super(TylkoMojeMixin, self).get_queryset().filter(stan=self.stan)

    def get(self, *args, **kw):
        self.object = self.get_object()
        self.object.web_page_uid = self.request.GET.get("web_page_uid", "")

        start_task = False
        if self.object.task_id is None \
                or AsyncResult(self.object.task_id).status == "PENDING":
            start_task = True
            self.object.task_id = task_id = uuid()

        self.object.save()

        if start_task:
            transaction.on_commit(
                lambda self=self: self.task.apply_async(
                    args=(self.object.pk,),
                    task_id=task_id
                )
            )

        return self.render_json_response({"status": "ok"})


class UruchomTworzenieKolumnImport_Dyscyplin(UruchomZadaniePrzetwarzania):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    task = stworz_kolumny
    stan = Import_Dyscyplin.STAN.NOWY


class UruchomPrzetwarzanieImport_Dyscyplin(UruchomZadaniePrzetwarzania):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    task = przeanalizuj_import_dyscyplin
    stan = Import_Dyscyplin.STAN.OPCJE_IMPORTU_OKRESLONE


class UruchomIntegracjeImport_DyscyplinView(UruchomZadaniePrzetwarzania):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin
    task = integruj_import_dyscyplin
    stan = Import_Dyscyplin.STAN.PRZEANALIZOWANY


class UsunImport_Dyscyplin(WprowadzanieDanychRequiredMixin, TylkoMojeMixin, BaseDeleteView):
    success_url = reverse_lazy("import_dyscyplin:index")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        transaction.on_commit(
            lambda: messages.add_message(
                self.request,
                messages.INFO,
                'Plik importu dyscyplin "%s" został usunięty.' % self.object.plik.name)
        )
        return super(UsunImport_Dyscyplin, self).delete(request, *args, **kwargs)

    get = delete


class API_Do_IntegracjiView(WprowadzanieDanychRequiredMixin, TylkoMojeMixin, JSONResponseMixin, BaseDetailView):
    func = "poprawne_wiersze_do_integracji"

    def get(self, *args, **kw):
        self.object = self.get_object()

        fn = getattr(self.object, self.func)()

        fn_filtered = fn
        search = self.request.GET.get("search[value]", "")
        if search:
            fn_filtered = fn_filtered.filter(
                Q(nazwisko__icontains=search) |
                Q(imiona__icontains=search) |
                Q(original__nazwa_jednostki__icontains=search) |
                Q(original__wydział__icontains=search) |
                Q(info__icontains=search) |
                Q(dyscyplina__icontains=search) |
                Q(subdyscyplina__icontains=search) |
                Q(kod_dyscypliny__icontains=search) |
                Q(kod_subdyscypliny__icontains=search)
            )

        start = int(self.request.GET.get("start", 0))
        draw = int(self.request.GET.get("draw", 1))
        length = int(self.request.GET.get("length", 10))

        ordering = int(self.request.GET.get("order[0][column]", 0))
        direction = self.request.GET.get("order[0][dir]", "asc")
        fld = self.request.GET.get("columns[%i][data]" % ordering, "dopasowanie_autora")
        if fld:
            ordering_mapping = {
                "dopasowanie_autora": "autor__nazwisko",
                "jednostka": "nazwa_jednostki",
                "wydzial": "nazwa_wydzialu",
                "dyscyplina": "dyscyplina__nazwa",
                "procent_dyscypliny": "procent_dyscypliny",
                "subdyscyplina": "subdyscyplina__nazwa",
                "procent_subdyscypliny": "procent_subdyscypliny"
            }
            fld = ordering_mapping.get(fld, fld)
        if direction != 'asc':
            fld = '-' + fld

        fn_output = fn_filtered
        if fld:
            fn_output = fn_output.order_by(fld)
        fn_output = fn_output[start:start + length]

        recordsTotal = fn.count()
        recordsFiltered = fn_filtered.count()
        return self.render_json_response(
            {
                "data": [x.serialize_dict() for x in fn_output],
                "draw": draw,
                "recordsTotal": recordsTotal,
                "recordsFiltered": recordsFiltered,
            }
        )


class API_Nie_Do_IntegracjiView(API_Do_IntegracjiView):
    func = "niepoprawne_wiersze"


class API_Zintegrowane(API_Do_IntegracjiView):
    func = "zintegrowane_wiersze"
