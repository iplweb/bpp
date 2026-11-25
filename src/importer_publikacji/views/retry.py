"""Endpoint do retry-owania task-a importera publikacji po błędzie."""

import uuid

from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.views import View

from ..models import ImportSession
from ..permissions import ImporterPermissionMixin
from ..tasks import create_publication_task, fetch_session_task


class ImportTaskRetryView(ImporterPermissionMixin, View):
    """POST — wyczyść state błędu, enqueueuj odpowiedni task ponownie."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)

        if session.status != ImportSession.Status.IMPORT_FAILED:
            return HttpResponseBadRequest(
                "Retry można wywołać tylko na sesji w stanie IMPORT_FAILED."
            )

        failed_stage = session.last_failed_stage

        session.last_error_message = ""
        session.last_error_traceback = ""
        session.last_failed_stage = ""

        if failed_stage == "fetch":
            # FD#512: poprzednie zadanie mogło jeszcze nie skończyć (strażnik
            # uznał je za zawieszone, a ono czeka na wolne źródło). Blokada
            # wiersza sesji + nowy identyfikator zadania zapisany w TEJ SAMEJ
            # transakcji, przed wysłaniem: stare zadanie albo dokończy swój
            # zapis przed nami (i zaraz go skasujemy), albo zobaczy, że sesja
            # ma nowego właściciela, i wycofa się bez zapisu.
            with transaction.atomic():
                ImportSession.objects.select_for_update().get(pk=session.pk)
                session.authors.all().delete()
                session.raw_data = {}
                session.normalized_data = {}
                session.status = ImportSession.Status.FETCHING
                session.celery_task_id = str(uuid.uuid4())
                session.save()

            fetch_session_task.apply_async(
                args=[session.pk, request.user.pk], task_id=session.celery_task_id
            )

        elif failed_stage == "create":
            session.created_record_content_type = None
            session.created_record_id = None
            session.status = ImportSession.Status.CREATING
            session.save()

            # Read PBN export preference from session. CreateView.post must persist
            # matched_data["pbn_export_pending"] = also_pbn when user clicks
            # "Utwórz + PBN" so this retry respects the original choice. Defaults
            # to False until that wiring lands (Task 12).
            also_pbn = bool(session.matched_data.get("pbn_export_pending", False))
            task = create_publication_task.delay(session.pk, request.user.pk, also_pbn)
            session.celery_task_id = task.id
            session.save(update_fields=["celery_task_id"])

        else:
            return HttpResponseBadRequest(f"Nieznany last_failed_stage: {failed_stage}")

        return redirect("importer_publikacji:task-status", session_id=session.pk)

    def get(self, request, session_id):
        return HttpResponseNotAllowed(["POST"])
