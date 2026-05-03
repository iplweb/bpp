"""Capacity-rule based unpinning (84% accuracy heuristic)."""

from denorm import denorms

from ewaluacja_optymalizacja.tasks.unpinning.capacity_analysis import (
    apply_unpinning,
    format_unpinning_preview,
    identify_unpinning_candidates,
)


def handle_capacity_based_unpinning(stdout, style, dyscyplina_obj, dry_run=True):
    """Analyze and optionally apply capacity-based unpinning.

    For each multi-author publication, keep the author with most
    remaining capacity (= 4.0 - current_slots) and unpin others.
    Returns the list of ``UnpinningCandidate`` objects identified.
    """
    stdout.write("\n" + "=" * 80)
    stdout.write("CAPACITY-BASED UNPINNING ANALYSIS")
    stdout.write("=" * 80)
    stdout.write(f"Analyzing discipline: {dyscyplina_obj.nazwa}")

    candidates = identify_unpinning_candidates(dyscyplina_obj)

    preview_text = format_unpinning_preview(candidates)
    stdout.write(preview_text)

    if not candidates:
        stdout.write(style.WARNING("No unpinning candidates found."))
        return candidates

    if dry_run:
        stdout.write(
            style.WARNING(
                f"\nDry-run mode: {len(candidates)} publications would be modified."
            )
        )
    else:
        stdout.write("\nApplying unpinning decisions...")
        result = apply_unpinning(candidates, dyscyplina_obj, dry_run=False)

        stdout.write(
            style.SUCCESS(
                f"Applied unpinning: {result['unpinned_count']} assignments modified"
            )
        )

        if result["errors"]:
            for error in result["errors"]:
                stdout.write(style.ERROR(f"  Error: {error}"))

        stdout.write("Flushing denorms...")
        denorms.flush()
        stdout.write(style.SUCCESS("Denorms flushed"))

    return candidates
