# -*- encoding: utf-8 -*-

import os

from braces.views import LoginRequiredMixin
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from crispy_forms_foundation.layout import Layout, Fieldset, Hidden
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.utils.functional import cached_property
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from egeria import tasks
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Update, Diff_Autor_Delete
from egeria.models.core import EgeriaImport, EgeriaRow
from egeria.models.funkcja_autora import Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete
from egeria.models.jednostka import Diff_Jednostka_Delete, Diff_Jednostka_Update, Diff_Jednostka_Create
from egeria.models.tytul import Diff_Tytul_Create, Diff_Tytul_Delete
from egeria.models.wydzial import Diff_Wydzial_Create, Diff_Wydzial_Delete
from notifications import send_redirect


class EgeriaImportListView(LoginRequiredMixin, ListView):
    model = EgeriaImport

    def get(self, request, *args, **kwargs):
        if request.GET.has_key("delete"):
            obj = None
            try:
                obj = EgeriaImport.objects.get(pk=request.GET['delete'])
            except (TypeError, EgeriaImport.DoesNotExist):
                pass

            if obj:
                if obj.created_by == request.user:
                    try:
                        os.unlink(obj.file.path)
                    except IOError:
                        pass
                    obj.cleanup()
                    obj.delete()

        return super(EgeriaImportListView, self).get(request, *args, **kwargs)


class DiffListViewBase(LoginRequiredMixin, ListView):
    """
    Bazowa klasa widoku obsługująca podgląd diffów.

    Jeżeli atrybut klasy "display_submit_button" jest ustawiony jako True, wyświetla przycisk
    "Zatwierdź". Jeżeli nie, to będzie wyświetlony przycisk "Następny". Jeden i drugi przycisk
    powodują przejście do następnego kroku
    """

    template_name = "egeria/diff_list_simple.html"
    ask_on_submit = True

    def on_submit(self, request):
        tasks.next_import_step(
            self.parent.pk,
            request.user.username,
            self.get_next_url(),
            request.GET['messageId'])

    def get(self, request, *args, **kwargs):
        try:
            self.parent
        except EgeriaImport.DoesNotExist:
            raise Http404

        self.object_list = self.get_queryset()

        if request.GET.has_key("submit"):
            self.on_submit(request)
            return HttpResponse("K")

        return super(DiffListViewBase, self).get(request, *args, **kwargs)

    @cached_property
    def parent(self):
        return EgeriaImport.objects.get(pk=self.kwargs['pk'])

    def get_queryset(self):
        return self.model.objects.filter(parent=self.parent).select_related()

    def get_context_data(self, **kwargs):
        return super(DiffListViewBase, self).get_context_data(
            this_title=self.title,
            list_label=self.list_label,
            parent=self.parent,
            ask_on_submit=self.ask_on_submit,
            next_url=self.get_next_url(),
            **kwargs)

    def get_next_url(self):
        return reverse(self.next_url, args=(self.parent.pk,))


class DontReallySubmitMixin:
    ask_on_submit = False
    def on_submit(self, request):
        send_redirect(request.user.username, self.get_next_url(), request.GET['messageId'])


class Diff_Tytul_CreateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "nowe tytuły"
    list_label = "Nowe tytuły, które zostaną dodane do bazy:"
    model = Diff_Tytul_Create
    next_url = "egeria:diff_tytul_delete"


class Diff_Tytul_DeleteListView(DiffListViewBase):
    title = "usuwane tytuły"
    list_label = "Nieużywane tytuły, które zostaną usunięte:"
    model = Diff_Tytul_Delete
    next_url = "egeria:diff_funkcja_create"


class Diff_Funkcja_Autora_CreateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "nowe funkcje autorów w jednostkach"
    list_label = title.capitalize() + ", które zostaną dodane do bazy:"
    model = Diff_Funkcja_Autora_Create
    next_url = "egeria:diff_funkcja_delete"


class Diff_Funkcja_Autora_DeleteListView(DiffListViewBase):
    title = "zbędne funkcje autorów w jednostkach"
    list_label = title.capitalize() + ", które zostaną usunięte:"
    model = Diff_Funkcja_Autora_Delete
    next_url = "egeria:diff_wydzial_create"


class Diff_Wydzial_CreateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "nowe wydziały"
    list_label = title.capitalize() + ", które zostaną dodane do bazy:"
    model = Diff_Wydzial_Create
    next_url = "egeria:diff_wydzial_delete"


