"""Widoki eksportu rozbieżności do XLSX."""

from datetime import datetime
from io import BytesIO

from braces.views import GroupRequiredMixin
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponse
from django.views import View
from openpyxl import Workbook

from bpp.models import Wydawnictwo_Ciagle
from bpp.util import worksheet_columns_autosize, worksheet_create_table

from ..models import RozbieznoscZrodlaPBN
from .constants import DEFAULT_ROK_DO, DEFAULT_ROK_OD
from .forms import DyscyplinyFilterForm, FilterForm


class ExportDyscyplinyXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności dyscyplin do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # When no GET params, use defaults
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

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
        ) = self.get_filter_params()

        queryset = RozbieznoscZrodlaPBN.objects.select_related(
            "zrodlo", "zrodlo__pbn_uid"
        )
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

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

        return queryset.order_by("zrodlo__nazwa", "rok")

    def get(self, request):
        queryset = self.get_queryset()

        wb = Workbook()
        ws = wb.active
        ws.title = "Rozbieżności dyscyplin"

        # Nagłówki
        headers = [
            "Źródło",
            "ISSN",
            "e-ISSN",
            "Rok",
            "Dyscypliny BPP",
            "Dyscypliny PBN",
            "Rozbieżność",
        ]
        ws.append(headers)

        def format_dyscypliny(value):
            """Add spaces after commas in discipline list."""
            if not value:
                return ""
            return ", ".join(c.strip() for c in value.split(","))

        # Dane
        for rozbieznosc in queryset:
            ws.append(
                [
                    rozbieznosc.zrodlo.nazwa,
                    rozbieznosc.zrodlo.issn or "",
                    rozbieznosc.zrodlo.e_issn or "",
                    rozbieznosc.rok,
                    format_dyscypliny(rozbieznosc.dyscypliny_bpp),
                    format_dyscypliny(rozbieznosc.dyscypliny_pbn),
                    "Tak" if rozbieznosc.ma_rozbieznosc_dyscyplin else "Nie",
                ]
            )

        # Formatowanie
        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title="RozbieznosciDyscyplin")

        # Odpowiedź HTTP
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"rozbieznosci_dyscyplin_pbn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response


class ExportXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request (jak w ListView)."""
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

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        rok_od, rok_do, search, dyscyplina, tylko_rozbieznosci = (
            self.get_filter_params()
        )

        queryset = RozbieznoscZrodlaPBN.objects.select_related(
            "zrodlo", "zrodlo__pbn_uid"
        )
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

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

        # Filtr tylko rozbieżności punktów
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        return queryset.order_by("zrodlo__nazwa", "rok")

    def get(self, request):
        queryset = self.get_queryset()

        wb = Workbook()
        ws = wb.active
        ws.title = "Rozbieżności źródeł PBN"

        # Nagłówki
        headers = [
            "Źródło",
            "ISSN",
            "e-ISSN",
            "Rok",
            "Punkty BPP",
            "Punkty PBN",
            "Różnica punktów",
            "Dyscypliny BPP",
            "Dyscypliny PBN",
            "Rozbieżność punktów",
            "Rozbieżność dyscyplin",
        ]
        ws.append(headers)

        # Dane
        for rozbieznosc in queryset:
            roznica = None
            if (
                rozbieznosc.punkty_bpp is not None
                and rozbieznosc.punkty_pbn is not None
            ):
                roznica = float(rozbieznosc.punkty_bpp - rozbieznosc.punkty_pbn)

            ws.append(
                [
                    rozbieznosc.zrodlo.nazwa,
                    rozbieznosc.zrodlo.issn or "",
                    rozbieznosc.zrodlo.e_issn or "",
                    rozbieznosc.rok,
                    float(rozbieznosc.punkty_bpp) if rozbieznosc.punkty_bpp else None,
                    float(rozbieznosc.punkty_pbn) if rozbieznosc.punkty_pbn else None,
                    roznica,
                    rozbieznosc.dyscypliny_bpp or "",
                    rozbieznosc.dyscypliny_pbn or "",
                    "Tak" if rozbieznosc.ma_rozbieznosc_punktow else "Nie",
                    "Tak" if rozbieznosc.ma_rozbieznosc_dyscyplin else "Nie",
                ]
            )

        # Formatowanie
        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title="RozbieznosciZrodelPBN")

        # Odpowiedź HTTP
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = (
            f"rozbieznosci_zrodel_pbn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response
