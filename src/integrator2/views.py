from braces.views import GroupRequiredMixin
from django.db import transaction
from django.views.generic.edit import FormView
from django.views.generic.list import ListView

from integrator2.forms import FormListaMinisterialna
from integrator2.models.lista_ministerialna import ListaMinisterialnaIntegration
from integrator2.tasks import analyze_file

from django.contrib import messages

from django.utils.functional import cached_property

from bpp.const import GR_WPROWADZANIE_DANYCH


class Main(GroupRequiredMixin, ListView):
    paginate_by = 10
    group_required = GR_WPROWADZANIE_DANYCH
    template_name = "main.html"

    def get_queryset(self):
        return ListaMinisterialnaIntegration.objects.filter(
            owner=self.request.user
        ).order_by("-uploaded_on")


class UploadListaMinisterialna(GroupRequiredMixin, FormView):
    group_required = GR_WPROWADZANIE_DANYCH
    template_name = "new.html"
    form_class = FormListaMinisterialna
    success_url = ".."

    def form_valid(self, form):
        form.instance.owner = self.request.user
        self.object = form.save()
        messages.add_message(
            self.request, messages.INFO, "Plik został dodany do kolejki przetwarzania."
        )
        transaction.on_commit(lambda: analyze_file.delay(self.object.pk))
        return super(FormView, self).form_valid(form)


class DetailBase(GroupRequiredMixin, ListView):
    # def get_template_names(self):
    #     return [self.kwargs['model_name'] + "_detail.html"]

    paginate_by = 100

    group_required = GR_WPROWADZANIE_DANYCH

    @cached_property
    def object(self):
        return self.get_object()

    def get_object(self):
        from django.apps import apps

        model = apps.get_model(
            app_label="integrator2", model_name=self.kwargs["model_name"]
        )
        return model.objects.get(pk=self.kwargs["pk"], owner=self.request.user)

    def get_queryset(self):
        return self.object.not_integrated().order_by("nazwa")

    def get_context_data(self, **kwargs):
        return super().get_context_data(object=self.object, **kwargs)
