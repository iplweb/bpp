"""
CBV mixins for LiveOperation views.

BaseLiveOperationMixin — login-required + owner-scoped queryset + optional
group gate (LIVE_OPERATIONS["REQUIRED_GROUP"]).  All views inherit from it.

Consumer apps subclass these views, set model/form_class, and register their
own URL patterns under app_name="live_operations".  See tests/urls.py for an
example.
"""
from __future__ import annotations

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from django.views.generic.detail import SingleObjectMixin

from live_operations.conf import get_setting


class BaseLiveOperationMixin(AccessMixin):
    """
    Owner-scoped, login-required base for all LiveOperation views.

    - Unauthenticated → redirect to login (via AccessMixin.handle_no_permission).
    - Authenticated but wrong group → 403.
    - Queryset always filtered to owner=request.user (prevents cross-user leaks).
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        required_group = get_setting("REQUIRED_GROUP")
        if required_group and not request.user.groups.filter(
            name=required_group
        ).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model._default_manager.filter(owner=self.request.user)


class CreateLiveOperationView(BaseLiveOperationMixin, CreateView):
    """Create a new LiveOperation, assign owner, enqueue, redirect to live page."""

    def form_valid(self, form):
        form.instance.owner = self.request.user
        self.object = form.save()
        self.object.enqueue()
        return redirect(self.object.get_absolute_url())


class LiveOperationView(BaseLiveOperationMixin, DetailView):
    """
    Live host page for a running or finished operation.

    Template order: object.get_host_template_name() → live_operations/operation.html.
    For finished operations the result is rendered inline (deep-link / refresh).
    """

    def get_template_names(self):
        return [self.object.get_host_template_name(), "live_operations/operation.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["base_template"] = get_setting("BASE_TEMPLATE")
        return ctx


class LiveOperationListView(BaseLiveOperationMixin, ListView):
    """List all operations owned by the current user."""

    template_name = "live_operations/operation_list.html"
    context_object_name = "operations"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["base_template"] = get_setting("BASE_TEMPLATE")
        return ctx


class CancelView(BaseLiveOperationMixin, SingleObjectMixin, View):
    """POST-only: set cancel_requested=True and redirect to live page."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        operation = self.get_object()
        operation.cancel_requested = True
        operation.save(update_fields=["cancel_requested"])
        return redirect(operation.get_absolute_url())


class RestartView(BaseLiveOperationMixin, SingleObjectMixin, View):
    """POST-only: reset terminal state, re-enqueue, redirect to live page."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        operation = self.get_object()
        operation.finished_on = None
        operation.started_on = None
        operation.finished_successfully = False
        operation.cancelled = False
        operation.cancel_requested = False
        operation.traceback = None
        operation.result_context = None
        operation.save(
            update_fields=[
                "finished_on",
                "started_on",
                "finished_successfully",
                "cancelled",
                "cancel_requested",
                "traceback",
                "result_context",
            ]
        )
        operation.enqueue()
        return redirect(operation.get_absolute_url())
