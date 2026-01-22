from io import BytesIO

from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from openpyxl import Workbook
from queryset_sequence import QuerySetSequence

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask
from pbn_wysylka_oswiadczen.queries import get_publications_queryset
from pbn_wysylka_oswiadczen.tasks import wysylka_oswiadczen_task


def group_required(group_name):
    """Custom decorator requiring user to be in specified group or be superuser."""

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())

            if (
                request.user.is_superuser
                or request.user.groups.filter(name=group_name).exists()
            ):
                return view_func(request, *args, **kwargs)
            else:
                from django.core.exceptions import PermissionDenied

                raise PermissionDenied("Nie masz uprawnien do dostepu do tej strony")

        return _wrapped_view

    return decorator


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class PbnWysylkaOswiadczenMainView(TemplateView):
    """Main dashboard for PBN statement sending."""

    template_name = "pbn_wysylka_oswiadczen/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Default parameters
        rok_od = int(self.request.GET.get("rok_od", 2022))
        rok_do = int(self.request.GET.get("rok_do", 2025))
        tytul = self.request.GET.get("tytul", "").strip()
        tylko_odpiete = self.request.GET.get("tylko_odpiete", "").lower() == "true"

        # Get publication counts
        ciagle_qs, zwarte_qs = get_publications_queryset(
            rok_od, rok_do, tytul or None, tylko_odpiete, with_annotations=True
        )
        ciagle_count = ciagle_qs.count()
        zwarte_count = zwarte_qs.count()

        # Calculate total oświadczeń (sum of liczba_oswiadczen across all publications)
        ciagle_oswiadczen = (
            ciagle_qs.aggregate(total=Sum("liczba_oswiadczen"))["total"] or 0
        )
        zwarte_oswiadczen = (
            zwarte_qs.aggregate(total=Sum("liczba_oswiadczen"))["total"] or 0
        )

        context["rok_od"] = rok_od
        context["rok_do"] = rok_do
        context["tytul"] = tytul
        context["tylko_odpiete"] = tylko_odpiete
        context["ciagle_count"] = ciagle_count
        context["zwarte_count"] = zwarte_count
        context["total_count"] = ciagle_count + zwarte_count
        context["total_oswiadczen"] = ciagle_oswiadczen + zwarte_oswiadczen

        # Add latest task information
        latest_task = PbnWysylkaOswiadczenTask.get_latest_task()
        context["latest_task"] = latest_task

        # Check if resuming is possible (there's a task with logs)
        context["can_resume"] = (
            latest_task
            and latest_task.logs.filter(status="success").exists()
            and latest_task.status in ("completed", "failed")
        )

        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class PublicationListView(TemplateView):
    """HTMX partial view for paginated publication list."""

    template_name = "pbn_wysylka_oswiadczen/_publication_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Parameters
        rok_od = int(self.request.GET.get("rok_od", 2022))
        rok_do = int(self.request.GET.get("rok_do", 2025))
        tytul = self.request.GET.get("tytul", "").strip()
        tylko_odpiete = self.request.GET.get("tylko_odpiete", "").lower() == "true"
        page = int(self.request.GET.get("page", 1))
        per_page = 50

        # Get publications
        ciagle_qs, zwarte_qs = get_publications_queryset(
            rok_od, rok_do, tytul or None, tylko_odpiete, with_annotations=True
        )

        # Combine querysets
        combined_qs = QuerySetSequence(ciagle_qs, zwarte_qs)

        # Paginate
        paginator = Paginator(combined_qs, per_page)
        page_obj = paginator.get_page(page)

        context["page_obj"] = page_obj
        context["rok_od"] = rok_od
        context["rok_do"] = rok_do
        context["tytul"] = tytul
        context["tylko_odpiete"] = tylko_odpiete

        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class TaskStatusView(View):
    """API view to check task status for HTMX polling."""

    def get(self, request):
        # Get latest task
        latest_task = PbnWysylkaOswiadczenTask.get_latest_task()

        # Check if any task is currently running
        is_running = PbnWysylkaOswiadczenTask.objects.filter(status="running").exists()

        response_data = {"is_running": is_running, "latest_task": None}

        if latest_task:
            response_data["latest_task"] = {
                "id": latest_task.id,
                "status": latest_task.status,
                "created_at": latest_task.created_at.isoformat(),
                "started_at": (
                    latest_task.started_at.isoformat()
                    if latest_task.started_at
                    else None
                ),
                "completed_at": (
                    latest_task.completed_at.isoformat()
                    if latest_task.completed_at
                    else None
                ),
                "error_message": latest_task.error_message,
                "user": latest_task.user.username,
                "total_publications": latest_task.total_publications,
                "processed_publications": latest_task.processed_publications,
                "current_publication": latest_task.current_publication,
                "progress_percent": latest_task.progress_percent,
                "success_count": latest_task.success_count,
                "error_count": latest_task.error_count,
                "skipped_count": latest_task.skipped_count,
                "last_updated": latest_task.last_updated.isoformat(),
                "is_stalled": latest_task.is_stalled(),
            }

        return JsonResponse(response_data)


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class StartTaskView(View):
    """API view to start statement sending task."""

    def post(self, request):
        # Check if user has PBN authorization
        user = request.user
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Nie jestes zalogowany w PBN. Prosze najpierw "
                    "zalogowac sie do PBN.",
                }
            )

        if not pbn_user.pbn_token_possibly_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": "Twoj token PBN wygasl. Prosze zalogowac sie "
                    "ponownie do PBN.",
                }
            )

        # Clean up stale running tasks
        PbnWysylkaOswiadczenTask.cleanup_stale_running_tasks()

        # Check if task is already running
        running_task = PbnWysylkaOswiadczenTask.objects.filter(status="running").first()
        if running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Zadanie wysylki jest juz uruchomione. "
                    "Prosze poczekac na jego zakonczenie.",
                }
            )

        # Get parameters
        rok_od = int(request.POST.get("rok_od", 2022))
        rok_do = int(request.POST.get("rok_do", 2025))
        tytul = request.POST.get("tytul", "").strip()
        resume_mode = request.POST.get("resume_mode", "false").lower() == "true"

        # Create task record
        task = PbnWysylkaOswiadczenTask.objects.create(
            user=user,
            status="pending",
            rok_od=rok_od,
            rok_do=rok_do,
            tytul=tytul,
            resume_mode=resume_mode,
        )

        # Start Celery task
        try:
            celery_result = wysylka_oswiadczen_task.delay(task.pk)
            task.celery_task_id = celery_result.id
            task.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Zadanie wysylki oswiadczen zostalo uruchomione.",
                    "task_id": task.pk,
                }
            )
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.save()
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Nie udalo sie uruchomic zadania: {str(e)}",
                }
            )


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class CancelTaskView(View):
    """API view to cancel a running task."""

    def post(self, request):
        running_task = PbnWysylkaOswiadczenTask.objects.filter(status="running").first()
        if not running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Brak uruchomionego zadania do anulowania.",
                }
            )

        running_task.status = "failed"
        running_task.error_message = "Zadanie anulowane przez uzytkownika"
        running_task.completed_at = timezone.now()
        running_task.save()

        return JsonResponse({"success": True, "message": "Zadanie zostalo anulowane."})


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class TaskStatusPartialView(TemplateView):
    """HTMX partial view for task status panel."""

    template_name = "pbn_wysylka_oswiadczen/_task_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["latest_task"] = PbnWysylkaOswiadczenTask.get_latest_task()
        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class LogListView(TemplateView):
    """View for browsing task logs."""

    template_name = "pbn_wysylka_oswiadczen/logs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        task_id = self.request.GET.get("task_id")
        status_filter = self.request.GET.get("status")
        page = int(self.request.GET.get("page", 1))
        per_page = 100

        logs_qs = PbnWysylkaLog.objects.all()

        if task_id:
            logs_qs = logs_qs.filter(task_id=task_id)
        if status_filter:
            logs_qs = logs_qs.filter(status=status_filter)

        logs_qs = logs_qs.select_related("task", "content_type")

        paginator = Paginator(logs_qs, per_page)
        page_obj = paginator.get_page(page)

        context["page_obj"] = page_obj
        context["task_id"] = task_id
        context["status_filter"] = status_filter
        context["tasks"] = PbnWysylkaOswiadczenTask.objects.all()[:20]

        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class LogDetailView(TemplateView):
    """View for log detail with JSON data."""

    template_name = "pbn_wysylka_oswiadczen/log_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log_id = kwargs.get("pk")
        context["log"] = PbnWysylkaLog.objects.select_related(
            "task", "content_type"
        ).get(pk=log_id)
        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class ExcelExportView(View):
    """Export filtered publications to Excel file."""

    def get(self, request):
        # Get filter parameters
        rok_od = int(request.GET.get("rok_od", 2022))
        rok_do = int(request.GET.get("rok_do", 2025))
        tytul = request.GET.get("tytul", "").strip()
        tylko_odpiete = request.GET.get("tylko_odpiete", "").lower() == "true"

        # Get publications
        ciagle_qs, zwarte_qs = get_publications_queryset(
            rok_od, rok_do, tytul or None, tylko_odpiete, with_annotations=True
        )
        combined_qs = QuerySetSequence(ciagle_qs, zwarte_qs)

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Publikacje"

        # Header row
        headers = ["ID", "Typ", "Tytul", "Rok", "PBN UID", "Oswiadczen", "Przypietych"]
        ws.append(headers)

        # Style header row
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)

        # Data rows
        for publication in combined_qs:
            # Determine publication type
            pub_type = (
                "Ciagle"
                if publication._meta.model_name == "wydawnictwo_ciagle"
                else "Zwarte"
            )
            pbn_uid = publication.pbn_uid_id if publication.pbn_uid_id else ""

            ws.append(
                [
                    publication.pk,
                    pub_type,
                    publication.tytul_oryginalny,
                    publication.rok,
                    pbn_uid,
                    publication.liczba_oswiadczen,
                    publication.liczba_przypietych,
                ]
            )

        # Adjust column widths
        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 80
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 40
        ws.column_dimensions["F"].width = 12
        ws.column_dimensions["G"].width = 12

        # Generate response
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"pbn-wysylka-publikacje-{rok_od}-{rok_do}.xlsx"
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response
