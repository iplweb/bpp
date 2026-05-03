"""Database persistence + record loading for optimization results."""

from decimal import Decimal

from django.utils import timezone

from bpp.models import Autor, Dyscyplina_Naukowa, Rekord
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_optymalizacja.core import is_low_mono
from ewaluacja_optymalizacja.models import (
    OptimizationAuthorResult,
    OptimizationPublication,
    OptimizationRun,
)


def save_optimization_to_database(stdout, style, results, dyscyplina):
    """Save optimization results to the database.

    Removes any previous ``OptimizationRun`` rows for this discipline,
    then writes a fresh run with per-author and per-publication detail.

    Returns the freshly created ``OptimizationRun`` instance.
    """
    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)

    # Usun stare optymalizacje dla tej dyscypliny
    OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina_obj).delete()

    opt_run = OptimizationRun.objects.create(
        dyscyplina_naukowa=dyscyplina_obj,
        status="completed",
        total_points=Decimal(str(results.total_points)),
        total_slots=Decimal(str(results.total_slots)),
        total_publications=results.total_publications,
        low_mono_count=results.low_mono_count,
        low_mono_percentage=Decimal(str(results.low_mono_percentage)),
        validation_passed=results.validation_passed,
        finished_at=timezone.now(),
    )

    for author_id, author_data in results.authors.items():
        selected_pubs = author_data["selected_pubs"]
        limits = author_data["limits"]

        record = (
            IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                autor_id=author_id, dyscyplina_naukowa=dyscyplina_obj
            )
            .order_by("-ilosc_udzialow")
            .first()
        )
        rodzaj_autora = record.rodzaj_autora if record else None

        total_points = sum(p.points for p in selected_pubs)
        total_slots = sum(p.base_slots for p in selected_pubs)
        mono_slots = sum(p.base_slots for p in selected_pubs if p.kind == "monography")

        author_result = OptimizationAuthorResult.objects.create(
            optimization_run=opt_run,
            autor_id=author_id,
            rodzaj_autora=rodzaj_autora,
            total_points=Decimal(str(total_points)),
            total_slots=Decimal(str(total_slots)),
            mono_slots=Decimal(str(mono_slots)),
            slot_limit_total=Decimal(str(limits["total"])),
            slot_limit_mono=Decimal(str(limits["mono"])),
        )

        for pub in selected_pubs:
            OptimizationPublication.objects.create(
                author_result=author_result,
                rekord_id=pub.id,
                kind=pub.kind,
                points=Decimal(str(pub.points)),
                slots=Decimal(str(pub.base_slots)),
                is_low_mono=is_low_mono(pub),
                author_count=pub.author_count,
            )

    stdout.write(style.SUCCESS(f"Saved optimization run #{opt_run.pk} to database"))
    return opt_run


def load_author_names_and_records(results):
    """Load author display names + ``Rekord`` objects referenced by results.

    Returns a tuple ``(authors, by_author, all_selected, author_names, rekords)``.
    """
    authors = sorted(results.authors.keys())
    by_author = {
        author_id: data["selected_pubs"] for author_id, data in results.authors.items()
    }
    all_selected = []
    for selections in by_author.values():
        all_selected.extend(selections)

    author_names = {}
    for autor in Autor.objects.filter(pk__in=authors):
        author_names[autor.pk] = str(autor)

    all_rekord_ids = [p.id for p in all_selected]
    all_rekord_ids.extend(
        [p.id for p in results.all_pubs if p.id not in {pub.id for pub in all_selected}]
    )
    all_rekord_ids = list(set(all_rekord_ids))

    rekords = {}
    for rekord in Rekord.objects.filter(pk__in=all_rekord_ids):
        rekords[rekord.pk] = rekord

    return authors, by_author, all_selected, author_names, rekords
