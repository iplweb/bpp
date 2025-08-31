import logging

from django.core.management import call_command
from django.db import models
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required

from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


class RozbieznoscDyscyplinPBNListView(ListView):
    """Widok listy rozbieżności dyscyplin między BPP a PBN."""

    model = RozbieznoscDyscyplinPBN
    template_name = "komparator_pbn_udzialy/list.html"
    context_object_name = "rozbieznosci"
    paginate_by = 50

    def get_queryset(self):
        """Optymalizowany queryset z prefetch_related."""
        queryset = super().get_queryset()

        # Optymalizacja zapytań
        queryset = queryset.select_related(
            "oswiadczenie_instytucji",
            "oswiadczenie_instytucji__publicationId",
            "dyscyplina_bpp",
            "dyscyplina_pbn",
            "content_type",
        ).prefetch_related(
            "oswiadczenie_instytucji__personId",
        )

        # Filtrowanie
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(oswiadczenie_instytucji__publicationId__tytul__icontains=search)
                | Q(dyscyplina_bpp__nazwa__icontains=search)
                | Q(dyscyplina_pbn__nazwa__icontains=search)
            )

        # Filtrowanie po typie rozbieżności
        filter_type = self.request.GET.get("filter")
        if filter_type == "bpp_empty":
            queryset = queryset.filter(dyscyplina_bpp__isnull=True)
        elif filter_type == "pbn_empty":
            queryset = queryset.filter(dyscyplina_pbn__isnull=True)
        elif filter_type == "both_present":
            queryset = queryset.filter(
                dyscyplina_bpp__isnull=False,
                dyscyplina_pbn__isnull=False,
            ).exclude(dyscyplina_bpp=models.F("dyscyplina_pbn"))

        # Filtrowanie po roku publikacji
        rok_min = self.request.GET.get("rok_min", "2022")
        rok_max = self.request.GET.get("rok_max", "2025")

        if rok_min:
            try:
                rok_min_int = int(rok_min)
                queryset = queryset.filter(
                    oswiadczenie_instytucji__publicationId__year__gte=rok_min_int
                )
            except (ValueError, TypeError):
                pass

        if rok_max:
            try:
                rok_max_int = int(rok_max)
                queryset = queryset.filter(
                    oswiadczenie_instytucji__publicationId__year__lte=rok_max_int
                )
            except (ValueError, TypeError):
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statystyki
        total = RozbieznoscDyscyplinPBN.objects.count()
        bpp_empty = RozbieznoscDyscyplinPBN.objects.filter(
            dyscyplina_bpp__isnull=True
        ).count()
        pbn_empty = RozbieznoscDyscyplinPBN.objects.filter(
            dyscyplina_pbn__isnull=True
        ).count()
        both_present = RozbieznoscDyscyplinPBN.objects.filter(
            dyscyplina_bpp__isnull=False,
            dyscyplina_pbn__isnull=False,
        ).count()

        context.update(
            {
                "total_count": total,
                "bpp_empty_count": bpp_empty,
                "pbn_empty_count": pbn_empty,
                "both_present_count": both_present,
                "search": self.request.GET.get("search", ""),
                "filter": self.request.GET.get("filter", ""),
                "rok_min": self.request.GET.get("rok_min", "2022"),
                "rok_max": self.request.GET.get("rok_max", "2025"),
            }
        )

        return context


class RozbieznoscDyscyplinPBNDetailView(DetailView):
    """Widok szczegółowy rozbieżności."""

    model = RozbieznoscDyscyplinPBN
    template_name = "komparator_pbn_udzialy/detail.html"
    context_object_name = "rozbieznosc"

    def get_queryset(self):
        """Optymalizowany queryset."""
        return (
            super()
            .get_queryset()
            .select_related(
                "oswiadczenie_instytucji",
                "oswiadczenie_instytucji__publicationId",
                "dyscyplina_bpp",
                "dyscyplina_pbn",
                "content_type",
            )
            .prefetch_related(
                "oswiadczenie_instytucji__personId",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Dodajemy informacje o publikacji i autorze
        rozbieznosc = self.object
        wydawnictwo_autor = rozbieznosc.get_wydawnictwo_autor()

        if wydawnictwo_autor:
            context["autor"] = wydawnictwo_autor.autor
            context["publikacja"] = wydawnictwo_autor.rekord
            context["jednostka"] = wydawnictwo_autor.jednostka
            context["wydawnictwo_autor"] = wydawnictwo_autor

        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("komparator_pbn_udzialy.add_rozbieznoscdyscyplinpbn"),
    name="dispatch",
)
class RebuildDiscrepanciesView(View):
    """Widok do przebudowy rozbieżności."""

    def get(self, request):
        """Wyświetla stronę potwierdzenia."""
        context = {
            "current_count": RozbieznoscDyscyplinPBN.objects.count(),
        }
        return render(
            request,
            "komparator_pbn_udzialy/rebuild_confirm.html",
            context,
        )

    def post(self, request):
        """Uruchamia przebudowę rozbieżności."""
        run_async = request.POST.get("run_async") == "on"

        if run_async:
            # Uruchom w tle używając Celery
            try:
                from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

                clear_existing = request.POST.get("clear_existing") == "on"
                task = porownaj_dyscypliny_pbn_task.delay(clear_existing=clear_existing)

                # Zapisz task_id w sesji
                request.session["komparator_task_id"] = task.id

                messages.info(
                    request,
                    f"Przebudowa rozbieżności została uruchomiona w tle. ID zadania: {task.id}",
                )

                # Przekieruj do strony statusu
                return HttpResponseRedirect(
                    reverse(
                        "komparator_pbn_udzialy:task_status",
                        kwargs={"task_id": task.id},
                    )
                )

            except Exception as e:
                logger.error(f"Błąd podczas uruchamiania zadania Celery: {e}")
                messages.error(
                    request,
                    f"Nie można uruchomić zadania w tle: {str(e)}. Spróbuj uruchomić synchronicznie.",
                )
                return HttpResponseRedirect(reverse("komparator_pbn_udzialy:rebuild"))
        else:
            # Uruchom synchronicznie (stara metoda)
            try:
                clear_existing = request.POST.get("clear_existing") == "on"

                call_command(
                    "porownaj_dyscypliny_pbn",
                    clear=clear_existing,
                    no_progress=True,
                )

                messages.success(
                    request,
                    "Przebudowa rozbieżności zakończona pomyślnie.",
                )

            except Exception as e:
                logger.error(f"Błąd podczas przebudowy rozbieżności: {e}")
                messages.error(
                    request,
                    f"Wystąpił błąd podczas przebudowy: {str(e)}",
                )

        return HttpResponseRedirect(reverse("komparator_pbn_udzialy:list"))


@method_decorator(login_required, name="dispatch")
class TaskStatusView(View):
    """Widok do sprawdzania statusu zadania w tle."""

    def get(self, request, task_id):
        """Wyświetla stronę ze statusem zadania."""
        return render(
            request, "komparator_pbn_udzialy/task_status.html", {"task_id": task_id}
        )


@method_decorator(login_required, name="dispatch")
class TaskStatusAPIView(View):
    """API endpoint do sprawdzania statusu zadania."""

    def get(self, request, task_id):
        """Zwraca status zadania w formacie JSON."""
        try:
            from komparator_pbn_udzialy.tasks import get_task_status

            status = get_task_status(task_id)
            return JsonResponse(status)

        except Exception as e:
            logger.error(f"Błąd podczas pobierania statusu zadania: {e}")
            return JsonResponse({"status": "ERROR", "message": str(e)}, status=500)
