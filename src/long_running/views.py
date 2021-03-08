from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.utils.functional import cached_property
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
        qset = RestrictToOwnerMixin.get_queryset(self).order_by("-last_updated_on")

        # Skasju poprzednie operacje
        for elem in qset[self.max_previous_ops :]:
            elem.delete()

        return qset


# class DetailListView(ListView):
#     detail_context_object_name = 'object'
#
#     def get(self, request, *args, **kwargs):
#         self.object = self.get_object()
#         return super(DetailListView, self).get(request, *args, **kwargs)
#
#     def get_queryset_for_object(self):
#         raise NotImplementedError('You need to provide the queryset for the object')
#
#     def get_object(self):
#         queryset = self.get_queryset_for_object()
#         DetailView.get_object(self, queryset)
#         pk = self.kwargs.get('pk')
#         if pk is None:
#             raise AttributeError('pk expected in url')
#         return get_object_or_404(queryset, pk=pk)
#
#     def get_context_data(self, **kwargs):
#         context = super(DetailListView, self).get_context_data(**kwargs)
#         context[self.detail_context_object_name] = self.object
#         return context


class LongRunningDetailsView(ListView):
    paginate_by = 25

    @cached_property
    def parent_object(self):
        o = self.model.objects.get(pk=self.kwargs["pk"])
        if o.owner != self.request.user:
            raise Http404
        return o

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def get_context_data(self, **kwargs):
        return super(LongRunningDetailsView, self).get_context_data(
            extraChannels=[self.parent_object.pk], object=self.parent_object, **kwargs
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
