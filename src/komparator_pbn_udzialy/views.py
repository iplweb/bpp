import logging

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q, Value
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Uczelnia
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
from ewaluacja_common.okres import lata_okresu
from komparator_pbn_udzialy.models import (
    BrakAutoraWPublikacji,
    ProblemWrapper,
    RozbieznoscDyscyplinPBN,
)
from pbn_downloader_app.freshness import is_pbn_publications_data_fresh

logger = logging.getLogger(__name__)

#: Znaczniki tabeli źródłowej w połączonej liście problemów (UNION).
RODZAJ_ROZBIEZNOSC = "rozbieznosc"
RODZAJ_BRAK_AUTORA = "brak_autora"

#: Ścieżka od rekordu problemu do roku publikacji w PBN.
ROK_PUBLIKACJI_PBN = "oswiadczenie_instytucji__publicationId__year"


def filtr_uczelni(request):
    """``Q`` zawężające problemy do oświadczeń instytucji bieżącej uczelni.

    Lustro oświadczeń PBN jest wspólne dla całej instalacji; w instalacji
    wielouczelnianej każda uczelnia ma widzieć tylko swoje (oświadczenie
    wiąże się z uczelnią przez ``institutionId == uczelnia.pbn_uid`` — pole
    ``uczelnia`` oświadczenia bywa puste). W instalacji z jedną uczelnią nie
    filtrujemy niczego: lista wygląda jak dotąd, także gdy uczelnia nie ma
    ustawionego identyfikatora PBN albo oświadczenia mają inny.
    """
    if Uczelnia.objects.count() <= 1:
        return Q()
    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None or uczelnia.pbn_uid_id is None:
        # Nie wiadomo, czyje oświadczenia pokazać — nie pokazujemy cudzych.
        return Q(pk__in=[])
    return Q(oswiadczenie_instytucji__institutionId_id=uczelnia.pbn_uid_id)


def brak_identyfikatora_pbn(request):
    """Instalacja wielouczelniana, a bieżąca uczelnia nie ma „Odpowiednika
    w PBN” (albo nie da się jej ustalić): nie wiadomo, które oświadczenia jej
    dotyczą. Widoki pokazują wtedy komunikat zamiast pustej listy."""
    if Uczelnia.objects.count() <= 1:
        return False
    uczelnia = Uczelnia.objects.get_for_request(request)
    return uczelnia is None or uczelnia.pbn_uid_id is None


