"""Widoki listy możliwości odpinania."""

import logging
from decimal import Decimal

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import Uczelnia

logger = logging.getLogger(__name__)


def _get_dyscyplina_filter(request):
    """Extract and validate dyscyplina ID from request."""
    dyscyplina_id = request.GET.get("dyscyplina")
    if not dyscyplina_id:
        return None

    try:
        return int(dyscyplina_id)
    except (ValueError, TypeError):
        return None


def _cache_rekord_objects(opportunities_qs):
    """Preload Rekord objects to avoid N+1 queries."""
    from bpp.models import Rekord

    all_opportunities = list(opportunities_qs)
    rekord_ids = [opp.rekord_id for opp in all_opportunities]
    rekordy = {r.pk: r for r in Rekord.objects.filter(pk__in=rekord_ids)}

    # Attach rekord objects to opportunities
    for opp in all_opportunities:
        opp._cached_rekord = rekordy.get(opp.rekord_id)

    return all_opportunities


def _get_punkty_kbn(opportunity):
    """Safely get punkty_kbn from opportunity's rekord."""
    try:
        return opportunity.rekord.original.punkty_kbn or Decimal("0")
    except (AttributeError, TypeError):
        return Decimal("0")


def _filter_by_punktacja(opportunities, punktacja_zrodla):
    """Filter opportunities by punktacja_zrodla range."""
    if not punktacja_zrodla:
        return opportunities

    punktacja_ranges = {
        "0-100": lambda p: p < Decimal("100"),
        "100-140": lambda p: Decimal("100") <= p < Decimal("140"),
        "140-200": lambda p: Decimal("140") <= p < Decimal("200"),
        "200+": lambda p: p >= Decimal("200"),
    }

    filter_func = punktacja_ranges.get(punktacja_zrodla)
    if not filter_func:
        return opportunities

    return [opp for opp in opportunities if filter_func(_get_punkty_kbn(opp))]


def _create_sort_key_function(sort_by):
    """Create a sort key function based on sort_by parameter."""
    # Define sort key extractors
    sort_keys = {
        "tytul": lambda opp: opp.rekord_tytul or "",
        "punktacja": _get_punkty_kbn,
        "dyscyplina": lambda opp: (
            opp.dyscyplina_naukowa.nazwa if opp.dyscyplina_naukowa else ""
        ),
        "autor_a": lambda opp: (
            opp.autor_could_benefit.nazwisko if opp.autor_could_benefit else ""
        ),
        "slots_missing": lambda opp: opp.slots_missing or Decimal("0"),
        "slot_in_work": lambda opp: opp.slot_in_work or Decimal("0"),
        "punkty_a": lambda opp: opp.punkty_roznica_a or Decimal("0"),
        "sloty_a": lambda opp: opp.sloty_roznica_a or Decimal("0"),
        "punkty_b": lambda opp: opp.punkty_roznica_b or Decimal("0"),
        "sloty_b": lambda opp: opp.sloty_roznica_b or Decimal("0"),
        "autor_b": lambda opp: (
            opp.autor_currently_using.nazwisko if opp.autor_currently_using else ""
        ),
        "makes_sense": lambda opp: opp.makes_sense,
    }

    # Return the requested sort key function, defaulting to punkty_b
    return sort_keys.get(sort_by, sort_keys["punkty_b"])


