# -*- encoding: utf-8 -*-


from braces.views import LoginRequiredMixin
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from crispy_forms_foundation.layout import Layout, Fieldset
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from egeria.models.core import EgeriaImport
from egeria.models.tytul import Diff_Tytul_Create
from egeria.tasks import analyze_egeriaimport


# Podgląd zanalizowanego pliku:
# PRZEKIEROWANIE do egeriaimport_detail:
# jeżeli analyzed to idzie do analysis_level_ileśtam
# gdzie tak na prawde jest to klasa wyświetlająca listę ewentualnei detale Diff_COSTAM_Update/create/delete
# z opcjonalnymi detalami wyświetlenia EgeriaRow

# TESTY bo potem mi się POPIERDOLI
# 1) tytuły: dodane, usuwane
# 2) stanowiska: dodane, usuwane
# 3) wydziały: dodane, usuwane
# 4) jednostki: dodane, aktualizowane, usuwane (3 ekrany)
# 5) autorzy: dodani, aktualizowani, usuwani (3 ekrany z przewijaniem)

class EgeriaImportListView(LoginRequiredMixin, ListView):
    model = EgeriaImport


class DiffListViewBase(LoginRequiredMixin, ListView):
    def get(self, request, *args, **kwargs):
        if request.GET.has_key("submit"):
            raise NotImplementedError
        elif request.GET.has_key("cancel"):
            raise NotImplementedError

        return super(DiffListViewBase, self).get(request, *args, **kwargs)


class Diff_Tytul_CreateListView(DiffListViewBase):
    def get_queryset(self):
        self.parent = EgeriaImport.objects.get(pk=self.kwargs['pk'])
        object_list = Diff_Tytul_Create.objects.filter(parent=self.parent)
        object_list.parent = self.parent
        return object_list

    def get_context_data(self, **kwargs):
        return super(Diff_Tytul_CreateListView, self).get_context_data(this_title="nowe tytuły", **kwargs)


class EgeriaImportCreateView(LoginRequiredMixin, CreateView):
    model = EgeriaImport
    fields = ['file']

    def get_form(self, form_class=None):
        form = super(EgeriaImportCreateView, self).get_form(form_class)
        form.helper = FormHelper()
        form.helper.layout = Layout(
            Fieldset('Dodaj nowy plik importu',
                     'file',
                     ))
        form.helper.add_input(Submit('submit', 'Utwórz import osób', css_class='submit button'))
        return form

    def form_valid(self, *args, **kw):
        ret = super(EgeriaImportCreateView, self).form_valid(*args, **kw)
        self.object.created_by = self.request.user
        self.object.save()
        analyze_egeriaimport.delay(self.object.pk)
        return ret


class EgeriaImportDetailView(LoginRequiredMixin, DetailView):
    model = EgeriaImport

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.analyzed:
            args = (self.object.pk,)
            return HttpResponseRedirect(reverse("egeria:diff_tytul_create", args=args))

        return super(EgeriaImportDetailView, self).get(request, *args, **kwargs)
