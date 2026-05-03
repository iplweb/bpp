"""Phase 3 capacity-based pinning analysis + application."""

from denorm import denorms

from ewaluacja_optymalizacja.core import (
    analyze_pinning_candidates,
    apply_pinning_candidates,
)


def handle_phase3_pinning(
    stdout,
    style,
    results,
    all_selected,
    author_slot_limits,
    dyscyplina_obj,
    log_callback,
    dry_run=True,
    rerun_after_pinning=False,
    algorithm_mode="two-phase",
    verbose=False,
):
    """Analyze and optionally apply capacity-based pinning.

    Finds unpinned authors who have free slots and can be re-pinned to
    unselected publications to utilise remaining capacity. With
    ``rerun_after_pinning=True`` the optimization is re-run after the
    pinning has been applied.
    """
    stdout.write("\n" + "=" * 80)
    stdout.write("PHASE 3: CAPACITY-BASED PINNING ANALYSIS")
    stdout.write("=" * 80)

    candidates = analyze_pinning_candidates(
        all_selected=all_selected,
        all_pubs=results.all_pubs,
        author_slot_limits=author_slot_limits,
        dyscyplina_id=dyscyplina_obj.pk,
        log_func=log_callback,
    )

    if not candidates:
        stdout.write(style.WARNING("No pinning candidates found."))
        return

    total_potential_points = sum(c.points for c in candidates)
    total_potential_slots = sum(c.slots for c in candidates)

    stdout.write("\n" + "-" * 40)
    stdout.write(f"Total candidates: {len(candidates)}")
    stdout.write(f"Potential points gain: {total_potential_points:.1f}")
    stdout.write(f"Potential slots used: {total_potential_slots:.2f}")
    stdout.write("-" * 40)

    if dry_run:
        stdout.write(
            style.WARNING(
                f"\nAnalysis complete (dry-run). Use --enable-pinning to apply "
                f"changes for {len(candidates)} candidates."
            )
        )
        return

    stdout.write("\nApplying pinning changes...")
    result = apply_pinning_candidates(
        candidates=candidates,
        dyscyplina_obj=dyscyplina_obj,
        log_func=log_callback,
        dry_run=False,
    )

    if result["errors"]:
        for error in result["errors"]:
            stdout.write(style.ERROR(f"  Error: {error}"))

    stdout.write(
        style.SUCCESS(f"Applied pinning: {result['pinned_count']} assignments modified")
    )

    stdout.write("Flushing denorms...")
    denorms.flush()
    stdout.write(style.SUCCESS("Denorms flushed"))

    if rerun_after_pinning and result["pinned_count"] > 0:
        stdout.write("\n" + "=" * 80)
        stdout.write("RE-RUNNING OPTIMIZATION AFTER PINNING")
        stdout.write("=" * 80)

        from django.core.management import call_command

        rerun_args = [dyscyplina_obj.nazwa]
        rerun_kwargs = {
            "verbose": verbose,
            "algorithm_mode": algorithm_mode,
            "unpin_not_selected": False,
            "rerun_after_unpin": False,
            "analyze_unpinning": False,
            "auto_unpin": False,
            "analyze_pinning": False,
            "enable_pinning": False,
            "show_publications": False,
        }

        old_points = results.total_points

        try:
            call_command("solve_evaluation", *rerun_args, **rerun_kwargs)
            stdout.write(
                style.SUCCESS(f"\nPhase 3 complete. Previous points: {old_points:.1f}")
            )
        except Exception as e:
            stdout.write(style.ERROR(f"Error during re-run: {e}"))
