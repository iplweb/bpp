"""Views for PBN import interface"""

import logging
import random

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from bpp.models import Jednostka, Jezyk, Uczelnia, Wydzial
from bpp.util import zaloguj_polkniety_wyjatek

from .models import (
    ImportInconsistency,
    ImportLog,
    ImportSession,
)
from .utils.institution_import import (
    sprawdz_obca_jednostka,
    znajdz_lub_utworz_jednostke_domyslna,
    znajdz_lub_utworz_wydzial_domyslny,
)
from .utils.log_export import (
    PREVIEW_LIMIT,
    count_log_entries,
    render_session_log_text,
)
from .utils.step_definitions import (
    get_all_disable_keys,
    get_form_steps,
)

logger = logging.getLogger(__name__)

# Maksymalna liczba wierszy ImportLog ładowana do widoków HTMX. Endpointy są
# re-fetchowane co 5 s podczas długiego importu — bez tego limitu każde
# odświeżenie ciągnęłoby tysiące wierszy. Pełny log pozostaje pobieralny przez
# ImportLogDownloadView (nieprzycięty).
MAX_LOGS_DISPLAY = 200


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
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        context["pbn_configured"] = uczelnia and uczelnia.pbn_integracja
        context["uczelnia"] = uczelnia
        context["uzywaj_wydzialow"] = uczelnia.uzywaj_wydzialow if uczelnia else False

        # Gate-check multi-hosted: obca jednostka MUSI istnieć i być podpięta do
        # wydziału tej uczelni, inaczej import padnie na triggerze spójności.
        # Sygnalizujemy to już przy wejściu na stronę (baner w szablonie).
        context["obca_jednostka_problem"] = (
            sprawdz_obca_jednostka(uczelnia) if uczelnia else None
        )

        # Sprawdź czy użytkownik ma ważny token PBN
        context["pbn_token_valid"] = self.request.user.pbn_token_possibly_valid()

        # Pobierz wydziały i jednostki — multi-hosted: WYŁĄCZNIE tej uczelni,
        # z której idzie request. Bez filtra formularz oferował encje obcych
        # uczelni, co prowadziło do startu importu z domyślną jednostką spoza
        # właściwej uczelni. Bez uczelni (brak kontekstu) nie ma czego importować.
        if uczelnia:
            wydzialy = Wydzial.objects.filter(uczelnia=uczelnia)
            jednostki = Jednostka.objects.filter(
                skupia_pracownikow=True, uczelnia=uczelnia
            )
        else:
            wydzialy = Wydzial.objects.none()
            jednostki = Jednostka.objects.none()

        # Jeśli brak wydziałów I brak jednostek - utwórz domyślne
        if not wydzialy.exists() and not jednostki.exists() and uczelnia:
            wydzial_domyslny, _ = znajdz_lub_utworz_wydzial_domyslny(uczelnia)
            jednostka_domyslna, _ = znajdz_lub_utworz_jednostke_domyslna(uczelnia)
            # Faza B (#438): ``Jednostka.wydzial`` to zdenormalizowany self-FK
            # do korzenia — nie przypisujemy Wydzialu. Podpinamy jednostkę pod
            # węzeł-lustro wydziału domyślnego (MPTT ``parent``); denorm wyliczy
            # ``wydzial`` przy zapisie.
            if jednostka_domyslna.parent is None:
                from bpp.models.struktura_konwersja import (
                    znajdz_lub_utworz_wezel_wydzialu,
                )

                wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial_domyslny)
                jednostka_domyslna.parent = wezel
                jednostka_domyslna.skupia_pracownikow = True
                jednostka_domyslna.save()
            # Odśwież querysets (wciąż zawężone do uczelni kontekstu)
            wydzialy = Wydzial.objects.filter(uczelnia=uczelnia)
            jednostki = Jednostka.objects.filter(
                skupia_pracownikow=True, uczelnia=uczelnia
            )

        context["wydzialy"] = wydzialy
        context["jednostki"] = jednostki

        # Domyślnie zaznaczony wydział/jednostka: WYŁĄCZNIE encja-placeholder
        # mająca "Domyślny"/"Domyślna" w nazwie (taka, jaką tworzą
        # znajdz_lub_utworz_*_domyslny). Jeśli takiej nie ma — pole zostaje
        # PUSTE i użytkownik musi świadomie wybrać prawdziwą jednostkę/wydział.
        # Nie podstawiamy tu nigdy losowej, realnej jednostki uczelni.
        context["wydzial_domyslny"] = wydzialy.filter(
            nazwa__icontains="domyśln"
        ).first()
        context["jednostka_domyslna"] = jednostki.filter(
            nazwa__icontains="domyśln"
        ).first()

        # Domyślny język dla publikacji bez (poprawnego) języka w PBN. Lista
        # widocznych języków + preselekcja polskiego (get_jezyk_polski to ten
        # sam kontrakt, którego używa importer jako fallback).
        context["jezyki"] = Jezyk.objects.filter(widoczny=True).order_by("nazwa")
        context["jezyk_domyslny"] = (
            Jezyk.objects.filter(skrot="pol.").first()
            or Jezyk.objects.filter(nazwa__iexact="polski").first()
        )

        # Import steps for dynamic form rendering (from step_definitions.py)
        context["import_steps"] = get_form_steps()

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

    @staticmethod
    def _bledy_kontekstu_uczelni(uczelnia, jednostka, wydzial):
        """Gate-check multi-hosted: spójność wybranych encji z uczelnią requestu.

        Domyślna jednostka i wydział MUSZĄ należeć do tej samej uczelni, z której
        idzie request (i do której pójdzie import) — inaczej import przypisywałby
        autorów/prace do encji obcej uczelni (cichy wyciek danych między
        tenantami). Egzekwujemy nawet przy zmanipulowanym formularzu (encje
        zawężamy też w GET, ale POST musi się bronić sam). Dodatkowo obca
        jednostka uczelni musi być skonfigurowana, bo krok institution_setup
        padłby na triggerze ``bpp_jednostka_wydzial_sprawdz_uczelnia_id``.

        Zwraca listę komunikatów błędów (pustą, gdy wszystko OK).
        """
        if uczelnia is None:
            return []

        errors = []
        if jednostka is not None and jednostka.uczelnia_id != uczelnia.pk:
            errors.append(
                "Wybrana domyślna jednostka należy do innej uczelni niż ta, "
                "z której uruchamiasz import."
            )
        if wydzial is not None and wydzial.uczelnia_id != uczelnia.pk:
            errors.append(
                "Wybrany domyślny wydział należy do innej uczelni niż ta, "
                "z której uruchamiasz import."
            )
        obca_problem = sprawdz_obca_jednostka(uczelnia)
        if obca_problem:
            errors.append(obca_problem)
        return errors

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

        # Domyślny język jest opcjonalny — przy braku/niepoprawnym wyborze
        # importer i tak spadnie na polski (resolve_default_jezyk). Bez
        # gate-checku per-uczelnia: języki są globalne.
        jezyk_id = request.POST.get("jezyk_domyslny_id")
        jezyk = Jezyk.objects.filter(pk=jezyk_id).first() if jezyk_id else None

        # Domyślna jednostka/wydział muszą być świadomie wybrane przez
        # użytkownika — nie pozwalamy ruszyć importu z pustym polem (w domyślnym
        # widoku nic nie jest pre-zaznaczone, chyba że istnieje placeholder
        # "Domyślna…"). Wydział egzekwujemy tylko gdy uczelnia używa wydziałów.
        # Multi-hosted: uczelnię bierzemy z requestu (NIE get_default) — tak samo
        # jak entrypoint zadania w tle kilka linii niżej.
        uczelnia = Uczelnia.objects.get_for_request(request)
        uzywaj_wydzialow = uczelnia.uzywaj_wydzialow if uczelnia else False

        errors = []
        if jednostka is None:
            errors.append("Wybierz domyślną jednostkę przed rozpoczęciem importu.")
        if uzywaj_wydzialow and wydzial is None:
            errors.append("Wybierz domyślny wydział przed rozpoczęciem importu.")

        errors += self._bledy_kontekstu_uczelni(uczelnia, jednostka, wydzial)

        if errors:
            for error in errors:
                messages.error(request, error)
            if request.headers.get("HX-Request"):
                response = HttpResponse()
                response["HX-Redirect"] = reverse("pbn_import:dashboard")
                return response
            return redirect("pbn_import:dashboard")

        # Build config dynamically from step_definitions
        disable_keys = get_all_disable_keys()
        config = {
            disable_key: not request.POST.get(form_field)
            for form_field, disable_key in disable_keys.items()
        }

        # Add additional config options
        config.update(
            {
                "delete_existing": request.POST.get("delete_existing") == "on",
                "wydzial_domyslny": wydzial.nazwa if wydzial else "",
                "wydzial_domyslny_id": wydzial.pk if wydzial else None,
                "jednostka_domyslna": jednostka.nazwa if jednostka else "",
                "jednostka_domyslna_id": jednostka.pk if jednostka else None,
                # Kanoniczne klucze czytane przez kroki importu
                # (publication_import / statement_import) ORAZ zapisywane przez
                # krok institution_setup. Zapisujemy je już TU, na formularzu, by
                # import startujący od późniejszego kroku (np. od źródeł, z
                # pominięciem institution_setup) i tak znał domyślną jednostkę.
                # To naprawia ValueError "Nie znaleziono domyślnej jednostki".
                "default_jednostka_id": jednostka.pk if jednostka else None,
                "wydzial_id": wydzial.pk if wydzial else None,
                # Domyślny język importu (fallback dla pozycji bez mainLanguage
                # albo z kodem spoza słownika Jezyk). Czytany przez
                # resolve_default_jezyk; None → polski.
                "default_jezyk": jezyk.nazwa if jezyk else "",
                "default_jezyk_id": jezyk.pk if jezyk else None,
            }
        )

        # Create import session
        session = ImportSession.objects.create(
            user=request.user,
            status="pending",
            config=config,
            current_step="Przygotowywanie importu...",
        )

        # Launch Celery task
        from .tasks import run_pbn_import

        # Multi-hosted: entrypoint zna konkretną uczelnię z requestu i MUSI
        # przekazać jej id do zadania w tle (zadanie NIE robi get_default()).
        uczelnia = Uczelnia.objects.get_for_request(request)
        result = run_pbn_import.delay(
            session.id, uczelnia_id=uczelnia.pk if uczelnia else None
        )
        session.task_id = result.id
        session.status = "pending"  # Keep as pending until task starts
        session.save()

        messages.success(request, f"Import #{session.id} został rozpoczęty!")

        if request.headers.get("HX-Request"):
            # Return HTMX response
            response = HttpResponse()
            response["HX-Redirect"] = reverse("pbn_import:dashboard")
            return response

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
                    zaloguj_polkniety_wyjatek(
                        "Nie udało się anulować zadania Celery "
                        f"{session.task_id} dla sesji importu #{session.id}",
                        logger=logger,
                        do_rollbar=True,
                    )
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
                request,
                "pbn_import/components/progress_compact.html",
                {"session": session},
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
        # Build disable config for all steps (used for presets that skip steps)
        disable_keys = get_all_disable_keys()
        all_disabled = {disable_key: True for disable_key in disable_keys.values()}

        presets = [
            {
                "id": "full",
                "name": "Wszystko",
                "description": "Importuje wszystkie dane z PBN",
                "icon": "fi-download",
                "config": {},  # Empty = all enabled
            },
            {
                "id": "update",
                "name": "Aktualizacja",
                "description": "Aktualizuje autorów, publikacje, oświadczenia i opłaty",
                "icon": "fi-refresh",
                "config": {
                    "disable_initial": True,
                    "disable_institutions": True,
                    "disable_zrodla_download": True,
                    "disable_zrodla_process": True,
                    "disable_punktacja_zrodel": True,
                    "disable_wydawcy_download": True,
                    "disable_wydawcy_process": True,
                    "disable_konferencje_download": True,
                    "disable_konferencje_process": True,
                    # autorzy, publikacje, oswiadczenia, oplaty pozostają włączone
                    "delete_existing": False,
                },
            },
            {
                "id": "sources_only",
                "name": "Tylko źródła",
                "description": "Importuje i aktualizuje punktację źródeł",
                "icon": "fi-book",
                "config": {
                    **all_disabled,
                    "disable_zrodla_download": False,
                    "disable_zrodla_process": False,
                    "disable_punktacja_zrodel": False,
                    "delete_existing": False,
                },
            },
        ]

        return JsonResponse({"presets": presets})


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
        )[:MAX_LOGS_DISPLAY]

        # Get error logs specifically
        context["error_logs"] = ImportLog.objects.filter(
            session=session, level__in=["error", "critical", "warning"]
        ).order_by("-timestamp")[:MAX_LOGS_DISPLAY]

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
            code: {
                "label": choice_labels.get(code, f"Nieznany typ: {code}"),
                "count": counts_dict[code],
            }
            for code in counts_dict
        }
        context["inconsistency_summary"] = inconsistency_summary
        context["active_filter"] = ""  # No filter active on initial page load

        # Get configuration
        context["config"] = session.config

        # Symulowany raw log (tekst) — zakładka „Log" pokazuje go inline i daje
        # pobranie. Podgląd przycinamy do PREVIEW_LIMIT wpisów, żeby „mega mega
        # długi" log nie zatkał przeglądarki ani nie napuchł HTML-a strony;
        # pełny log zawsze do pobrania przez .txt. Dostępny dla każdego statusu
        # (dla biegnącego = migawka).
        log_total = count_log_entries(session)
        context["raw_log_text"] = render_session_log_text(session, limit=PREVIEW_LIMIT)
        context["raw_log_total"] = log_total
        context["raw_log_shown"] = min(log_total, PREVIEW_LIMIT)
        context["raw_log_truncated"] = log_total > PREVIEW_LIMIT

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

        logs = ImportLog.objects.filter(session=session).order_by("-timestamp")[
            :MAX_LOGS_DISPLAY
        ]
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
        ).order_by("-timestamp")[:MAX_LOGS_DISPLAY]
        return render(
            request,
            "pbn_import/components/error_logs.html",
            {"error_logs": error_logs, "session": session, "user": request.user},
        )


class ImportLogDownloadView(LoginRequiredMixin, ImportPermissionMixin, View):
    """Pobranie symulowanego raw logu tekstowego (błędy + ostrzeżenia).

    Dostępne dla sesji w dowolnym statusie (także nieudanej/anulowanej/
    biegnącej) — log nieudanego importu jest najcenniejszy. Dla biegnącego
    importu to migawka stanu z chwili żądania.
    """

    def get(self, request, pk):
        session = get_object_or_404(ImportSession, pk=pk)
        # Użytkownik widzi tylko swoje sesje (chyba że superuser).
        if not request.user.is_superuser and session.user != request.user:
            return HttpResponse("Forbidden", status=403)

        text = render_session_log_text(session)
        response = HttpResponse(text, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="pbn_import_log_{session.id}.txt"'
        )
        return response


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
            code: {
                "label": choice_labels.get(code, f"Nieznany typ: {code}"),
                "count": counts_dict[code],
            }
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