class Diff_Wydzial_DeleteListView(DiffListViewBase):
    title = "zbędne wydziały"
    list_label = title.capitalize() + ", które zostaną ukryte lub usunięte:"
    model = Diff_Wydzial_Delete
    next_url = "egeria:diff_jednostka_create"


class Diff_Jednostka_CreateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "nowe jednostki"
    list_label = title.capitalize() + ", które zostaną dodane do bazy:"
    model = Diff_Jednostka_Create
    next_url = "egeria:diff_jednostka_update"
    template_name = "egeria/diff_list_jednostka_create.html"


class Diff_Jednostka_UpdateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "aktualizowane jednostki"
    list_label = title.capitalize() + ", które zostaną zaktualizowane w bazie:"
    model = Diff_Jednostka_Update
    next_url = "egeria:diff_jednostka_delete"
    template_name = "egeria/diff_list_jednostka_update.html"


class Diff_Jednostka_DeleteListView(DiffListViewBase):
    title = "zbędne jednostki"
    list_label = title.capitalize() + ", które zostaną ukryte lub usunięte:"
    model = Diff_Jednostka_Delete
    next_url = "egeria:diff_autor_create"
    template_name = "egeria/diff_list_jednostka_delete.html"



class Diff_Autor_CreateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "nowi autorzy"
    list_label = title.capitalize() + ", którzy zostaną dodani do bazy:"
    model = Diff_Autor_Create
    next_url = "egeria:diff_autor_update"
    template_name = "egeria/diff_list_autor_create.html"


class Diff_Autor_UpdateListView(DontReallySubmitMixin, DiffListViewBase):
    title = "aktualizowani autorzy"
    list_label = title.capitalize() + ", którzy zostaną zaktualizowani w bazie:"
    model = Diff_Autor_Update
    next_url = "egeria:diff_autor_delete"
    template_name = "egeria/diff_list_autor_update.html"

    # def get_queryset(self):
    #     if self.request.GET.has_key("no_pesel")
    #     return super(Diff_Autor_UpdateListView, self).get_queryset().exclude(
    #         ~Q(reference__pesel_md5=F('pesel_md5'))
    #     )


class Diff_Autor_DeleteListView(DiffListViewBase):
    title = "zbędni autorzy"
    list_label = title.capitalize() + ', którzy zostaną ukryci, usunięci lub dodani do "Obcej jednostki"'
    model = Diff_Autor_Delete
    next_url = "egeria:results"
    template_name = "egeria/diff_list_autor_delete.html"

class ResultsView(DiffListViewBase):
    title = "Rezultaty integracji"
    list_label = "Rekordy niezmatchowane"
    template_name = "egeria/results.html"
    model = EgeriaRow

    @cached_property
    def parent(self):
        return EgeriaImport.objects.get(pk=self.kwargs['pk'])

    def get_queryset(self):
        return self.parent.unmatched()

    def get_next_url(self):
        return reverse("egeria:main")


class ResetImportStateView(LoginRequiredMixin, DetailView):
    model = EgeriaImport
    template_name = "egeria/reset_import_state.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.created_by != request.user:
            return HttpResponseForbidden("!")

        messageId = getattr(request, request.method).get('messageId')

        if messageId is not None:
            tasks.reset_import_state.delay(
                self.object.pk,
                request.user.username,
                messageId)

            return HttpResponse("K")

        return super(ResetImportStateView, self).get(request, *args, **kwargs)


class EgeriaImportCreateView(LoginRequiredMixin, CreateView):
    model = EgeriaImport
    fields = ['file']

    def get_success_url(self):
        return reverse("egeria:main") + "?hilite=%s" % self.object.pk

    def get_form(self, form_class=None):
        form = super(EgeriaImportCreateView, self).get_form(form_class)
        form.helper = FormHelper()
        form.helper.layout = Layout(
            Fieldset('Dodaj nowy plik importu',
                     'file',
                     ))
        form.helper.add_input(Hidden("messageId", "123"))  # Wypełni później JavaScript
        form.helper.add_input(Submit('submit', 'Utwórz import osób', css_class='submit button'))
        return form

    def form_valid(self, *args, **kw):
        ret = super(EgeriaImportCreateView, self).form_valid(*args, **kw)
        self.object.created_by = self.request.user
        self.object.save()
        tasks.analyze_egeriaimport.delay(self.object.pk)
        return ret


class EgeriaImportDetailView(LoginRequiredMixin, DetailView):
    model = EgeriaImport

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.analyzed:
            args = (self.object.pk,)
            return HttpResponseRedirect(reverse("egeria:diff_tytul_create", args=args))

        return super(EgeriaImportDetailView, self).get(request, *args, **kwargs)
