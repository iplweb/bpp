"""Widoki HTTP przeglądarki ewaluacji (HTMX + akcje pin/swap)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import (
    Autor_Dyscyplina,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)

from ...models import (
    OptimizationRun,
    StatusPrzegladarkaRecalc,
)
from ...tasks import solve_all_reported_disciplines
from .builders import _get_filtered_publications
from .discipline_summary import (
    _get_discipline_summary,
    _get_filter_options,
    _get_reported_disciplines,
    _snapshot_discipline_points,
)


@login_required
def evaluation_browser(request):
    """
    Główna strona przeglądarki ewaluacji.
    Wyświetla podsumowanie dyscyplin i tabelę publikacji z filtrami.
    """
    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni.")
        return redirect("ewaluacja_optymalizacja:index")

    status = StatusPrzegladarkaRecalc.get_or_create()
    # Pokazuj diff tylko gdy przeliczanie zakończone (w_trakcie=False)
    show_diff = not status.w_trakcie
    discipline_summary = _get_discipline_summary(
        uczelnia, status.punkty_przed, show_diff
    )
    filters = _get_filter_options(uczelnia)

    context = {
        "uczelnia": uczelnia,
        "discipline_summary": discipline_summary,
        "filters": filters,
        "status": status,
    }

    return render(
        request,
        "ewaluacja_optymalizacja/evaluation_browser.html",
        context,
    )


@login_required
def browser_summary(request):
    """HTMX partial - podsumowanie punktacji dyscyplin."""
    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        return HttpResponseBadRequest("Nie znaleziono uczelni")

    status = StatusPrzegladarkaRecalc.get_or_create()
    # Pokazuj diff tylko gdy przeliczanie zakończone (w_trakcie=False)
    show_diff = not status.w_trakcie
    discipline_summary = _get_discipline_summary(
        uczelnia, status.punkty_przed, show_diff
    )

    return render(
        request,
        "ewaluacja_optymalizacja/_browser_discipline_summary.html",
        {"discipline_summary": discipline_summary},
    )


@login_required
def browser_table(request):
    """HTMX partial - tabela publikacji z paginacją i filtrami."""
    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        return HttpResponseBadRequest("Nie znaleziono uczelni")

    reported_ids = _get_reported_disciplines(uczelnia)

    filters = {
        "rok": request.GET.get("rok"),
        "tytul": request.GET.get("tytul"),
        "dyscyplina": request.GET.get("dyscyplina"),
        "dyscyplina_nieprzypisana": request.GET.get("dyscyplina_nieprzypisana"),
        "nazwisko": request.GET.get("nazwisko"),
        "punkty_od": request.GET.get("punkty_od"),
        "punkty_do": request.GET.get("punkty_do"),
    }

    publications = _get_filtered_publications(uczelnia, filters, reported_ids)

    page = request.GET.get("page", 1)
    paginator = Paginator(publications, 50)
    page_obj = paginator.get_page(page)

    context = {
        "publications": page_obj,
        "filters": filters,
        "page_obj": page_obj,
    }

    return render(
        request,
        "ewaluacja_optymalizacja/_browser_publication_table.html",
        context,
    )


@login_required
@require_POST
def browser_toggle_pin(request, model_type, pk):
    """Toggle przypieta na rekordzie autor-publikacja."""
    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        return HttpResponseBadRequest("Nie znaleziono uczelni")

    # Wybierz odpowiedni model
    model_map = {
        "ciagle": Wydawnictwo_Ciagle_Autor,
        "zwarte": Wydawnictwo_Zwarte_Autor,
    }
    model = model_map.get(model_type)
    if not model:
        return HttpResponseBadRequest("Nieprawidłowy typ modelu")

    try:
        autor_rekord = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return HttpResponseBadRequest("Nie znaleziono rekordu")

    # Toggle przypieta
    autor_rekord.przypieta = not autor_rekord.przypieta
    autor_rekord.save()

    # Zapisz punkty przed przeliczeniem
    punkty_przed = _snapshot_discipline_points(uczelnia)

    # Uruchom przeliczanie
    with transaction.atomic():
        status = StatusPrzegladarkaRecalc.get_or_create()
        if status.w_trakcie:
            return HttpResponseBadRequest(
                "Przeliczanie już trwa. Poczekaj na zakończenie."
            )

        task = solve_all_reported_disciplines.delay(uczelnia.pk)
        status.rozpocznij(str(task.id), uczelnia, punkty_przed)

    action = "przypięto" if autor_rekord.przypieta else "odpięto"

    return render(
        request,
        "ewaluacja_optymalizacja/_browser_recalc_modal.html",
        {
            "task_id": task.id,
            "action": action,
            "status": status,
            "all_done": False,
        },
    )


@login_required
@require_POST
def browser_swap_discipline(request, model_type, pk):
    """Zamień dyscyplinę na drugą dla autora z dwoma dyscyplinami."""
    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        return HttpResponseBadRequest("Nie znaleziono uczelni")

    model_map = {
        "ciagle": Wydawnictwo_Ciagle_Autor,
        "zwarte": Wydawnictwo_Zwarte_Autor,
    }
    model = model_map.get(model_type)
    if not model:
        return HttpResponseBadRequest("Nieprawidłowy typ modelu")

    try:
        autor_rekord = model.objects.select_related("autor", "rekord").get(pk=pk)
    except model.DoesNotExist:
        return HttpResponseBadRequest("Nie znaleziono rekordu")

    # Pobierz rok publikacji
    rok = autor_rekord.rekord.rok

    # Pobierz dyscypliny autora
    try:
        autor_dyscyplina = Autor_Dyscyplina.objects.get(
            autor=autor_rekord.autor,
            rok=rok,
        )
    except Autor_Dyscyplina.DoesNotExist:
        return HttpResponseBadRequest("Nie znaleziono przypisania dyscypliny autora")

    if not autor_dyscyplina.dwie_dyscypliny():
        return HttpResponseBadRequest("Autor ma tylko jedną dyscyplinę")

    # Określ docelową dyscyplinę
    current = autor_rekord.dyscyplina_naukowa
    if current == autor_dyscyplina.dyscyplina_naukowa:
        target = autor_dyscyplina.subdyscyplina_naukowa
    elif current == autor_dyscyplina.subdyscyplina_naukowa:
        target = autor_dyscyplina.dyscyplina_naukowa
    else:
        return HttpResponseBadRequest(
            "Obecna dyscyplina nie pasuje do przypisań autora"
        )

    # Wykonaj zamianę
    autor_rekord.dyscyplina_naukowa = target
    autor_rekord.save()

    # Zapisz punkty i uruchom przeliczanie
    punkty_przed = _snapshot_discipline_points(uczelnia)

    with transaction.atomic():
        status = StatusPrzegladarkaRecalc.get_or_create()
        if status.w_trakcie:
            return HttpResponseBadRequest(
                "Przeliczanie już trwa. Poczekaj na zakończenie."
            )

        task = solve_all_reported_disciplines.delay(uczelnia.pk)
        status.rozpocznij(str(task.id), uczelnia, punkty_przed)

    return render(
        request,
        "ewaluacja_optymalizacja/_browser_recalc_modal.html",
        {
            "task_id": task.id,
            "action": f"zamieniono na {target.nazwa}",
            "status": status,
            "all_done": False,
        },
    )


@login_required
def browser_recalc_status(request):
    """HTMX polling - status przeliczania."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    uczelnia = Uczelnia.objects.first()
    if not uczelnia:
        return HttpResponseBadRequest("Nie znaleziono uczelni")

    status = StatusPrzegladarkaRecalc.get_or_create()

    # Policz postęp
    raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia,
        liczba_n__gte=12,
    ).count()

    completed = OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        status="completed",
    ).count()

    progress = int((completed / raportowane) * 100) if raportowane > 0 else 0
    all_done = completed == raportowane

    # Status jest aktualizowany przez Celery chord callback (finalize_browser_recalc)
    # Tutaj sprawdzamy tylko w celu ustalenia all_done dla UI

    context = {
        "status": status,
        "progress": progress,
        "completed": completed,
        "total": raportowane,
        "all_done": all_done,
    }

    return render(
        request,
        "ewaluacja_optymalizacja/_browser_recalc_modal.html",
        context,
    )
