from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views.generic import CreateView, DetailView, ListView

from long_running.tasks import perform_generic_long_running_task


class LongRunningTaskCallerMixin:
    task = perform_generic_long_running_task

    def task_on_commit(self, pk):
        ct = ContentType.objects.get_for_model(self.model)

        transaction.on_commit(lambda: self.task.delay(ct.app_label, ct.model, pk))


class RestrictToOwnerMixin(LoginRequiredMixin):
    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)


class LongRunningOperationsView(RestrictToOwnerMixin, ListView):
    max_previous_ops = 10

    def get_queryset(self):
        with transaction.atomic():
            for elem in self.model.objects.filter(owner=self.request.user)[10:]:
                elem.delete()
        return RestrictToOwnerMixin.get_queryset(self)


class LongRunningDetailsView(RestrictToOwnerMixin, DetailView):
    def get_context_data(self, **kwargs):
        return super(LongRunningDetailsView, self).get_context_data(
            extraChannels=[self.object.pk], **kwargs
        )


class CreateLongRunningOperationView(
    LoginRequiredMixin, LongRunningTaskCallerMixin, CreateView
):
    def form_valid(self, form):
        form.instance.owner = self.request.user
        self.object = form.save()
        self.task_on_commit(pk=form.instance.pk)
        return HttpResponseRedirect(self.get_success_url())


class RestartLongRunningOperationView(
    RestrictToOwnerMixin, LongRunningTaskCallerMixin, DetailView
):
    task = perform_generic_long_running_task

    @transaction.atomic
    def get(self, *args, **kw):
        self.object = self.get_object()
        if self.object.finished_on is not None:
            self.object.mark_reset()
            self.task_on_commit(pk=self.object.pk)
        return HttpResponseRedirect("..")
