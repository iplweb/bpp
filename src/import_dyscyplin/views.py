from braces.views import GroupRequiredMixin, JSONResponseMixin
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView
from django.views.generic.edit import BaseDeleteView

from bpp.models.const import GR_WPROWADZANIE_DANYCH
from import_dyscyplin.tasks import przeanalizuj_import_dyscyplin
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


class DetailImport_Dyscyplin(GroupRequiredMixin, TylkoMojeMixin, DetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin

    def get_context_data(self, **kwargs):
        return super(DetailImport_Dyscyplin, self).get_context_data(
            notification=self.request.GET.get("notification", "0"),
            **kwargs)


class UruchomPrzetwarzanieImport_Dyscyplin(GroupRequiredMixin, TylkoMojeMixin, DetailView, JSONResponseMixin):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Import_Dyscyplin

    def get_queryset(self):
        return super(TylkoMojeMixin, self).get_queryset().filter(stan=Import_Dyscyplin.STAN.NOWY)

    def get(self, *args, **kw):
        self.object = self.get_object()
        self.object.web_page_uid = self.request.GET.get("web_page_uid", "")
        self.object.save()

        przeanalizuj_import_dyscyplin.delay(self.object.pk)
        return self.render_json_response({"status": "ok"})


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