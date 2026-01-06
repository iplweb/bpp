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


def _get_discipline_summary(uczelnia, punkty_przed=None, show_diff=True):
    """Pobierz podsumowanie dyscyplin z punktacją i opcjonalnym diff.

    Args:
        uczelnia: Instancja Uczelni
        punkty_przed: Dict {discipline_id: points} przed zmianą
        show_diff: Czy pokazywać diff (False gdy przeliczanie w trakcie)
    """
    from django.db.models import OuterRef, Subquery

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    punkty_przed = punkty_przed or {}
    # Obliczaj diff tylko gdy show_diff=True (czyli po zakończeniu wszystkich tasków)
    calculate_diff = show_diff and bool(punkty_przed)

    raportowane = (
        LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia,
            liczba_n__gte=12,
        )
        .select_related("dyscyplina_naukowa")
        .order_by("dyscyplina_naukowa__nazwa")
    )

    # Pre-fetch latest OptimizationRun per discipline (single query)
    reported_disc_ids = list(
        raportowane.values_list("dyscyplina_naukowa_id", flat=True)
    )

    latest_run_subquery = (
        OptimizationRun.objects.filter(
            uczelnia=uczelnia,
            dyscyplina_naukowa_id=OuterRef("dyscyplina_naukowa_id"),
            status="completed",
        )
        .order_by("-started_at")
        .values("pk")[:1]
    )

    opt_runs = OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        status="completed",
        dyscyplina_naukowa_id__in=reported_disc_ids,
        pk__in=Subquery(
            OptimizationRun.objects.filter(
                uczelnia=uczelnia,
                status="completed",
                dyscyplina_naukowa_id__in=reported_disc_ids,
            )
            .annotate(latest_pk=Subquery(latest_run_subquery))
            .values("latest_pk")
        ),
    )

    opt_runs_by_disc = {r.dyscyplina_naukowa_id: r for r in opt_runs}

    summary = []
    total_points = 0
    total_slots = 0
    total_diff = 0

    for ln in raportowane:
        disc_id = ln.dyscyplina_naukowa_id
        opt_run = opt_runs_by_disc.get(disc_id)

        current_points = float(opt_run.total_points) if opt_run else 0
        current_slots = (
            float(opt_run.total_slots) if opt_run and opt_run.total_slots else 0
        )
        before_points = punkty_przed.get(str(disc_id), 0) if calculate_diff else 0
        diff = current_points - before_points if calculate_diff else 0

        total_points += current_points
        total_slots += current_slots
        total_diff += diff

        summary.append(
            {
                "dyscyplina": ln.dyscyplina_naukowa,
                "punkty": current_points,
                "slots": current_slots,
                "diff": diff,
                "has_diff": calculate_diff and before_points > 0,
            }
        )

    return {
        "disciplines": summary,
        "total_points": total_points,
        "total_slots": total_slots,
        "total_diff": total_diff,
        "has_diff": calculate_diff,
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


def _get_distinct_punkty_kbn(rok=None):
    """
    Pobierz unikalne wartości punkty_kbn z publikacji.

    Zwraca posortowaną listę unikalnych wartości punkty_kbn z obu typów publikacji.
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    base_filter = {"rok__in": [2022, 2023, 2024, 2025]}
    if rok:
        base_filter["rok"] = int(rok)

    ciagle_punkty = set(
        Wydawnictwo_Ciagle.objects.filter(**base_filter)
        .values_list("punkty_kbn", flat=True)
        .distinct()
    )
    zwarte_punkty = set(
        Wydawnictwo_Zwarte.objects.filter(**base_filter)
        .values_list("punkty_kbn", flat=True)
        .distinct()
    )

    all_punkty = ciagle_punkty | zwarte_punkty
    # Usuń None i posortuj malejąco (najwyższe punkty na górze)
    return sorted([p for p in all_punkty if p is not None], reverse=True)


def _build_rekord_ids(ciagle_list, zwarte_list, ct_ciagle, ct_zwarte):
    """Zbuduj słowniki rekord_id dla publikacji."""
    all_rekord_ids = []
    ciagle_rekord_ids = {}
    zwarte_rekord_ids = {}

    for pub in ciagle_list:
        rekord_id = (ct_ciagle.pk, pub.pk)
        ciagle_rekord_ids[pub.pk] = rekord_id
        all_rekord_ids.append(list(rekord_id))

    for pub in zwarte_list:
        rekord_id = (ct_zwarte.pk, pub.pk)
        zwarte_rekord_ids[pub.pk] = rekord_id
        all_rekord_ids.append(list(rekord_id))

    return all_rekord_ids, ciagle_rekord_ids, zwarte_rekord_ids


def _prefetch_selected_publications(all_rekord_ids):
    """Pobierz set rekord_ids wybranych publikacji."""
    selected_rekord_ids = set()
    if all_rekord_ids:
        for op in OptimizationPublication.objects.filter(rekord_id__in=all_rekord_ids):
            selected_rekord_ids.add(tuple(op.rekord_id))
    return selected_rekord_ids


def _prefetch_punktacja_cache(all_rekord_ids):
    """Pobierz cache punktacji dla wszystkich publikacji."""
    punktacja_cache = {}
    if all_rekord_ids:
        for cpa in Cache_Punktacja_Autora.objects.filter(rekord_id__in=all_rekord_ids):
            rekord_key = tuple(cpa.rekord_id)
            if rekord_key not in punktacja_cache:
                punktacja_cache[rekord_key] = {}
            punktacja_cache[rekord_key][(cpa.autor_id, cpa.dyscyplina_id)] = {
                "pkdaut": cpa.pkdaut,
                "slot": cpa.slot,
            }
    return punktacja_cache


def _prefetch_autorzy_by_pub(autorzy_qs, pub_list):
    """Grupuj autorów wg publikacji i zbierz pary (autor_id, rok)."""
    autorzy_by_pub = {}
    autor_rok_pairs = set()
    pub_by_pk = {p.pk: p for p in pub_list}

    for ar in autorzy_qs:
        if ar.rekord_id not in autorzy_by_pub:
            autorzy_by_pub[ar.rekord_id] = []
        autorzy_by_pub[ar.rekord_id].append(ar)
        pub = pub_by_pk.get(ar.rekord_id)
        if pub:
            autor_rok_pairs.add((ar.autor_id, pub.rok))

    return autorzy_by_pub, autor_rok_pairs


def _prefetch_autor_dyscypliny(autor_rok_pairs):
    """Pobierz mapę Autor_Dyscyplina dla par (autor_id, rok)."""
    from django.db.models import Q

    autor_dyscypliny = {}
    if autor_rok_pairs:
        q_filter = Q()
        for autor_id, r in autor_rok_pairs:
            q_filter |= Q(autor_id=autor_id, rok=r)
        for ad in Autor_Dyscyplina.objects.filter(q_filter):
            autor_dyscypliny[(ad.autor_id, ad.rok)] = ad
    return autor_dyscypliny


def _build_publication_list(
    pub_list, model_type, rekord_ids, selected, punktacja_cache, autorzy_by_pub, ad_map
):
    """Zbuduj listę publikacji z autorami."""
    publications = []
    for pub in pub_list:
        rekord_id = rekord_ids[pub.pk]
        jest_wybrana = rekord_id in selected
        pub_punktacja = punktacja_cache.get(rekord_id, {})

        authors = _build_authors_list(
            autorzy_by_pub.get(pub.pk, []),
            pub.rok,
            model_type,
            pub_punktacja,
            ad_map,
        )

        if authors:
            publications.append(
                {
                    "pk": pub.pk,
                    "model_type": model_type,
                    "tytul": pub.tytul_oryginalny,
                    "rok": pub.rok,
                    "punkty_kbn": pub.punkty_kbn,
                    "jest_wybrana": jest_wybrana,
                    "url": pub.get_absolute_url(),
                    "authors": authors,
                }
            )
    return publications


def _get_filtered_publications(uczelnia, filters, reported_ids):
    """
    Pobierz publikacje z filtrami.

    Zwraca listę dict z informacjami o publikacjach i autorach.
    Zoptymalizowano pod kątem unikania zapytań N+1.
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    rok = filters.get("rok")
    tytul = (filters.get("tytul") or "").strip()
    dyscyplina = filters.get("dyscyplina")
    nazwisko = (filters.get("nazwisko") or "").strip()
    punkty_kbn = filters.get("punkty_kbn")

    # Bazowe filtrowanie
    base_filter = {"rok__in": [2022, 2023, 2024, 2025]}
    if rok:
        base_filter["rok"] = int(rok)
    if punkty_kbn:
        base_filter["punkty_kbn"] = punkty_kbn

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

    # Phase 1: Pobierz wszystkie publikacje jako listy
    ciagle_list = list(ciagle_qs.order_by("rok", "tytul_oryginalny"))
    zwarte_list = list(zwarte_qs.order_by("rok", "tytul_oryginalny"))

    # Phase 2-3: Zbuduj rekord_ids i pobierz wybrane publikacje
    all_rekord_ids, ciagle_rekord_ids, zwarte_rekord_ids = _build_rekord_ids(
        ciagle_list, zwarte_list, ct_ciagle, ct_zwarte
    )
    selected_rekord_ids = _prefetch_selected_publications(all_rekord_ids)
    punktacja_cache = _prefetch_punktacja_cache(all_rekord_ids)

    # Phase 4: Pobierz wszystkich autorów dla publikacji (batch query)
    ciagle_pks = [p.pk for p in ciagle_list]
    zwarte_pks = [p.pk for p in zwarte_list]

    autor_base_filter = {
        "afiliuje": True,
        "zatrudniony": True,
        "dyscyplina_naukowa_id__in": reported_ids,
    }
    if dyscyplina:
        autor_base_filter["dyscyplina_naukowa_id"] = int(dyscyplina)
    if nazwisko:
        autor_base_filter["autor__nazwisko__icontains"] = nazwisko

    ciagle_autorzy = Wydawnictwo_Ciagle_Autor.objects.filter(
        rekord_id__in=ciagle_pks, **autor_base_filter
    ).select_related("autor", "dyscyplina_naukowa")

    zwarte_autorzy = Wydawnictwo_Zwarte_Autor.objects.filter(
        rekord_id__in=zwarte_pks, **autor_base_filter
    ).select_related("autor", "dyscyplina_naukowa")

    # Grupuj autorów po publikacji
    ciagle_autorzy_by_pub, ciagle_pairs = _prefetch_autorzy_by_pub(
        ciagle_autorzy, ciagle_list
    )
    zwarte_autorzy_by_pub, zwarte_pairs = _prefetch_autorzy_by_pub(
        zwarte_autorzy, zwarte_list
    )

    # Phase 5: Batch pre-fetch Autor_Dyscyplina
    autor_dyscypliny = _prefetch_autor_dyscypliny(ciagle_pairs | zwarte_pairs)

    # Phase 6: Zbuduj wyniki
    publications = _build_publication_list(
        ciagle_list,
        "ciagle",
        ciagle_rekord_ids,
        selected_rekord_ids,
        punktacja_cache,
        ciagle_autorzy_by_pub,
        autor_dyscypliny,
    )
    publications.extend(
        _build_publication_list(
            zwarte_list,
            "zwarte",
            zwarte_rekord_ids,
            selected_rekord_ids,
            punktacja_cache,
            zwarte_autorzy_by_pub,
            autor_dyscypliny,
        )
    )

    return publications


def _build_authors_list(autor_records, rok, model_type, punktacja_cache, autor_dysc):
    """Zbuduj listę autorów z prefetchowanych danych."""
    authors = []
    for autor_rekord in autor_records:
        # Sprawdź czy autor ma 2 dyscypliny (używając prefetchowanych danych)
        ad = autor_dysc.get((autor_rekord.autor_id, rok))
        has_two = ad.dwie_dyscypliny() if ad else False

        # Pobierz punktację autora
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
    punkty_kbn_values = _get_distinct_punkty_kbn()

    context = {
        "uczelnia": uczelnia,
        "discipline_summary": discipline_summary,
        "filters": filters,
        "status": status,
        "punkty_kbn_values": punkty_kbn_values,
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
        "nazwisko": request.GET.get("nazwisko"),
        "punkty_kbn": request.GET.get("punkty_kbn"),
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
