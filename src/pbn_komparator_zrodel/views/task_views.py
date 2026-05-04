"""Widoki uruchamiania i monitorowania zadań Celery dla komparatora źródeł PBN."""

from braces.views import GroupRequiredMixin
from celery.result import AsyncResult
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from ..models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN
from ..utils import is_pbn_journals_data_fresh


class PrzebudujRozbieznosciView(GroupRequiredMixin, View):
    """Widok do uruchamiania przebudowy rozbieżności."""

    group_required = "wprowadzanie danych"

    def get(self, request):
        meta = KomparatorZrodelMeta.get_instance()
        is_fresh, stale_message, last_download = is_pbn_journals_data_fresh()

        return render(
            request,
            "pbn_komparator_zrodel/rebuild_confirm.html",
            {
                "meta": meta,
                "current_count": RozbieznoscZrodlaPBN.objects.count(),
                "pbn_data_fresh": is_fresh,
                "pbn_stale_message": stale_message,
                "pbn_last_download": last_download,
            },
        )

    def post(self, request):
        # Sprawdź świeżość danych PBN
        is_fresh, stale_message, _ = is_pbn_journals_data_fresh()
        if not is_fresh:
            messages.error(
                request,
                f"Nie można uruchomić porównywania: {stale_message}. "
                "Najpierw pobierz aktualne dane źródeł z PBN.",
            )
            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:przebuduj"))

        from ..tasks import porownaj_zrodla_task

        min_rok = int(request.POST.get("min_rok", 2022))
        clear_existing = request.POST.get("clear_existing") == "on"

        task = porownaj_zrodla_task.delay(
            min_rok=min_rok,
            clear_existing=clear_existing,
        )

        request.session["komparator_zrodel_task_id"] = task.id
        messages.info(request, f"Zadanie porównywania uruchomione. ID: {task.id}")

        return HttpResponseRedirect(
            reverse("pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id})
        )


class TaskStatusView(GroupRequiredMixin, View):
    """Status zadania z HTMX polling."""

    group_required = "wprowadzanie danych"

    def get(self, request, task_id):
        task = AsyncResult(task_id)
        task_info = task.info if isinstance(task.info, dict) else {}

        context = {
            "task_id": task_id,
            "task_ready": task.ready(),
        }

        if not task.ready():
            context["info"] = task_info
        elif task.failed():
            context["error"] = str(task.info)
        elif task.successful():
            result = task.result or {}
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)
            stats = result.get("stats", {})

            if stats:
                messages.success(
                    request,
                    f"Porównywanie zakończone. Przetworzono: {stats.get('processed', 0)}, "
                    f"rozbieżności punktów: {stats.get('points_discrepancies', 0)}, "
                    f"rozbieżności dyscyplin: {stats.get('discipline_discrepancies', 0)}",
                )
            else:
                messages.success(
                    request,
                    f"Zaktualizowano {updated} rekordów."
                    + (f" Błędy: {errors}." if errors else ""),
                )

            # HTMX redirect
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = reverse("pbn_komparator_zrodel:list")
                return response
            return redirect("pbn_komparator_zrodel:list")

        # HTMX request: zwróć tylko partial
        if request.headers.get("HX-Request"):
            return render(request, "pbn_komparator_zrodel/_progress.html", context)

        return render(request, "pbn_komparator_zrodel/task_status.html", context)
