import logging

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView

from bpp.const import GR_WPROWADZANIE_DANYCH
from ewaluacja_common.okres import lata_okresu
from komparator_pbn_udzialy.models import (
    BrakAutoraWPublikacji,
    ProblemWrapper,
    RozbieznoscDyscyplinPBN,
)
from pbn_downloader_app.freshness import is_pbn_publications_data_fresh

logger = logging.getLogger(__name__)

#: Ścieżka od rekordu problemu do roku publikacji w PBN.
ROK_PUBLIKACJI_PBN = "oswiadczenie_instytucji__publicationId__year"


def _rok(wartosc):
    """Rok z parametru GET jako ``int`` albo ``None`` (puste pole albo
    nie-liczba = bez ograniczenia z tej strony)."""
    try:
        return int(wartosc)
    except (ValueError, TypeError):
        return None


def filtruj_lata(queryset, rok_min, rok_max):
    """Zostaw problemy publikacji PBN z lat ``rok_min``–``rok_max``."""
    rok_min, rok_max = _rok(rok_min), _rok(rok_max)
    if rok_min is not None:
        queryset = queryset.filter(**{f"{ROK_PUBLIKACJI_PBN}__gte": rok_min})
    if rok_max is not None:
        queryset = queryset.filter(**{f"{ROK_PUBLIKACJI_PBN}__lte": rok_max})
    return queryset


