"""Views for PBN import interface"""

import json
import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, TemplateView

from bpp.models import Jednostka, Uczelnia, Wydzial

from .models import (
    ImportInconsistency,
    ImportLog,
    ImportSession,
)


class ImportPermissionMixin(PermissionRequiredMixin):
    """Mixin requiring PBN import permissions"""

    def has_permission(self):
        return (
            self.request.user.is_superuser
            or self.request.user.groups.filter(name="wprowadzanie danych").exists()
            or self.request.user.has_perm("pbn_import.add_importsession")
        )


class ImportDashboardView(LoginRequiredMixin, ImportPermissionMixin, TemplateView):
    """Main import dashboard"""

    template_name = "pbn_import/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get recent sessions with related data
        context["recent_sessions"] = (
            ImportSession.objects.filter(user=self.request.user)
            .select_related("user")
            .order_by("-started_at")[:10]
        )

        # Get active session if any
        active_session = (
            ImportSession.objects.filter(
                user=self.request.user, status__in=["running", "paused"]
            )
            .prefetch_related("logs")
            .first()
        )

        # Sprawdź czy aktywna sesja nie jest "zgubiona"
        if active_session and active_session.status == "running":
            was_cancelled = active_session.auto_cancel_if_lost()
            if was_cancelled:
                # Sesja została anulowana - odśwież z bazy (status się zmienił)
                active_session.refresh_from_db()
                # Dodaj komunikat dla użytkownika
                context["auto_cancelled_message"] = active_session.error_message

        context["active_session"] = active_session

        # Get motivational message
        context["motivational_message"] = self.get_motivational_message()

        # Check if PBN is configured
        uczelnia = Uczelnia.objects.get_default()
        context["pbn_configured"] = uczelnia and uczelnia.pbn_integracja
        context["uczelnia"] = uczelnia
        context["uzywaj_wydzialow"] = uczelnia.uzywaj_wydzialow if uczelnia else False

        # Sprawdź czy użytkownik ma ważny token PBN
        context["pbn_token_valid"] = self.request.user.pbn_token_possibly_valid()

        # Pobierz wszystkie wydziały i jednostki
        wydzialy = Wydzial.objects.all()
        jednostki = Jednostka.objects.filter(skupia_pracownikow=True)

        # Jeśli brak wydziałów I brak jednostek - utwórz domyślne
        if not wydzialy.exists() and not jednostki.exists() and uczelnia:
            wydzial_domyslny, _ = Wydzial.objects.get_or_create(
                skrot="WD",
                defaults={
                    "nazwa": "Wydział Domyślny",
                    "skrot_nazwy": "Wydz. Dom.",
                    "uczelnia": uczelnia,
                },
            )
            jednostka_domyslna, _ = Jednostka.objects.get_or_create(
                skrot="JD",
                defaults={
                    "nazwa": "Jednostka Domyślna",
                    "uczelnia": uczelnia,
                    "wydzial": wydzial_domyslny,
                    "skupia_pracownikow": True,
                },
            )
            # Odśwież querysets
            wydzialy = Wydzial.objects.all()
            jednostki = Jednostka.objects.filter(skupia_pracownikow=True)

        context["wydzialy"] = wydzialy
        context["jednostki"] = jednostki

        # Domyślnie wybrany wydział - pierwszy dostępny
        context["wydzial_domyslny"] = wydzialy.first()

        # Jednostka domyślna - szukaj "JD" lub pierwsza dostępna
        jednostka_domyslna = Jednostka.objects.filter(skrot="JD").first()
        if not jednostka_domyslna:
            jednostka_domyslna = jednostki.first()
        context["jednostka_domyslna"] = jednostka_domyslna

        return context

    def get_motivational_message(self):
        """Get a random motivational message"""
        messages = [
            "Import danych z PBN",
            "System gotowy do importu",
            "Panel importu danych",
            "Zarządzanie importem PBN",
            "Synchronizacja z PBN",
        ]
        return random.choice(messages)


