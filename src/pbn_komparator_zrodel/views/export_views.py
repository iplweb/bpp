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
from .forms import DyscyplinyFilterForm, FilterForm
from .okres import (
    filtruj_publikacje_w_okresie,
    lata_okresu,
    tylko_z_publikacjami_w_okresie,
)


class ExportDyscyplinyXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności dyscyplin do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # When no GET params, use defaults
        okres_od, okres_do = lata_okresu(self.request)
        if not self.request.GET:
            return okres_od, okres_do, "", True, False, True

        form = DyscyplinyFilterForm(
            self.request.GET, domyslne_lata=(okres_od, okres_do)
        )
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            z_publikacjami_w_okresie = tylko_z_publikacjami_w_okresie(self.request)
            return (
                rok_od,
                rok_do,
                search,
                tylko_rozbieznosci,
                bez_publikacji,
                z_publikacjami_w_okresie,
            )
        return okres_od, okres_do, "", True, False, True

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            z_publikacjami_w_okresie,
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

        # Filtr tylko źródła z publikacjami z lat wybranego okresu ewaluacji
        if z_publikacjami_w_okresie:
            queryset = filtruj_publikacje_w_okresie(
                queryset, *lata_okresu(self.request)
            )

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
        from bpp.util import sanitize_xlsx_workbook

        sanitize_xlsx_workbook(wb)
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response


class ExportXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request — te same co lista, łącznie
        z filtrami publikacji, żeby eksport obejmował dokładnie to, co widać
        na liście."""
        # Przy pierwszym wejściu (brak GET params) domyślne wartości jak na liście
        okres_od, okres_do = lata_okresu(self.request)
        domyslne = (okres_od, okres_do, "", "", True, False, True)
        if not self.request.GET:
            return domyslne

        form = FilterForm(self.request.GET, domyslne_lata=(okres_od, okres_do))
        if form.is_valid():
            return (
                form.cleaned_data["rok_od"],
                form.cleaned_data["rok_do"],
                form.cleaned_data["search"],
                form.cleaned_data["dyscyplina"],
                "tylko_rozbieznosci" in self.request.GET,
                "bez_publikacji" in self.request.GET,
                tylko_z_publikacjami_w_okresie(self.request),
            )
        return domyslne

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        (
            rok_od,
            rok_do,
            search,
            dyscyplina,
            tylko_rozbieznosci,
            bez_publikacji,
            z_publikacjami_w_okresie,
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

        if dyscyplina:
            queryset = queryset.filter(
                Q(dyscypliny_bpp__icontains=dyscyplina)
                | Q(dyscypliny_pbn__icontains=dyscyplina)
            )

        # Filtr tylko rozbieżności punktów
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        # Filtr tylko źródła z publikacjami (jak na liście)
        if bez_publikacji:
            queryset = queryset.filter(
                Exists(
                    Wydawnictwo_Ciagle.objects.filter(zrodlo_id=OuterRef("zrodlo_id"))
                )
            )

        # Filtr tylko źródła z publikacjami z lat wybranego okresu ewaluacji
        if z_publikacjami_w_okresie:
            queryset = filtruj_publikacje_w_okresie(
                queryset, *lata_okresu(self.request)
            )

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
        from bpp.util import sanitize_xlsx_workbook

        sanitize_xlsx_workbook(wb)
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response