@login_required
def unpinning_opportunities_list(request):
    """
    Wyświetla listę możliwości odpinania prac wieloautorskich.
    """
    from bpp.models import Dyscyplina_Naukowa
    from ewaluacja_metryki.models import StatusGenerowania

    from ..models import StatusUnpinningAnalyzy, UnpinningOpportunity

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    # Check if unpinning analysis is already running - używa modelu singleton zamiast sesji
    status_unpinning = StatusUnpinningAnalyzy.get_or_create()
    task_id = status_unpinning.task_id if status_unpinning.w_trakcie else None

    if task_id:
        task = AsyncResult(task_id)
        # Check if task is still running (PENDING, STARTED, or PROGRESS)
        if task.state in ["PENDING", "STARTED", "PROGRESS"]:
            messages.info(
                request,
                "Analiza możliwości odpinania jest w trakcie. "
                "Przekierowuję do strony postępu...",
            )
            return redirect(
                "ewaluacja_optymalizacja:unpinning-combined-status", task_id=task_id
            )
        # Task finished or failed - clear from database
        if task.state in ["SUCCESS", "FAILURE"]:
            status_unpinning.zakoncz("Zadanie zakończone")

    # Also check if metrics generation is running
    status = StatusGenerowania.get_or_create()
    if status.w_trakcie and task_id:
        # Metrics are running as part of unpinning chain
        messages.info(
            request,
            "Przeliczanie metryk dla analizy odpinania jest w trakcie. "
            "Przekierowuję do strony postępu...",
        )
        return redirect(
            "ewaluacja_optymalizacja:unpinning-combined-status", task_id=task_id
        )

    # Podstawowe filtrowanie
    opportunities_qs = UnpinningOpportunity.objects.filter(uczelnia=uczelnia)

    # Filtr po dyscyplinie
    dyscyplina_id = _get_dyscyplina_filter(request)
    if dyscyplina_id:
        opportunities_qs = opportunities_qs.filter(dyscyplina_naukowa_id=dyscyplina_id)

    # Filtr "tylko sensowne"
    only_sensible = request.GET.get("only_sensible") == "1"
    if only_sensible:
        opportunities_qs = opportunities_qs.filter(makes_sense=True)

    # Select related dla optymalizacji
    opportunities_qs = opportunities_qs.select_related(
        "autor_could_benefit",
        "autor_currently_using",
        "dyscyplina_naukowa",
        "metryka_could_benefit",
        "metryka_currently_using",
        "metryka_could_benefit__autor",
        "metryka_currently_using__autor",
    )

    # Preload Rekord objects
    all_opportunities = _cache_rekord_objects(opportunities_qs)

    # Filtr po punktacji źródła
    punktacja_zrodla = request.GET.get("punktacja_zrodla")
    all_opportunities = _filter_by_punktacja(all_opportunities, punktacja_zrodla)

    # Sortowanie
    sort_by = request.GET.get("sort_by", "punkty_b")
    sort_dir = request.GET.get("sort_dir", "desc")
    sort_key = _create_sort_key_function(sort_by)
    all_opportunities = sorted(
        all_opportunities, key=sort_key, reverse=(sort_dir == "desc")
    )

    # Paginacja po filtrowaniu i sortowaniu
    from django.core.paginator import Paginator

    paginator = Paginator(all_opportunities, 50)
    page_number = request.GET.get("page")
    opportunities = paginator.get_page(page_number)

    # Statystyki
    total_count = UnpinningOpportunity.objects.filter(uczelnia=uczelnia).count()
    sensible_count = UnpinningOpportunity.objects.filter(
        uczelnia=uczelnia, makes_sense=True
    ).count()
    sensible_percentage = (
        round((sensible_count / total_count) * 100, 1) if total_count > 0 else 0
    )

    # Lista dyscyplin dla filtra
    dyscypliny = Dyscyplina_Naukowa.objects.filter(
        pk__in=UnpinningOpportunity.objects.filter(uczelnia=uczelnia).values_list(
            "dyscyplina_naukowa_id", flat=True
        )
    ).order_by("nazwa")

    context = {
        "opportunities": opportunities,
        "total_count": total_count,
        "sensible_count": sensible_count,
        "sensible_percentage": sensible_percentage,
        "dyscypliny": dyscypliny,
        "selected_dyscyplina": dyscyplina_id,
        "only_sensible": only_sensible,
        "selected_punktacja_zrodla": punktacja_zrodla or "",
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "status_unpinning": status_unpinning,
    }

    return render(
        request, "ewaluacja_optymalizacja/unpinning_opportunities_list.html", context
    )