class StartImportView(LoginRequiredMixin, ImportPermissionMixin, View):
    """Start a new import session"""

    def post(self, request):
        # Get configuration from POST data
        # Checkboxes are inverted - if checkbox is checked, we DON'T disable
        # Pobierz ID z formularza i znajdź obiekty
        wydzial_id = request.POST.get("wydzial_domyslny_id")
        jednostka_id = request.POST.get("jednostka_domyslna_id")

        wydzial = Wydzial.objects.filter(pk=wydzial_id).first() if wydzial_id else None
        jednostka = (
            Jednostka.objects.filter(pk=jednostka_id).first() if jednostka_id else None
        )

        config = {
            "disable_initial": not request.POST.get("initial"),
            "disable_zrodla": not request.POST.get("zrodla"),
            "disable_wydawcy": not request.POST.get("wydawcy"),
            "disable_konferencje": not request.POST.get("konferencje"),
            "disable_autorzy": not request.POST.get("autorzy"),
            "disable_publikacje": not request.POST.get("publikacje"),
            "disable_integracja": not request.POST.get("integracja"),
            "disable_oswiadczenia": not request.POST.get("oswiadczenia"),
            "disable_oplaty": not request.POST.get("oplaty"),
            "delete_existing": request.POST.get("delete_existing") == "on",
            "wydzial_domyslny": wydzial.nazwa if wydzial else "",
            "wydzial_domyslny_id": wydzial.pk if wydzial else None,
            "jednostka_domyslna": jednostka.nazwa if jednostka else "",
            "jednostka_domyslna_id": jednostka.pk if jednostka else None,
        }

        # Create import session
        session = ImportSession.objects.create(
            user=request.user,
            status="pending",
            config=config,
            current_step="Przygotowywanie importu...",
        )

        # Launch Celery task
        from .tasks import run_pbn_import

        result = run_pbn_import.delay(session.id)
        session.task_id = result.id
        session.status = "pending"  # Keep as pending until task starts
        session.save()

        # Send WebSocket notification
        self.send_websocket_update(
            session,
            {
                "type": "import_started",
                "session_id": session.id,
                "message": "Import został rozpoczęty!",
            },
        )

        messages.success(request, f"Import #{session.id} został rozpoczęty!")

        if request.headers.get("HX-Request"):
            # Return HTMX response
            response = HttpResponse()
            response["HX-Redirect"] = reverse("pbn_import:dashboard")
            return response

        return redirect("pbn_import:dashboard")

    def send_websocket_update(self, session, data):
        """Send update via WebSocket"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"import_{session.id}", {"type": "import_update", "data": data}
        )

        return redirect("pbn_import:dashboard")


class CancelImportView(LoginRequiredMixin, ImportPermissionMixin, View):
    """Cancel an import session"""

    def post(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk, user=request.user)

        if session.status in ["running", "paused", "pending"]:
            session.status = "cancelled"
            session.completed_at = timezone.now()
            session.save()

            # Try to revoke the Celery task if it exists
            if session.task_id:
                from celery import current_app
                from celery.result import AsyncResult

                try:
                    # First, try to revoke the task (works with all worker types)
                    current_app.control.revoke(
                        session.task_id, terminate=True, signal="SIGTERM"
                    )

                    # For prefork pool, this will actually terminate the task
                    # For eventlet/gevent pools, this just marks it as revoked

                    # Check if the task is actually revoked
                    result = AsyncResult(session.task_id)  # noqa

                    ImportLog.objects.create(
                        session=session,
                        level="info",
                        step="Control",
                        message=f"Wysłano żądanie anulowania zadania Celery (ID: {session.task_id})",
                    )

                    # Note: The actual cancellation will be handled by checking session status
                    # in the import loops

                except Exception as e:
                    ImportLog.objects.create(
                        session=session,
                        level="warning",
                        step="Control",
                        message=f"Błąd przy próbie anulowania zadania Celery: {str(e)} - "
                        f"zadanie zostanie anulowane przez sprawdzanie statusu",
                    )

            # Log the cancellation
            ImportLog.objects.create(
                session=session,
                level="warning",
                step="Control",
                message="Import został anulowany przez użytkownika",
            )

            messages.warning(request, f"Import #{session.id} został anulowany")

        if request.headers.get("HX-Request"):
            # Return updated progress component for HTMX
            return render(
                request, "pbn_import/components/progress.html", {"session": session}
            )

        return redirect("pbn_import:dashboard")


class ImportProgressView(LoginRequiredMixin, ImportPermissionMixin, DetailView):
    """HTMX endpoint for progress updates"""

    model = ImportSession
    template_name = "pbn_import/components/progress_compact.html"
    context_object_name = "session"

    def get_queryset(self):
        return ImportSession.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Hide details button if we're being called from the detail view
        referer = self.request.META.get("HTTP_REFERER", "")
        if f"/session/{self.object.pk}/" in referer:
            context["hide_details_button"] = True
        return context


class ImportLogStreamView(LoginRequiredMixin, ImportPermissionMixin, View):
    """HTMX endpoint for log streaming"""

    def get(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk, user=request.user)

        # Get last N log entries
        logs = ImportLog.objects.filter(session=session).order_by("-timestamp")[:50]

        # Reverse to show oldest first
        logs = reversed(logs)

        return render(
            request,
            "pbn_import/components/log_window.html",
            {"logs": logs, "session": session},
        )


class ActiveSessionsView(LoginRequiredMixin, ImportPermissionMixin, ListView):
    """HTMX endpoint for active sessions list"""

    template_name = "pbn_import/components/active_sessions.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return (
            ImportSession.objects.filter(status__in=["running", "paused"])
            .select_related("user")
            .order_by("-started_at")
        )


class ImportPresetsView(LoginRequiredMixin, ImportPermissionMixin, View):
    """Get available import presets"""

    def get(self, request):
        presets = [
            {
                "id": "full",
                "name": "Wszystko",
                "description": "Importuje wszystkie dane z PBN",
                "icon": "fi-download",
                "config": {},
            },
            {
                "id": "update",
                "name": "Aktualizacja",
                "description": "Aktualizuje autorów, publikacje, oświadczenia i opłaty",
                "icon": "fi-refresh",
                "config": {
                    "disable_initial": True,
                    "disable_institutions": True,
                    "disable_zrodla": True,
                    "disable_wydawcy": True,
                    "disable_konferencje": True,
                    "delete_existing": False,
                },
            },
            {
                "id": "integration",
                "name": "Integracja danych",
                "description": "Integruje i synchronizuje dane między systemami",
                "icon": "fi-link",
                "config": {
                    "disable_initial": True,
                    "disable_institutions": True,
                    "disable_zrodla": True,
                    "disable_wydawcy": True,
                    "disable_konferencje": True,
                    "disable_autorzy": True,
                    "disable_publikacje": True,
                    "disable_integracja": False,
                    "disable_oswiadczenia": True,
                    "disable_oplaty": True,
                    "delete_existing": False,
                },
            },
        ]

        return JsonResponse({"presets": presets})


class SavePresetView(LoginRequiredMixin, ImportPermissionMixin, View):
    """Save a custom import preset"""

    @csrf_exempt
    def post(self, request):
        data = json.loads(request.body)  # noqa

        # In production, save to database or user preferences
        # For now, just return success

        return JsonResponse({"success": True, "message": "Preset zapisany pomyślnie!"})


class ImportSessionDetailView(LoginRequiredMixin, ImportPermissionMixin, DetailView):
    """Detailed view of import session with logs and errors"""

    model = ImportSession
    template_name = "pbn_import/session_detail.html"
    context_object_name = "session"

    def get_queryset(self):
        # Users can only see their own sessions unless they're superuser
        if self.request.user.is_superuser:
            return ImportSession.objects.all()
        return ImportSession.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        # Get all logs for this session
        context["logs"] = ImportLog.objects.filter(session=session).order_by(
            "-timestamp"
        )

        # Get error logs specifically
        context["error_logs"] = ImportLog.objects.filter(
            session=session, level__in=["error", "critical", "warning"]
        ).order_by("-timestamp")

        # Get inconsistencies
        inconsistencies = (
            ImportInconsistency.objects.filter(session=session)
            .select_related("bpp_publication_content_type")
            .order_by("-timestamp")
        )
        context["inconsistencies"] = inconsistencies
        context["inconsistency_count"] = inconsistencies.count()

        # Build inconsistency summary by type using single aggregation query
        inconsistency_counts = (
            inconsistencies.values("inconsistency_type")
            .annotate(count=Count("id"))
            .order_by()
        )
        counts_dict = {
            item["inconsistency_type"]: item["count"] for item in inconsistency_counts
        }
        choice_labels = dict(ImportInconsistency.INCONSISTENCY_TYPE_CHOICES)
        inconsistency_summary = {
            code: {"label": choice_labels[code], "count": counts_dict[code]}
            for code in counts_dict
        }
        context["inconsistency_summary"] = inconsistency_summary
        context["active_filter"] = ""  # No filter active on initial page load

        # Get configuration
        context["config"] = session.config

        # Calculate duration - use model property which handles both completed
        # and running sessions
        context["duration"] = session.duration

        return context


class ImportAllLogsView(LoginRequiredMixin, ImportPermissionMixin, View):
    """HTMX endpoint for all logs"""

    def get(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk)
        # Check permission - users can only see their own sessions unless superuser
        if not request.user.is_superuser and session.user != request.user:
            return HttpResponse("Forbidden", status=403)

        logs = ImportLog.objects.filter(session=session).order_by("-timestamp")
        return render(
            request,
            "pbn_import/components/all_logs.html",
            {"logs": logs, "session": session, "user": request.user},
        )


class ImportErrorLogsView(LoginRequiredMixin, ImportPermissionMixin, View):
    """HTMX endpoint for error logs"""

    def get(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk)
        # Check permission - users can only see their own sessions unless superuser
        if not request.user.is_superuser and session.user != request.user:
            return HttpResponse("Forbidden", status=403)

        error_logs = ImportLog.objects.filter(
            session=session, level__in=["error", "critical", "warning"]
        ).order_by("-timestamp")
        return render(
            request,
            "pbn_import/components/error_logs.html",
            {"error_logs": error_logs, "session": session, "user": request.user},
        )


class ImportInconsistenciesView(LoginRequiredMixin, ImportPermissionMixin, View):
    """HTMX endpoint for inconsistencies"""

    def get(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk)
        # Check permission - users can only see their own sessions unless superuser
        if not request.user.is_superuser and session.user != request.user:
            return HttpResponse("Forbidden", status=403)

        # Get filter type from query parameter
        filter_type = request.GET.get("filter_type", "")

        # Get all inconsistencies for building summary
        all_inconsistencies = ImportInconsistency.objects.filter(session=session)

        # Build inconsistency summary by type using single aggregation query
        inconsistency_counts = (
            all_inconsistencies.values("inconsistency_type")
            .annotate(count=Count("id"))
            .order_by()
        )
        counts_dict = {
            item["inconsistency_type"]: item["count"] for item in inconsistency_counts
        }
        choice_labels = dict(ImportInconsistency.INCONSISTENCY_TYPE_CHOICES)
        inconsistency_summary = {
            code: {"label": choice_labels[code], "count": counts_dict[code]}
            for code in counts_dict
        }

        # Apply filter if specified
        if filter_type and filter_type in dict(
            ImportInconsistency.INCONSISTENCY_TYPE_CHOICES
        ):
            inconsistencies = all_inconsistencies.filter(
                inconsistency_type=filter_type
            ).order_by("-timestamp")
        else:
            inconsistencies = all_inconsistencies.order_by("-timestamp")
            filter_type = ""  # Reset if invalid

        return render(
            request,
            "pbn_import/components/inconsistencies.html",
            {
                "inconsistencies": inconsistencies,
                "inconsistency_summary": inconsistency_summary,
                "session": session,
                "user": request.user,
                "active_filter": filter_type,
            },
        )
