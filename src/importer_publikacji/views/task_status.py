"""Widok statusu Celery task-a dla wizard-a importera.

Source of truth dla "done/failed" to session.status. AsyncResult używamy
TYLKO dla task.info (progress meta). Powód: race condition gdy task w
Redis już SUCCESS, ale session.save() jeszcze nie zafiałduje w DB.
"""

from celery.result import AsyncResult
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views import View

from ..models import ImportSession
from ..permissions import ImporterPermissionMixin

TERMINAL_STATUSES = {
    ImportSession.Status.FETCHED,
    ImportSession.Status.VERIFIED,
    ImportSession.Status.SOURCE_MATCHED,
    ImportSession.Status.AUTHORS_MATCHED,
    ImportSession.Status.REVIEW,
    ImportSession.Status.COMPLETED,
    ImportSession.Status.CANCELLED,
}


class ImportTaskStatusView(ImporterPermissionMixin, View):
    """GET — renderuje partial postępu (HTMX) lub pełną stronę."""

    def get(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)
        is_htmx = request.headers.get("HX-Request") == "true"

        if session.status == ImportSession.Status.IMPORT_FAILED:
            return self._render_error(request, session, is_htmx)

        if session.status in TERMINAL_STATUSES:
            return self._redirect_to_continue(session, is_htmx)

        info = None
        if session.celery_task_id:
            task = AsyncResult(session.celery_task_id)
            if isinstance(task.info, dict):
                info = task.info

        return self._render_progress(request, session, info, is_htmx)

    def _render_error(self, request, session, is_htmx):
        template = (
            "importer_publikacji/partials/task_error.html"
            if is_htmx
            else "importer_publikacji/step_task_status.html"
        )
        return render(request, template, {"session": session})

    def _redirect_to_continue(self, session, is_htmx):
        url = session.get_continue_url()
        if url is None:
            from django.urls import reverse

            url = reverse("importer_publikacji:index")
        if is_htmx:
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)

    def _render_progress(self, request, session, info, is_htmx):
        ctx = {"session": session, "info": info}
        template = (
            "importer_publikacji/partials/task_progress.html"
            if is_htmx
            else "importer_publikacji/step_task_status.html"
        )
        return render(request, template, ctx)