@login_required
def export_unpinning_opportunities_xlsx(request):  # noqa: C901
    """Export unpinning opportunities list to XLSX format with filters applied"""
    import datetime
    from decimal import Decimal

    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    from bpp.models import Dyscyplina_Naukowa, Rekord
    from ewaluacja_common.models import Rodzaj_Autora

    from ..models import UnpinningOpportunity

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    # Filtrowanie (identyczne jak w unpinning_opportunities_list)
    opportunities_qs = UnpinningOpportunity.objects.filter(uczelnia=uczelnia)

    # Filtr po dyscyplinie (opcjonalnie)
    dyscyplina_id = request.GET.get("dyscyplina")
    if dyscyplina_id:
        try:
            dyscyplina_id = int(dyscyplina_id)
            opportunities_qs = opportunities_qs.filter(
                dyscyplina_naukowa_id=dyscyplina_id
            )
        except (ValueError, TypeError):
            pass

    # Filtr "tylko sensowne"
    only_sensible = request.GET.get("only_sensible")
    if only_sensible == "1":
        opportunities_qs = opportunities_qs.filter(makes_sense=True)

    # Select related dla optymalizacji
    opportunities_qs = opportunities_qs.select_related(
        "autor_could_benefit",
        "autor_currently_using",
        "dyscyplina_naukowa",
        "metryka_could_benefit",
        "metryka_currently_using",
        "metryka_could_benefit__autor",
        "metryka_currently_using__autor",
        "metryka_could_benefit__jednostka",
        "metryka_currently_using__jednostka",
    )

    # Preload Rekord objects to avoid N+1 queries
    all_opportunities = list(opportunities_qs)
    rekord_ids = [opp.rekord_id for opp in all_opportunities]
    rekordy = {r.pk: r for r in Rekord.objects.filter(pk__in=rekord_ids)}

    # Attach rekord objects to opportunities
    for opp in all_opportunities:
        opp._cached_rekord = rekordy.get(opp.rekord_id)

    # Filtr po punktacji źródła (identyczne jak w unpinning_opportunities_list)
    punktacja_zrodla = request.GET.get("punktacja_zrodla")
    if punktacja_zrodla:
        filtered_opportunities = []
        for opp in all_opportunities:
            try:
                punkty = opp.rekord.original.punkty_kbn or Decimal("0")
            except (AttributeError, TypeError):
                punkty = Decimal("0")

            if punktacja_zrodla == "0-100" and punkty < Decimal("100"):
                filtered_opportunities.append(opp)
            elif punktacja_zrodla == "100-140" and Decimal("100") <= punkty < Decimal(
                "140"
            ):
                filtered_opportunities.append(opp)
            elif punktacja_zrodla == "140-200" and Decimal("140") <= punkty < Decimal(
                "200"
            ):
                filtered_opportunities.append(opp)
            elif punktacja_zrodla == "200+" and punkty >= Decimal("200"):
                filtered_opportunities.append(opp)

        all_opportunities = filtered_opportunities

    opportunities_qs = all_opportunities

    # Setup workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Możliwości odpinania"

    # Define styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        start_color="366092", end_color="366092", fill_type="solid"
    )
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    even_row_fill = PatternFill(
        start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"
    )

    sensible_row_fill = PatternFill(
        start_color="E7F7E7", end_color="E7F7E7", fill_type="solid"
    )

    # Define headers
    headers = [
        "Lp.",
        "Tytuł pracy",
        "Punktacja źródła",
        "Dyscyplina",
        "Autor A (do odpięcia)",
        "Rodzaj autora A",
        "ID systemu kadrowego A",
        "Jednostka A",
        "% wykorzystania slotów A",
        "Sloty nazbierane A",
        "Sloty maksymalne A",
        "B może wziąć (slotów)",
        "Slot w pracy",
        "Różnica punktów A",
        "Różnica slotów A",
        "Różnica punktów B",
        "Różnica slotów B",
        "Autor B (skorzysta)",
        "Rodzaj autora B",
        "ID systemu kadrowego B",
        "Jednostka B",
        "% wykorzystania slotów B",
        "Sloty nazbierane B",
        "Sloty maksymalne B",
        "Sensowne?",
    ]

    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Helper function to format rodzaj_autora
    def format_rodzaj_autora(metryka):
        if metryka.rodzaj_autora == " ":
            return "Brak danych"
        try:
            rodzaj = Rodzaj_Autora.objects.get(skrot=metryka.rodzaj_autora)
            return rodzaj.nazwa
        except Rodzaj_Autora.DoesNotExist:
            return metryka.rodzaj_autora

    # Write data rows
    last_data_row = 1
    for row_idx, opp in enumerate(opportunities_qs, 2):
        last_data_row = row_idx

        # Determine row fill (sensible = green, otherwise alternating)
        if opp.makes_sense:
            row_fill = sensible_row_fill
        else:
            row_fill = even_row_fill if row_idx % 2 == 0 else None

        col = 1

        # Lp.
        cell = ws.cell(row=row_idx, column=col, value=row_idx - 1)
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Tytuł pracy
        cell = ws.cell(row=row_idx, column=col, value=opp.rekord_tytul)
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Punktacja źródła
        try:
            punkty_kbn = float(opp.rekord.original.punkty_kbn or 0)
        except (AttributeError, TypeError, ValueError):
            punkty_kbn = 0
        cell = ws.cell(row=row_idx, column=col, value=punkty_kbn)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Dyscyplina
        cell = ws.cell(row=row_idx, column=col, value=opp.dyscyplina_naukowa.nazwa)
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Autor A (do odpięcia)
        cell = ws.cell(row=row_idx, column=col, value=str(opp.autor_could_benefit))
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Rodzaj autora A
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=format_rodzaj_autora(opp.metryka_could_benefit),
        )
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # ID systemu kadrowego A
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=opp.autor_could_benefit.system_kadrowy_id or "",
        )
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Jednostka A
        jednostka_a = (
            opp.metryka_could_benefit.jednostka.nazwa
            if opp.metryka_could_benefit.jednostka
            else "-"
        )
        cell = ws.cell(row=row_idx, column=col, value=jednostka_a)
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # % wykorzystania slotów A
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_could_benefit.procent_wykorzystania_slotow) / 100,
        )
        cell.number_format = "0.00%"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Sloty nazbierane A
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_could_benefit.slot_nazbierany),
        )
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Sloty maksymalne A
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_could_benefit.slot_maksymalny),
        )
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # B może wziąć (slotów)
        cell = ws.cell(row=row_idx, column=col, value=float(opp.slots_missing))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Slot w pracy
        cell = ws.cell(row=row_idx, column=col, value=float(opp.slot_in_work))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Różnica punktów A
        cell = ws.cell(row=row_idx, column=col, value=float(opp.punkty_roznica_a))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Różnica slotów A
        cell = ws.cell(row=row_idx, column=col, value=float(opp.sloty_roznica_a))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Różnica punktów B
        cell = ws.cell(row=row_idx, column=col, value=float(opp.punkty_roznica_b))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Różnica slotów B
        cell = ws.cell(row=row_idx, column=col, value=float(opp.sloty_roznica_b))
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Autor B (skorzysta)
        cell = ws.cell(row=row_idx, column=col, value=str(opp.autor_currently_using))
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Rodzaj autora B
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=format_rodzaj_autora(opp.metryka_currently_using),
        )
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # ID systemu kadrowego B
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=opp.autor_currently_using.system_kadrowy_id or "",
        )
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Jednostka B
        jednostka_b = (
            opp.metryka_currently_using.jednostka.nazwa
            if opp.metryka_currently_using.jednostka
            else "-"
        )
        cell = ws.cell(row=row_idx, column=col, value=jednostka_b)
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # % wykorzystania slotów B
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_currently_using.procent_wykorzystania_slotow) / 100,
        )
        cell.number_format = "0.00%"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Sloty nazbierane B
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_currently_using.slot_nazbierany),
        )
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Sloty maksymalne B
        cell = ws.cell(
            row=row_idx,
            column=col,
            value=float(opp.metryka_currently_using.slot_maksymalny),
        )
        cell.number_format = "0.00"
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

        # Sensowne?
        cell = ws.cell(
            row=row_idx, column=col, value="TAK" if opp.makes_sense else "NIE"
        )
        cell.border = thin_border
        if row_fill:
            cell.fill = row_fill
        col += 1

    # Setup auto-filter, freeze panes
    if last_data_row > 1:
        last_col_letter = get_column_letter(len(headers))
        filter_range = f"A1:{last_col_letter}{last_data_row}"
        ws.auto_filter.ref = filter_range

    ws.freeze_panes = ws["A2"]

    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except BaseException:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Add summary
    summary_row = last_data_row + 2 if last_data_row > 1 else 3
    ws.cell(row=summary_row, column=1, value="Podsumowanie:")
    ws.cell(row=summary_row + 1, column=1, value="Liczba wierszy:")
    ws.cell(row=summary_row + 1, column=2, value=len(opportunities_qs))

    # Add filter information
    filter_info = []
    if dyscyplina_id:
        try:
            dyscyplina = Dyscyplina_Naukowa.objects.get(pk=dyscyplina_id)
            filter_info.append(f"Dyscyplina: {dyscyplina.nazwa}")
        except Dyscyplina_Naukowa.DoesNotExist:
            pass

    if punktacja_zrodla:
        punktacja_labels = {
            "0-100": "0-100 punktów",
            "100-140": "100-140 punktów",
            "140-200": "140-200 punktów",
            "200+": "200+ punktów",
        }
        filter_info.append(
            f"Punktacja źródła: {punktacja_labels.get(punktacja_zrodla, punktacja_zrodla)}"
        )

    if only_sensible == "1":
        filter_info.append("Tylko sensowne: TAK")

    filters_row = summary_row + 3
    ws.cell(row=filters_row, column=1, value="Zastosowane filtry:")

    if filter_info:
        ws.cell(row=filters_row + 1, column=1, value="; ".join(filter_info))
    else:
        ws.cell(row=filters_row + 1, column=1, value="Brak filtrów")

    # Create response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"unpinning_opportunities_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response


@login_required
@require_POST
def cancel_unpinning_task(request, task_id):
    """
    Anuluje zadanie analizy odpinania (revoke + forget z Redis).
    """
    from django_bpp.celery_tasks import app

    from ..models import StatusUnpinningAnalyzy

    task = AsyncResult(task_id)

    # Sprawdź czy to jest aktualnie działające zadanie w bazie danych
    status_unpinning = StatusUnpinningAnalyzy.get_or_create()
    if not status_unpinning.w_trakcie or status_unpinning.task_id != task_id:
        messages.error(
            request,
            "Nie możesz anulować tego zadania - nie jest aktualnie uruchomione.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    try:
        # Revoke the task (terminate if running)
        app.control.revoke(task_id, terminate=True)

        # Forget the result from backend (Redis)
        task.forget()

        # Clear from database
        status_unpinning.zakoncz("Zadanie anulowane przez użytkownika")

        logger.info(f"Task {task_id} cancelled by user {request.user}")
        messages.success(request, "Zadanie zostało anulowane.")

    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        messages.error(request, f"Nie udało się anulować zadania: {e}")

    return redirect("ewaluacja_optymalizacja:index")