class ProblemyPBNListView(GroupRequiredMixin, View):
    """Widok listy wszystkich problemów PBN - rozbieżności i brakujących autorów."""

    group_required = GR_WPROWADZANIE_DANYCH
    template_name = "komparator_pbn_udzialy/list.html"

    def get(self, request):
        # Filtry
        search = request.GET.get("search", "")
        filter_type = request.GET.get("filter", "")
        # Bez ręcznego zakresu: lata okresu ewaluacji z paska okresu.
        okres_od, okres_do = lata_okresu(request)
        rok_min = request.GET.get("rok_min", str(okres_od))
        rok_max = request.GET.get("rok_max", str(okres_do))

        # Pobierz rozbieżności
        rozbieznosci = self._get_rozbieznosci(search, filter_type, rok_min, rok_max)

        # Pobierz brakujących autorów
        brakujacy = self._get_brakujacy(search, filter_type, rok_min, rok_max)

        # Opakuj w wrapper i połącz
        all_problems = []
        for r in rozbieznosci:
            all_problems.append(ProblemWrapper(r))
        for b in brakujacy:
            all_problems.append(ProblemWrapper(b))

        # Sortuj po dacie (najnowsze pierwsze)
        all_problems.sort(key=lambda x: x.created_at, reverse=True)

        # Statystyki
        stats = self._get_stats(rok_min, rok_max)

        # PBN data freshness check
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_publications_data_fresh()
        )

        context = {
            "problemy": all_problems,
            "search": search,
            "filter": filter_type,
            "rok_min": rok_min,
            "rok_max": rok_max,
            "pbn_data_fresh": pbn_data_fresh,
            "pbn_stale_message": pbn_stale_message,
            "pbn_last_download": pbn_last_download,
            **stats,
        }

        return render(request, self.template_name, context)

    def _get_rozbieznosci(self, search, filter_type, rok_min, rok_max):
        """Pobiera rozbieżności dyscyplin z uwzględnieniem filtrów."""
        queryset = RozbieznoscDyscyplinPBN.objects.select_related(
            "oswiadczenie_instytucji",
            "oswiadczenie_instytucji__publicationId",
            "dyscyplina_bpp",
            "dyscyplina_pbn",
            "content_type",
        ).prefetch_related(
            "oswiadczenie_instytucji__personId",
        )

        # Wyszukiwanie
        if search:
            queryset = queryset.filter(
                Q(oswiadczenie_instytucji__publicationId__title__icontains=search)
                | Q(dyscyplina_bpp__nazwa__icontains=search)
                | Q(dyscyplina_pbn__nazwa__icontains=search)
            )

        # Filtrowanie po typie - dla rozbieżności
        if filter_type == "bpp_empty":
            queryset = queryset.filter(dyscyplina_bpp__isnull=True)
        elif filter_type == "pbn_empty":
            queryset = queryset.filter(dyscyplina_pbn__isnull=True)
        elif filter_type == "both_present":
            queryset = queryset.filter(
                dyscyplina_bpp__isnull=False,
                dyscyplina_pbn__isnull=False,
            ).exclude(dyscyplina_bpp=models.F("dyscyplina_pbn"))
        elif filter_type in [
            BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
            BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
            BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        ]:
            # Filtr dla typu brakującego autora - nie pokazuj rozbieżności
            return []

        return list(filtruj_lata(queryset, rok_min, rok_max))

    def _get_brakujacy(self, search, filter_type, rok_min, rok_max):
        """Pobiera brakujących autorów z uwzględnieniem filtrów."""
        queryset = BrakAutoraWPublikacji.objects.select_related(
            "oswiadczenie_instytucji",
            "oswiadczenie_instytucji__publicationId",
            "pbn_scientist",
            "autor",
            "dyscyplina_pbn",
            "content_type",
        )

        # Wyszukiwanie
        if search:
            queryset = queryset.filter(
                Q(pbn_scientist__lastName__icontains=search)
                | Q(pbn_scientist__name__icontains=search)
                | Q(oswiadczenie_instytucji__publicationId__title__icontains=search)
                | Q(autor__nazwisko__icontains=search)
            )

        # Filtrowanie po typie - dla brakujących autorów
        if filter_type in [
            BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
            BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
            BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        ]:
            queryset = queryset.filter(typ=filter_type)
        elif filter_type in ["bpp_empty", "pbn_empty", "both_present"]:
            # Filtr dla rozbieżności - nie pokazuj brakujących
            return []

        return list(filtruj_lata(queryset, rok_min, rok_max))

    def _get_stats(self, rok_min, rok_max):
        """Statystyki wszystkich typów problemów dla tego samego zakresu lat
        co lista (inaczej kafelki pokazywałyby inne liczby niż tabela)."""
        rozbieznosci = filtruj_lata(
            RozbieznoscDyscyplinPBN.objects.all(), rok_min, rok_max
        ).aggregate(
            total=Count("id"),
            bpp_empty=Count("id", filter=Q(dyscyplina_bpp__isnull=True)),
            pbn_empty=Count("id", filter=Q(dyscyplina_pbn__isnull=True)),
            both_present=Count(
                "id",
                filter=Q(dyscyplina_bpp__isnull=False, dyscyplina_pbn__isnull=False),
            ),
        )
        rozbieznosci_total = rozbieznosci["total"]
        bpp_empty = rozbieznosci["bpp_empty"]
        pbn_empty = rozbieznosci["pbn_empty"]
        both_present = rozbieznosci["both_present"]

        brakujacy = filtruj_lata(
            BrakAutoraWPublikacji.objects.all(), rok_min, rok_max
        ).aggregate(
            total=Count("id"),
            missing_autor=Count(
                "id", filter=Q(typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP)
            ),
            missing_link=Count(
                "id", filter=Q(typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA)
            ),
            missing_publication=Count(
                "id", filter=Q(typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI)
            ),
        )
        brakujacy_total = brakujacy["total"]
        missing_autor = brakujacy["missing_autor"]
        missing_link = brakujacy["missing_link"]
        missing_publication = brakujacy["missing_publication"]

        return {
            "total_count": rozbieznosci_total + brakujacy_total,
            "rozbieznosci_total": rozbieznosci_total,
            "bpp_empty_count": bpp_empty,
            "pbn_empty_count": pbn_empty,
            "both_present_count": both_present,
            "brakujacy_total": brakujacy_total,
            "missing_autor_count": missing_autor,
            "missing_link_count": missing_link,
            "missing_publication_count": missing_publication,
            # Stałe dla filtrów
            "TYP_BRAK_AUTORA": BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
            "TYP_BRAK_POWIAZANIA": BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
            "TYP_BRAK_PUBLIKACJI": BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        }


