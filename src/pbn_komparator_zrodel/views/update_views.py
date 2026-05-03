"""Widoki aktualizacji źródeł — pojedyncze i masowe."""

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View

from bpp.models import Wydawnictwo_Ciagle

from ..models import RozbieznoscZrodlaPBN
from .constants import (
    DEFAULT_ROK_DO,
    DEFAULT_ROK_OD,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
)
from .forms import DyscyplinyFilterForm, FilterForm


class AktualizujPojedynczyView(GroupRequiredMixin, View):
    """Aktualizacja pojedynczego źródła."""

    group_required = "wprowadzanie danych"

    def post(self, request, pk):
        from ..update_utils import aktualizuj_zrodlo_z_pbn

        typ = request.POST.get("typ", "oba")  # punkty, dyscypliny, oba

        try:
            rozbieznosc = RozbieznoscZrodlaPBN.objects.select_related("zrodlo").get(
                pk=pk
            )
            aktualizuj_zrodlo_z_pbn(
                rozbieznosc.zrodlo,
                rozbieznosc.rok,
                aktualizuj_punkty=(typ in ["punkty", "oba"]),
                aktualizuj_dyscypliny=(typ in ["dyscypliny", "oba"]),
                user=request.user,
            )
            messages.success(
                request,
                f"Zaktualizowano źródło {rozbieznosc.zrodlo.nazwa} za rok {rozbieznosc.rok}",
            )
        except RozbieznoscZrodlaPBN.DoesNotExist:
            messages.error(request, "Nie znaleziono rozbieżności")
        except Exception as e:
            messages.error(request, f"Błąd podczas aktualizacji: {e}")

        # Przekieruj z powrotem do listy z zachowaniem filtrów
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return HttpResponseRedirect(referer)
        return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))


class AktualizujWszystkieView(GroupRequiredMixin, View):
    """Aktualizacja wszystkich źródeł z rozbieżnościami."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # Przy pierwszym wejściu (brak GET params) domyślnie checkbox zaznaczony
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

        form = FilterForm(self.request.GET)
        if form.is_valid():
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            return (
                form.cleaned_data["rok_od"],
                form.cleaned_data["rok_do"],
                form.cleaned_data["search"],
                form.cleaned_data["dyscyplina"],
                tylko_rozbieznosci,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

    def post(self, request):
        from ..tasks import aktualizuj_wszystkie_task

        typ = request.POST.get("typ", "oba")
        rok_od, rok_do, search, dyscyplina, tylko_rozbieznosci = (
            self.get_filter_params()
        )

        # Buduj queryset z filtrami
        queryset = RozbieznoscZrodlaPBN.objects.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        if dyscyplina:
            queryset = queryset.filter(
                Q(dyscypliny_bpp__icontains=dyscyplina)
                | Q(dyscypliny_pbn__icontains=dyscyplina)
            )

        # Filtr tylko rozbieżności punktów (z checkboxa)
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        # Dodatkowy filtr na podstawie typu aktualizacji
        if typ == "punkty":
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)
        elif typ == "dyscypliny":
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        pks = list(queryset.values_list("pk", flat=True))

        if not pks:
            messages.warning(request, "Brak rekordów do aktualizacji")
            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))

        if len(pks) >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            # Uruchom jako task Celery
            task = aktualizuj_wszystkie_task.delay(
                pks=pks,
                typ=typ,
                user_id=request.user.id,
            )
            return HttpResponseRedirect(
                reverse(
                    "pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id}
                )
            )
        else:
            # Wykonaj synchronicznie
            from ..update_utils import aktualizuj_wiele_zrodel

            result = aktualizuj_wiele_zrodel(pks, typ=typ, user=request.user)
            if result["errors"]:
                messages.warning(
                    request,
                    f"Zaktualizowano {result['updated']} rekordów. Błędy: {result['errors']}.",
                )
            else:
                messages.success(
                    request, f"Zaktualizowano {result['updated']} rekordów."
                )

            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))


class AktualizujWszystkieDyscyplinyView(GroupRequiredMixin, View):
    """Aktualizacja wszystkich dyscyplin źródeł z rozbieżnościami."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

        form = DyscyplinyFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            bez_publikacji_2022_2025 = "bez_publikacji_2022_2025" in self.request.GET
            return (
                rok_od,
                rok_do,
                search,
                tylko_rozbieznosci,
                bez_publikacji,
                bez_publikacji_2022_2025,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

    def post(self, request):
        from ..tasks import aktualizuj_wszystkie_task

        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
        ) = self.get_filter_params()

        # Buduj queryset z filtrami
        queryset = RozbieznoscZrodlaPBN.objects.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        # Filtr tylko rozbieżności dyscyplin
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        # Filtr tylko źródła z publikacjami
        if bez_publikacji:
            has_publications = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id")
            )
            queryset = queryset.filter(Exists(has_publications))

        # Filtr tylko źródła z publikacjami 2022-2025
        if bez_publikacji_2022_2025:
            has_publications_2022_2025 = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id"), rok__gte=2022, rok__lte=2025
            )
            queryset = queryset.filter(Exists(has_publications_2022_2025))

        # Tylko te z rozbieżnościami dyscyplin
        queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        pks = list(queryset.values_list("pk", flat=True))

        if not pks:
            messages.warning(request, "Brak rekordów do aktualizacji")
            return HttpResponseRedirect(
                reverse("pbn_komparator_zrodel:dyscypliny_list")
            )

        if len(pks) >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            # Uruchom jako task Celery
            task = aktualizuj_wszystkie_task.delay(
                pks=pks,
                typ="dyscypliny",
                user_id=request.user.id,
            )
            return HttpResponseRedirect(
                reverse(
                    "pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id}
                )
            )
        else:
            # Wykonaj synchronicznie
            from ..update_utils import aktualizuj_wiele_zrodel

            result = aktualizuj_wiele_zrodel(pks, typ="dyscypliny", user=request.user)
            if result["errors"]:
                messages.warning(
                    request,
                    f"Zaktualizowano {result['updated']} rekordów. Błędy: {result['errors']}.",
                )
            else:
                messages.success(
                    request, f"Zaktualizowano {result['updated']} rekordów."
                )

            return HttpResponseRedirect(
                reverse("pbn_komparator_zrodel:dyscypliny_list")
            )
