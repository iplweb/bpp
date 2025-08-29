from django.http import JsonResponse
from django.views import View
from django.views.generic.base import TemplateView

from pbn_downloader_app.models import PbnDownloadTask, PbnInstitutionPeopleTask
from pbn_downloader_app.tasks import (
    download_institution_people,
    download_institution_publications,
)

from django.utils.decorators import method_decorator

from bpp.const import GR_WPROWADZANIE_DANYCH

# Custom group required decorator


def group_required(group_name):
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

                raise PermissionDenied("You don't have permission to access this page")

        return _wrapped_view

    return decorator


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class PbnDownloaderMainView(TemplateView):
    """Main dashboard for PBN downloader status."""

    template_name = "pbn_downloader_app/main.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add latest task information
        latest_task = PbnDownloadTask.get_latest_task()
        latest_people_task = PbnInstitutionPeopleTask.get_latest_task()
        context["latest_task"] = latest_task
        context["latest_people_task"] = latest_people_task

        return context


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class StartPbnDownloadView(View):
    """API view to start PBN download task."""

    def post(self, request):
        # Check if user has PBN authorization
        user = request.user
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You are not authorized in PBN. Please log in to PBN first.",
                }
            )

        if not pbn_user.pbn_token_possibly_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": "Your PBN token has expired. Please log in to PBN again.",
                }
            )

        # Check if task is already running using database lock
        # Clean up any stale running tasks first
        PbnDownloadTask.cleanup_stale_running_tasks()

        running_task = PbnDownloadTask.objects.filter(status="running").first()
        if running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Download task is already running. Please wait for it to complete.",
                }
            )

        # Start the task
        try:
            download_institution_publications.delay(user.pk)
            return JsonResponse({"success": True, "message": "Download task started."})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Failed to start task: {str(e)}"}
            )


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class TaskStatusView(View):
    """API view to check task status."""

    def get(self, request):
        # Get latest task
        latest_task = PbnDownloadTask.get_latest_task()

        # Check if any task is currently running using database
        is_running = PbnDownloadTask.objects.filter(status="running").exists()

        response_data = {"is_running": is_running, "latest_task": None}

        if latest_task:
            response_data["latest_task"] = {
                "id": latest_task.id,
                "status": latest_task.status,
                "started_at": latest_task.started_at.isoformat(),
                "completed_at": (
                    latest_task.completed_at.isoformat()
                    if latest_task.completed_at
                    else None
                ),
                "error_message": latest_task.error_message,
                "user": latest_task.user.username,
                "current_step": latest_task.current_step,
                "progress_percentage": latest_task.progress_percentage,
                "publications_processed": latest_task.publications_processed,
                "statements_processed": latest_task.statements_processed,
                "total_publications": latest_task.total_publications,
                "total_statements": latest_task.total_statements,
                "last_updated": latest_task.last_updated.isoformat(),
            }

        return JsonResponse(response_data)


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class RetryTaskView(View):
    """API view to retry a failed task."""

    def post(self, request):
        # Check if user has PBN authorization
        user = request.user
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You are not authorized in PBN. Please log in to PBN first.",
                }
            )

        if not pbn_user.pbn_token_possibly_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": "Your PBN token has expired. Please log in to PBN again.",
                }
            )

        # Check if task is already running using database lock
        # Clean up any stale running tasks first
        PbnDownloadTask.cleanup_stale_running_tasks()

        running_task = PbnDownloadTask.objects.filter(status="running").first()
        if running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Download task is already running. Please wait for it to complete.",
                }
            )

        # Start the task
        try:
            download_institution_publications.delay(user.pk)
            return JsonResponse(
                {"success": True, "message": "Download task restarted."}
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Failed to restart task: {str(e)}"}
            )


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class StartPbnPeopleDownloadView(View):
    """API view to start PBN people download task."""

    def post(self, request):
        # Check if user has PBN authorization
        user = request.user
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You are not authorized in PBN. Please log in to PBN first.",
                }
            )

        if not pbn_user.pbn_token_possibly_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": "Your PBN token has expired. Please log in to PBN again.",
                }
            )

        # Check if task is already running using database lock
        # Clean up any stale running tasks first
        PbnInstitutionPeopleTask.cleanup_stale_running_tasks()

        running_task = PbnInstitutionPeopleTask.objects.filter(status="running").first()
        if running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "People download task is already running. Please wait for it to complete.",
                }
            )

        # Start the task
        try:
            download_institution_people.delay(user.pk)
            return JsonResponse(
                {"success": True, "message": "People download task started."}
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Failed to start people task: {str(e)}"}
            )


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class PeopleTaskStatusView(View):
    """API view to check people task status."""

    def get(self, request):
        # Get latest task
        latest_task = PbnInstitutionPeopleTask.get_latest_task()

        # Check if any task is currently running using database
        is_running = PbnInstitutionPeopleTask.objects.filter(status="running").exists()

        response_data = {"is_running": is_running, "latest_task": None}

        if latest_task:
            response_data["latest_task"] = {
                "id": latest_task.id,
                "status": latest_task.status,
                "started_at": latest_task.started_at.isoformat(),
                "completed_at": (
                    latest_task.completed_at.isoformat()
                    if latest_task.completed_at
                    else None
                ),
                "error_message": latest_task.error_message,
                "user": latest_task.user.username,
                "current_step": latest_task.current_step,
                "progress_percentage": latest_task.progress_percentage,
                "people_processed": latest_task.people_processed,
                "total_people": latest_task.total_people,
                "last_updated": latest_task.last_updated.isoformat(),
            }

        return JsonResponse(response_data)


@method_decorator(group_required(GR_WPROWADZANIE_DANYCH), name="dispatch")
class RetryPeopleTaskView(View):
    """API view to retry a failed people task."""

    def post(self, request):
        # Check if user has PBN authorization
        user = request.user
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You are not authorized in PBN. Please log in to PBN first.",
                }
            )

        if not pbn_user.pbn_token_possibly_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": "Your PBN token has expired. Please log in to PBN again.",
                }
            )

        # Check if task is already running using database lock
        # Clean up any stale running tasks first
        PbnInstitutionPeopleTask.cleanup_stale_running_tasks()

        running_task = PbnInstitutionPeopleTask.objects.filter(status="running").first()
        if running_task:
            return JsonResponse(
                {
                    "success": False,
                    "error": "People download task is already running. Please wait for it to complete.",
                }
            )

        # Start the task
        try:
            download_institution_people.delay(user.pk)
            return JsonResponse(
                {"success": True, "message": "People download task restarted."}
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Failed to restart people task: {str(e)}"}
            )
