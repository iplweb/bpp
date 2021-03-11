from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.functional import cached_property
from django.views.generic import CreateView, DetailView, ListView

from long_running import const
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


class LongRunningSingleObjectChannelSubscriberMixin:
    def get_context_data(self, **kwargs):
        return super(
            LongRunningSingleObjectChannelSubscriberMixin, self
        ).get_context_data(extraChannels=[self.object.pk], **kwargs)


class LongRunningRouterView(
    RestrictToOwnerMixin, LongRunningSingleObjectChannelSubscriberMixin, DetailView
):
    """You can mount this view somewhere on an url with a pk (an uuid) of
    an Operation and it will try routing to either a web page with the progress
    report, or in case operation finishes, to a result page (or an error page...)"""

    redirect_prefix = None

    STATE_TO_SUFFIX_MAP = {
        const.PROCESSING_STARTED: "details",
        const.PROCESSING_FINISHED_WITH_ERROR: "details",
        const.PROCESSING_FINISHED_SUCCESSFULLY: "results",
    }

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data()
        state = self.object.get_state()

        if state == const.PROCESSING_NOT_STARTED:
            # If not started, redirect to itself but after a few seconds
            return TemplateResponse(
                request=self.request,
                template="long_running/router_view_wait.html",
                context=context,
            )

        suffix = self.STATE_TO_SUFFIX_MAP.get(state)

        url = self.object.get_url(suffix)

        return HttpResponseRedirect(url)


class LongRunningDetailsView(
    RestrictToOwnerMixin, LongRunningSingleObjectChannelSubscriberMixin, DetailView
):
    pass


class LongRunningResultsView(ListView):
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
        return super(LongRunningResultsView, self).get_context_data(
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
    # task = perform_generic_long_running_task

    @transaction.atomic
    def get(self, *args, **kw):
        self.object = self.get_object()
        if self.object.finished_on is not None:
            self.object.mark_reset()
            self.task_on_commit(pk=self.object.pk)
        return HttpResponseRedirect("..")