class BezIdentyfikatoraPBNMixin:
    """Zamiast widoku — strona z komunikatem, gdy ``brak_identyfikatora_pbn``."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and brak_identyfikatora_pbn(request):
            return render(
                request,
                "komparator_pbn_udzialy/brak_identyfikatora_pbn.html",
                {"biezaca_uczelnia": Uczelnia.objects.get_for_request(request)},
            )
        return super().dispatch(request, *args, **kwargs)


def _autorzy_bpp(search):
    """``Q`` dla rozbieżności dyscyplin: autor BPP (nazwisko albo imiona)
    powiązania autor–praca, którego dotyczy rozbieżność. Powiązanie jest
    kluczem generycznym, stąd podzapytanie na każdy typ pracy."""
    warunek = Q()
    for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
        pasujace = model.objects.filter(
            Q(autor__nazwisko__icontains=search) | Q(autor__imiona__icontains=search)
        ).values("pk")
        warunek |= Q(
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=pasujace,
        )
    return warunek


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


class ProblemyPBNListView(GroupRequiredMixin, BezIdentyfikatoraPBNMixin, View):
    """Widok listy wszystkich problemów PBN - rozbieżności i brakujących autorów."""

    group_required = GR_WPROWADZANIE_DANYCH
    template_name = "komparator_pbn_udzialy/list.html"

    paginate_by = 50

    def get(self, request):
        # Filtry
        search = request.GET.get("search", "")
        filter_type = request.GET.get("filter", "")
        # Bez ręcznego zakresu: lata okresu ewaluacji z paska okresu.
        okres_od, okres_do = lata_okresu(request)
        rok_min = request.GET.get("rok_min", str(okres_od))
        rok_max = request.GET.get("rok_max", str(okres_do))

        uczelnia = filtr_uczelni(request)
        rozbieznosci = self._get_rozbieznosci(
            search, filter_type, rok_min, rok_max
        ).filter(uczelnia)
        brakujacy = self._get_brakujacy(search, filter_type, rok_min, rok_max).filter(
            uczelnia
        )

        # Obie tabele w jednym zapytaniu (UNION ALL): filtrowanie, sortowanie
        # (najnowsze pierwsze) i stronicowanie robi baza, a nie Python.
        klucze = (
            rozbieznosci.annotate(rodzaj=Value(RODZAJ_ROZBIEZNOSC))
            .values_list("rodzaj", "pk", "created_at")
            .union(
                brakujacy.annotate(rodzaj=Value(RODZAJ_BRAK_AUTORA)).values_list(
                    "rodzaj", "pk", "created_at"
                ),
                all=True,
            )
            .order_by("-created_at", "rodzaj", "-pk")
        )
        page_obj = Paginator(klucze, self.paginate_by).get_page(request.GET.get("page"))

        # Statystyki
        stats = self._get_stats(rok_min, rok_max, uczelnia)

        # PBN data freshness check
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_publications_data_fresh()
        )

        context = {
            "problemy": self._problemy_strony(page_obj.object_list),
            "page_obj": page_obj,
            "paginator": page_obj.paginator,
            "is_paginated": page_obj.has_other_pages(),
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

    @staticmethod
    def _problemy_strony(klucze):
        """Rekordy jednej strony (w kolejności ``klucze``) z danymi do tabeli
        dociągniętymi stałą liczbą zapytań — bez zapytań na wiersz."""
        klucze = list(klucze)
        pk_wg_rodzaju = {RODZAJ_ROZBIEZNOSC: [], RODZAJ_BRAK_AUTORA: []}
        for rodzaj, pk, _created_at in klucze:
            pk_wg_rodzaju[rodzaj].append(pk)

        obiekty = {}
        if pk_wg_rodzaju[RODZAJ_ROZBIEZNOSC]:
            for obj in (
                RozbieznoscDyscyplinPBN.objects.filter(
                    pk__in=pk_wg_rodzaju[RODZAJ_ROZBIEZNOSC]
                )
                .select_related(
                    "oswiadczenie_instytucji__publicationId",
                    "dyscyplina_bpp",
                    "dyscyplina_pbn",
                )
                .prefetch_related(
                    GenericPrefetch(
                        "wydawnictwo_autor",
                        [
                            model.objects.select_related("autor__tytul", "rekord")
                            for model in (
                                Wydawnictwo_Ciagle_Autor,
                                Wydawnictwo_Zwarte_Autor,
                            )
                        ],
                    )
                )
            ):
                obiekty[RODZAJ_ROZBIEZNOSC, obj.pk] = obj
        if pk_wg_rodzaju[RODZAJ_BRAK_AUTORA]:
            for obj in BrakAutoraWPublikacji.objects.filter(
                pk__in=pk_wg_rodzaju[RODZAJ_BRAK_AUTORA]
            ).select_related(
                "oswiadczenie_instytucji__publicationId",
                "pbn_scientist",
                "dyscyplina_pbn",
            ):
                obiekty[RODZAJ_BRAK_AUTORA, obj.pk] = obj

        return [
            ProblemWrapper(obiekty[rodzaj, pk])
            for rodzaj, pk, _created_at in klucze
            if (rodzaj, pk) in obiekty
        ]

    def _get_rozbieznosci(self, search, filter_type, rok_min, rok_max):
        """Rozbieżności dyscyplin z uwzględnieniem filtrów (queryset)."""
        queryset = RozbieznoscDyscyplinPBN.objects.all()

        # Wyszukiwanie
        if search:
            queryset = queryset.filter(
                Q(oswiadczenie_instytucji__publicationId__title__icontains=search)
                | Q(dyscyplina_bpp__nazwa__icontains=search)
                | Q(dyscyplina_pbn__nazwa__icontains=search)
                | _autorzy_bpp(search)
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
            return queryset.none()

        return filtruj_lata(queryset, rok_min, rok_max)

    def _get_brakujacy(self, search, filter_type, rok_min, rok_max):
        """Brakujący autorzy z uwzględnieniem filtrów (queryset)."""
        queryset = BrakAutoraWPublikacji.objects.all()

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
            return queryset.none()

        return filtruj_lata(queryset, rok_min, rok_max)

    def _get_stats(self, rok_min, rok_max, uczelnia=Q()):
        """Statystyki wszystkich typów problemów dla tego samego zakresu lat
        co lista (inaczej kafelki pokazywałyby inne liczby niż tabela)."""
        rozbieznosci = filtruj_lata(
            RozbieznoscDyscyplinPBN.objects.filter(uczelnia), rok_min, rok_max
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
            BrakAutoraWPublikacji.objects.filter(uczelnia), rok_min, rok_max
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


class RozbieznoscDyscyplinPBNDetailView(
    GroupRequiredMixin, BezIdentyfikatoraPBNMixin, DetailView
):
    """Widok szczegółowy rozbieżności."""

    group_required = GR_WPROWADZANIE_DANYCH
    model = RozbieznoscDyscyplinPBN
    template_name = "komparator_pbn_udzialy/detail.html"
    context_object_name = "rozbieznosc"

    def get_queryset(self):
        """Optymalizowany queryset (w instalacji wielouczelnianej tylko
        problemy oświadczeń bieżącej uczelni — cudze dają 404)."""
        return (
            super()
            .get_queryset()
            .filter(filtr_uczelni(self.request))
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


class BrakAutoraDetailView(GroupRequiredMixin, BezIdentyfikatoraPBNMixin, DetailView):
    """Widok szczegółowy brakującego autora."""

    group_required = GR_WPROWADZANIE_DANYCH
    model = BrakAutoraWPublikacji
    template_name = "komparator_pbn_udzialy/brak_autora_detail.html"
    context_object_name = "brak_autora"

    def get_queryset(self):
        """Optymalizowany queryset (w instalacji wielouczelnianej tylko
        problemy oświadczeń bieżącej uczelni — cudze dają 404)."""
        return (
            super()
            .get_queryset()
            .filter(filtr_uczelni(self.request))
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
