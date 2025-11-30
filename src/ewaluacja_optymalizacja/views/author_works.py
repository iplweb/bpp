"""Widok szczegółów prac autora w kontekście optymalizacji."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from bpp.models import Autor
from bpp.models.cache import Cache_Punktacja_Autora_Query
from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
from bpp.models.patent import Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
from ewaluacja_metryki.models import MetrykaAutora

from ..models import OptimizationRun


@login_required
def author_works_detail(request, run_pk, autor_pk):
    """
    Szczegółowy widok prac autora w kontekście optymalizacji.

    Wyświetla trzy kategorie prac:
    - Prace nazbierane (wybrane przez algorytm)
    - Prace nienazbierane (wszystkie minus nazbierane)
    - Prace z odpiętą dyscypliną (przypieta=False)
    """
    run = get_object_or_404(
        OptimizationRun.objects.select_related("dyscyplina_naukowa", "uczelnia"),
        pk=run_pk,
    )
    autor = get_object_or_404(Autor, pk=autor_pk)

    # Get metryka for this author and discipline
    metryka = get_object_or_404(
        MetrykaAutora.objects.select_related("dyscyplina_naukowa"),
        autor=autor,
        dyscyplina_naukowa=run.dyscyplina_naukowa,
    )

    # Get works collected (nazbierane)
    # prace_nazbierane/wszystkie are stored as lists of [content_type_id, object_id]
    # Convert to tuples for set operations and querying
    prace_nazbierane_ids = {tuple(r) for r in (metryka.prace_nazbierane or [])}
    prace_wszystkie_ids = {tuple(r) for r in (metryka.prace_wszystkie or [])}
    prace_nienazbierane_ids = prace_wszystkie_ids - prace_nazbierane_ids

    # Query collected works using rekord__pk__in with tuple PKs
    prace_nazbierane = (
        Cache_Punktacja_Autora_Query.objects.filter(
            rekord__pk__in=prace_nazbierane_ids,
            autor=autor,
            dyscyplina=run.dyscyplina_naukowa,
        )
        .select_related("rekord", "jednostka")
        .order_by("-pkdaut")
    )

    # Query not collected works
    prace_nienazbierane = (
        Cache_Punktacja_Autora_Query.objects.filter(
            rekord__pk__in=prace_nienazbierane_ids,
            autor=autor,
            dyscyplina=run.dyscyplina_naukowa,
        )
        .select_related("rekord", "jednostka")
        .order_by("-pkdaut")
    )

    # Query unpinned works (przypieta=False for this discipline)
    # Need to query all three author-publication models
    prace_odpiete = []

    # Wydawnictwo_Ciagle_Autor
    odpiete_ciagle = (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor,
            dyscyplina_naukowa=run.dyscyplina_naukowa,
            przypieta=False,
        )
        .select_related("rekord")
        .order_by("-rekord__rok", "rekord__tytul_oryginalny")
    )
    for wa in odpiete_ciagle:
        prace_odpiete.append(
            {
                "rekord": wa.rekord,
                "typ": "Wydawnictwo ciągłe",
            }
        )

    # Wydawnictwo_Zwarte_Autor
    odpiete_zwarte = (
        Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor,
            dyscyplina_naukowa=run.dyscyplina_naukowa,
            przypieta=False,
        )
        .select_related("rekord")
        .order_by("-rekord__rok", "rekord__tytul_oryginalny")
    )
    for wa in odpiete_zwarte:
        prace_odpiete.append(
            {
                "rekord": wa.rekord,
                "typ": "Wydawnictwo zwarte",
            }
        )

    # Patent_Autor
    odpiete_patenty = (
        Patent_Autor.objects.filter(
            autor=autor,
            dyscyplina_naukowa=run.dyscyplina_naukowa,
            przypieta=False,
        )
        .select_related("rekord")
        .order_by("-rekord__rok", "rekord__tytul_oryginalny")
    )
    for pa in odpiete_patenty:
        prace_odpiete.append(
            {
                "rekord": pa.rekord,
                "typ": "Patent",
            }
        )

    # Sort unpinned works by year descending
    prace_odpiete.sort(
        key=lambda x: (-(x["rekord"].rok or 0), x["rekord"].tytul_oryginalny)
    )

    # Check for second discipline with optimization run
    inna_dyscyplina = None
    inny_run = None

    # Get author's disciplines in 2022-2025
    autor_dyscypliny = Autor_Dyscyplina.objects.filter(
        autor=autor,
        rok__gte=2022,
        rok__lte=2025,
    ).select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")

    # Collect all disciplines for this author
    wszystkie_dyscypliny = set()
    for ad in autor_dyscypliny:
        if ad.dyscyplina_naukowa:
            wszystkie_dyscypliny.add(ad.dyscyplina_naukowa_id)
        if ad.subdyscyplina_naukowa:
            wszystkie_dyscypliny.add(ad.subdyscyplina_naukowa_id)

    # Remove current discipline
    wszystkie_dyscypliny.discard(run.dyscyplina_naukowa_id)

    # Check if there's an optimization run for another discipline
    if wszystkie_dyscypliny:
        inny_run = (
            OptimizationRun.objects.filter(
                dyscyplina_naukowa_id__in=wszystkie_dyscypliny,
                status="completed",
            )
            .select_related("dyscyplina_naukowa")
            .order_by("-started_at")
            .first()
        )
        if inny_run:
            inna_dyscyplina = inny_run.dyscyplina_naukowa

    # Calculate sums for tables
    suma_pkdaut_nazbierane = sum(p.pkdaut for p in prace_nazbierane)
    suma_slot_nazbierane = sum(p.slot for p in prace_nazbierane)
    suma_pkdaut_nienazbierane = sum(p.pkdaut for p in prace_nienazbierane)
    suma_slot_nienazbierane = sum(p.slot for p in prace_nienazbierane)

    context = {
        "run": run,
        "autor": autor,
        "metryka": metryka,
        "prace_nazbierane": prace_nazbierane,
        "prace_nienazbierane": prace_nienazbierane,
        "prace_odpiete": prace_odpiete,
        "inna_dyscyplina": inna_dyscyplina,
        "inny_run": inny_run,
        # Summary stats
        "liczba_nazbieranych": len(prace_nazbierane_ids),
        "liczba_nienazbieranych": len(prace_nienazbierane_ids),
        "liczba_odpietych": len(prace_odpiete),
        # Sums for tables
        "suma_pkdaut_nazbierane": suma_pkdaut_nazbierane,
        "suma_slot_nazbierane": suma_slot_nazbierane,
        "suma_pkdaut_nienazbierane": suma_pkdaut_nienazbierane,
        "suma_slot_nienazbierane": suma_slot_nienazbierane,
    }

    return render(request, "ewaluacja_optymalizacja/author_works_detail.html", context)