class RozbieznoscDyscyplinPBNDetailView(GroupRequiredMixin, DetailView):
    """Widok szczegółowy rozbieżności."""

    group_required = GR_WPROWADZANIE_DANYCH
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
            publikacja = wydawnictwo_autor.rekord
            context["autor"] = wydawnictwo_autor.autor
            context["publikacja"] = publikacja
            context["jednostka"] = wydawnictwo_autor.jednostka
            context["wydawnictwo_autor"] = wydawnictwo_autor
            context["publikacja_content_type"] = ContentType.objects.get_for_model(
                publikacja
            )

        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("komparator_pbn_udzialy.add_rozbieznoscdyscyplinpbn"),
    name="dispatch",
)
class RebuildDiscrepanciesView(View):
    """Widok do przebudowy rozbieżności.

    GET wyświetla ekran potwierdzenia, POST uruchamia zadanie Celery
    z ``clear_existing=True``.
    """

    template_name = "komparator_pbn_udzialy/rebuild_confirm.html"

    def get(self, request):
        pbn_data_fresh, pbn_stale_message, _ = is_pbn_publications_data_fresh()
        return render(
            request,
            self.template_name,
            {
                "pbn_data_fresh": pbn_data_fresh,
                "pbn_stale_message": pbn_stale_message,
            },
        )

    def post(self, request):
        pbn_data_fresh, pbn_stale_message, _ = is_pbn_publications_data_fresh()
        if not pbn_data_fresh:
            messages.error(
                request,
                f"Nie można przebudować rozbieżności: {pbn_stale_message}. "
                "Pobierz aktualne dane z PBN.",
            )
            return HttpResponseRedirect(reverse("komparator_pbn_udzialy:list"))

        try:
            from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

            task = porownaj_dyscypliny_pbn_task.delay(clear_existing=True)
            request.session["komparator_task_id"] = task.id

            messages.info(
                request,
                f"Przebudowa rozbieżności została uruchomiona w tle. "
                f"ID zadania: {task.id}",
            )

            return HttpResponseRedirect(
                reverse(
                    "komparator_pbn_udzialy:task_status",
                    kwargs={"task_id": task.id},
                )
            )

        except Exception as e:
            logger.exception("Błąd podczas uruchamiania zadania Celery")
            messages.error(
                request,
                f"Nie można uruchomić zadania w tle: {str(e)}",
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


class BrakAutoraDetailView(GroupRequiredMixin, DetailView):
    """Widok szczegółowy brakującego autora."""

    group_required = GR_WPROWADZANIE_DANYCH
    model = BrakAutoraWPublikacji
    template_name = "komparator_pbn_udzialy/brak_autora_detail.html"
    context_object_name = "brak_autora"

    def get_queryset(self):
        """Optymalizowany queryset."""
        return (
            super()
            .get_queryset()
            .select_related(
                "oswiadczenie_instytucji",
                "oswiadczenie_instytucji__publicationId",
                "pbn_scientist",
                "autor",
                "dyscyplina_pbn",
                "content_type",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        brak = self.object

        # Dodaj autora i publikację do kontekstu
        context["autor"] = brak.autor
        context["publikacja"] = brak.publikacja

        if brak.publikacja:
            context["publikacja_content_type"] = ContentType.objects.get_for_model(
                brak.publikacja
            )

        # Stałe dla szablonu
        context["TYP_BRAK_PUBLIKACJI"] = BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI
        context["TYP_BRAK_AUTORA"] = BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP
        context["TYP_BRAK_POWIAZANIA"] = BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA

        return context
