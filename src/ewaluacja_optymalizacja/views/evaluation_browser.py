"""Widoki przeglądarki ewaluacji."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.cache import Cache_Punktacja_Autora

from ..models import (
    OptimizationPublication,
    OptimizationRun,
    StatusPrzegladarkaRecalc,
)
from ..tasks import solve_all_reported_disciplines


def _get_reported_disciplines(uczelnia):
    """Pobierz ID raportowanych dyscyplin (liczba_n >= 12)."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    return list(
        LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia, liczba_n__gte=12
        ).values_list("dyscyplina_naukowa_id", flat=True)
    )


def _snapshot_discipline_points(uczelnia):
    """Zapisz aktualną punktację dyscyplin do obliczenia diff."""
    result = {}
    for opt_run in OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        status="completed",
    ):
        result[str(opt_run.dyscyplina_naukowa_id)] = float(opt_run.total_points)
    return result


def _get_discipline_summary(uczelnia, punkty_przed=None):
    """Pobierz podsumowanie dyscyplin z punktacją i opcjonalnym diff."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    punkty_przed = punkty_przed or {}

    raportowane = (
        LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia,
            liczba_n__gte=12,
        )
        .select_related("dyscyplina_naukowa")
        .order_by("dyscyplina_naukowa__nazwa")
    )

    summary = []
    total_points = 0
    total_diff = 0

    for ln in raportowane:
        disc_id = ln.dyscyplina_naukowa_id

        opt_run = (
            OptimizationRun.objects.filter(
                uczelnia=uczelnia,
                dyscyplina_naukowa_id=disc_id,
                status="completed",
            )
            .order_by("-started_at")
            .first()
        )

        current_points = float(opt_run.total_points) if opt_run else 0
        before_points = punkty_przed.get(str(disc_id), 0)
        diff = current_points - before_points if punkty_przed else 0

        total_points += current_points
        total_diff += diff

        summary.append(
            {
                "dyscyplina": ln.dyscyplina_naukowa,
                "punkty": current_points,
                "diff": diff,
                "has_diff": bool(punkty_przed) and before_points > 0,
            }
        )

    return {
        "disciplines": summary,
        "total_points": total_points,
        "total_diff": total_diff,
        "has_diff": bool(punkty_przed),
    }


def _get_filter_options(uczelnia):
    """Pobierz opcje dla filtrów."""
    reported_ids = _get_reported_disciplines(uczelnia)

    dyscypliny = Dyscyplina_Naukowa.objects.filter(pk__in=reported_ids).order_by(
        "nazwa"
    )

    return {
        "dyscypliny": dyscypliny,
        "lata": [2022, 2023, 2024, 2025],
    }


def _get_filtered_publications(uczelnia, filters, reported_ids):
    """
    Pobierz publikacje z filtrami.

    Zwraca listę dict z informacjami o publikacjach i autorach.
    """

    from django.contrib.contenttypes.models import ContentType

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    rok = filters.get("rok")
    tytul = (filters.get("tytul") or "").strip()
    dyscyplina = filters.get("dyscyplina")
    nazwisko = (filters.get("nazwisko") or "").strip()

    # Bazowe filtrowanie
    base_filter = {"rok__in": [2022, 2023, 2024, 2025]}
    if rok:
        base_filter["rok"] = int(rok)

    # Pobierz publikacje obu typów
    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(**base_filter)
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(**base_filter)

    if tytul:
        ciagle_qs = ciagle_qs.filter(tytul_oryginalny__icontains=tytul)
        zwarte_qs = zwarte_qs.filter(tytul_oryginalny__icontains=tytul)

    # Filtr po autorze z dyscypliną w raportowanych
    author_filter = {
        "afiliuje": True,
        "zatrudniony": True,
        "dyscyplina_naukowa_id__in": reported_ids,
    }

    if dyscyplina:
        author_filter["dyscyplina_naukowa_id"] = int(dyscyplina)

    if nazwisko:
        author_filter["autor__nazwisko__icontains"] = nazwisko

    # Ogranicz do publikacji z odpowiednimi autorami
    # Używamy subquery przez rekord_id (FK do publikacji)
    ciagle_with_authors = Wydawnictwo_Ciagle_Autor.objects.filter(
        **author_filter
    ).values_list("rekord_id", flat=True)
    ciagle_qs = ciagle_qs.filter(pk__in=ciagle_with_authors).distinct()

    zwarte_with_authors = Wydawnictwo_Zwarte_Autor.objects.filter(
        **author_filter
    ).values_list("rekord_id", flat=True)
    zwarte_qs = zwarte_qs.filter(pk__in=zwarte_with_authors).distinct()

    # Pobierz content types
    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    # Zbierz wyniki
    publications = []

    for pub in ciagle_qs.order_by("rok", "tytul_oryginalny"):
        rekord_id = [ct_ciagle.pk, pub.pk]
        jest_wybrana = OptimizationPublication.objects.filter(
            rekord_id=rekord_id
        ).exists()

        # Pobierz autorów
        authors = _get_authors_for_publication(
            pub, "ciagle", reported_ids, dyscyplina, nazwisko, rekord_id
        )
        if authors:  # Tylko jeśli są autorzy spełniający kryteria
            publications.append(
                {
                    "pk": pub.pk,
                    "model_type": "ciagle",
                    "tytul": pub.tytul_oryginalny,
                    "rok": pub.rok,
                    "punkty_kbn": pub.punkty_kbn,
                    "jest_wybrana": jest_wybrana,
                    "url": pub.get_absolute_url(),
                    "authors": authors,
                }
            )

    for pub in zwarte_qs.order_by("rok", "tytul_oryginalny"):
        rekord_id = [ct_zwarte.pk, pub.pk]
        jest_wybrana = OptimizationPublication.objects.filter(
            rekord_id=rekord_id
        ).exists()

        authors = _get_authors_for_publication(
            pub, "zwarte", reported_ids, dyscyplina, nazwisko, rekord_id
        )
        if authors:
            publications.append(
                {
                    "pk": pub.pk,
                    "model_type": "zwarte",
                    "tytul": pub.tytul_oryginalny,
                    "rok": pub.rok,
                    "punkty_kbn": pub.punkty_kbn,
                    "jest_wybrana": jest_wybrana,
                    "url": pub.get_absolute_url(),
                    "authors": authors,
                }
            )

    return publications


def _get_authors_for_publication(
    pub, model_type, reported_ids, dyscyplina, nazwisko, rekord_id
):
    """Pobierz autorów publikacji spełniających kryteria."""
    # Użyj modelu through (Wydawnictwo_*_Autor) - nie M2M do Autor
    if model_type == "ciagle":
        autor_qs = Wydawnictwo_Ciagle_Autor.objects.filter(
            rekord=pub,
            afiliuje=True,
            zatrudniony=True,
            dyscyplina_naukowa_id__in=reported_ids,
        )
    else:
        autor_qs = Wydawnictwo_Zwarte_Autor.objects.filter(
            rekord=pub,
            afiliuje=True,
            zatrudniony=True,
            dyscyplina_naukowa_id__in=reported_ids,
        )

    if dyscyplina:
        autor_qs = autor_qs.filter(dyscyplina_naukowa_id=int(dyscyplina))

    if nazwisko:
        autor_qs = autor_qs.filter(autor__nazwisko__icontains=nazwisko)

    autor_qs = autor_qs.select_related("autor", "dyscyplina_naukowa")

    # Pobierz cache punktacji dla tej publikacji
    punktacja_cache = {}
    for cpa in Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id):
        key = (cpa.autor_id, cpa.dyscyplina_id)
        punktacja_cache[key] = {"pkdaut": cpa.pkdaut, "slot": cpa.slot}

    authors = []
    for autor_rekord in autor_qs:
        # Sprawdź czy autor ma 2 dyscypliny
        has_two = _author_has_two_disciplines(autor_rekord.autor, pub.rok)

        # Pobierz punktację autora z cache
        key = (autor_rekord.autor_id, autor_rekord.dyscyplina_naukowa_id)
        punktacja = punktacja_cache.get(key, {})

        authors.append(
            {
                "pk": autor_rekord.pk,
                "autor": autor_rekord.autor,
                "dyscyplina": autor_rekord.dyscyplina_naukowa,
                "przypieta": autor_rekord.przypieta,
                "has_two_disciplines": has_two,
                "model_type": model_type,
                "pkdaut": punktacja.get("pkdaut"),
                "slot": punktacja.get("slot"),
            }
        )

    return authors


def _author_has_two_disciplines(autor, rok):
    """Sprawdź czy autor ma dwie dyscypliny w danym roku."""
    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
        return ad.dwie_dyscypliny()
    except Autor_Dyscyplina.DoesNotExist:
        return False


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
    discipline_summary = _get_discipline_summary(uczelnia, status.punkty_przed)
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
    discipline_summary = _get_discipline_summary(uczelnia, status.punkty_przed)

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
        "nazwisko": request.GET.get("nazwisko"),
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

    if all_done and status.w_trakcie:
        status.zakoncz("Przeliczanie zakończone pomyślnie")

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
