"""Unpinning of disciplines for non-selected publication-author pairs."""

import os

from denorm import denorms
from django.core.management import call_command
from django.db import transaction

from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


def handle_unpinning(
    stdout,
    style,
    selected_pubs,
    all_pubs,
    dyscyplina_obj,
    rerun_after_unpin,
    dyscyplina_name,
    output,
    verbose,
    algorithm_mode="two-phase",
):
    """Unpin disciplines for publications not selected by the optimizer."""
    stdout.write("\n" + "=" * 80)
    stdout.write("UNPINNING NON-SELECTED PUBLICATIONS")
    stdout.write("=" * 80)

    selected_ids = {p.id for p in selected_pubs}

    non_selected_pubs = [p for p in all_pubs if p.id not in selected_ids]

    if not non_selected_pubs:
        stdout.write(style.WARNING("No publications to unpin"))
        return

    stdout.write(
        f"Found {len(non_selected_pubs)} non-selected publication-author pairs"
    )

    to_unpin = {}
    for p in non_selected_pubs:
        key = (p.id, p.author)
        to_unpin[key] = p

    stdout.write(f"Unpinning {len(to_unpin)} author-publication associations...")

    unpinned_count = 0
    with transaction.atomic():
        for (rekord_id, autor_id), pub in to_unpin.items():
            content_type_id, object_id = rekord_id

            if pub.kind == "article":
                updated = Wydawnictwo_Ciagle_Autor.objects.filter(
                    rekord_id=object_id,
                    autor_id=autor_id,
                    dyscyplina_naukowa=dyscyplina_obj,
                    przypieta=True,
                ).update(przypieta=False)
                unpinned_count += updated
            elif pub.kind == "monography":
                updated = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord_id=object_id,
                    autor_id=autor_id,
                    dyscyplina_naukowa=dyscyplina_obj,
                    przypieta=True,
                ).update(przypieta=False)
                unpinned_count += updated
            # Patents could also be handled here if needed

    stdout.write(
        style.SUCCESS(f"Unpinned {unpinned_count} author-discipline associations")
    )

    stdout.write("Flushing denorms...")
    denorms.flush()
    stdout.write(style.SUCCESS("Denorms flushed"))

    if rerun_after_unpin:
        stdout.write("\n" + "=" * 80)
        stdout.write("RE-RUNNING OPTIMIZATION AFTER UNPINNING")
        stdout.write("=" * 80)

        rerun_args = [dyscyplina_name]
        rerun_kwargs = {
            "verbose": verbose,
            "unpin_not_selected": False,
            "rerun_after_unpin": False,
            "algorithm_mode": algorithm_mode,
        }

        if output:
            base, ext = os.path.splitext(output)
            rerun_output = f"{base}_after_unpin{ext}"
            rerun_kwargs["output"] = rerun_output
            stdout.write(f"Re-run results will be saved to: {rerun_output}")

        call_command("solve_evaluation", *rerun_args, **rerun_kwargs)
