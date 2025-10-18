import json
import sys
from dataclasses import dataclass

from django.core.management import BaseCommand
from django.db import transaction
from ortools.sat.python import cp_model
from tqdm import tqdm

from bpp import const
from bpp.models import Cache_Punktacja_Autora_Query, Dyscyplina_Naukowa, Rekord
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

# We'll scale slot numbers by 1000 for better precision (integers for CP-SAT)
SCALE = 1000


@dataclass(frozen=True)
class Pub:
    id: tuple  # (content_type_id, object_id) from rekord_id
    author: int  # autor_id
    kind: str  # "article" | "monography"
    points: float  # pkdaut from cache
    base_slots: float  # slot value from cache
    author_count: int  # number of authors with pinned disciplines

    @property
    def efficiency(self) -> float:
        """Points per slot ratio for optimization"""
        return self.points / self.base_slots if self.base_slots > 0 else 0


def slot_units(p: Pub) -> int:
    """Convert float slots to scaled integer units for CP-SAT solver"""
    # Use floor (int()) instead of round() to never exceed limits
    return int(p.base_slots * SCALE)


def is_low_mono(p: Pub) -> bool:
    """Check if publication is a low-point monography (< 200 points)"""
    return p.kind == "monography" and p.points < 200


def solve_author_knapsack(
    author_pubs: list[Pub], max_slots: float, max_mono_slots: float
) -> list[Pub]:
    """
    Solve knapsack problem for a single author using dynamic programming.
    Returns list of selected publications that maximize points within slot constraints.
    """
    if not author_pubs:
        return []

    # Sort by efficiency (points/slot ratio) descending, then by author count ascending
    # This ensures that when efficiency is equal, works with fewer authors are prioritized
    sorted_pubs = sorted(author_pubs, key=lambda p: (-p.efficiency, p.author_count))

    # Use CP-SAT for single-author optimization with both constraints
    m = cp_model.CpModel()

    # Decision variables
    selected = {}
    for p in sorted_pubs:
        selected[p.id] = m.NewBoolVar(f"select_{p.id[0]}_{p.id[1]}")

    # Objective: maximize points
    m.Maximize(sum(p.points * selected[p.id] for p in sorted_pubs))

    # Constraint 1: Total slots
    m.Add(
        sum(int(p.base_slots * SCALE) * selected[p.id] for p in sorted_pubs)
        <= int(max_slots * SCALE)
    )

    # Constraint 2: Monography slots
    mono_pubs = [p for p in sorted_pubs if p.kind == "monography"]
    if mono_pubs:
        m.Add(
            sum(int(p.base_slots * SCALE) * selected[p.id] for p in mono_pubs)
            <= int(max_mono_slots * SCALE)
        )

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # Single thread for deterministic results
    status = solver.Solve(m)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return []

    # Return selected publications
    result = []
    for p in sorted_pubs:
        if solver.Value(selected[p.id]) == 1:
            result.append(p)

    return result


def generate_pub_data(dyscyplina_nazwa: str) -> list[Pub]:
    """
    Generate publication data from cache_punktacja_autora table.

    Args:
        dyscyplina_nazwa: Name of the scientific discipline to filter by

    Returns:
        List of Pub objects with data from database
    """
    # Get discipline object
    try:
        dyscyplina = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)
    except Dyscyplina_Naukowa.DoesNotExist:
        raise ValueError(f"Discipline '{dyscyplina_nazwa}' not found in database")

    # Query cache data for years 2022-2025 and given discipline
    cache_entries = (
        Cache_Punktacja_Autora_Query.objects.filter(
            dyscyplina=dyscyplina,
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
        )
        .select_related(
            "autor",
            "rekord",
        )
        .exclude(pkdaut=0)  # Exclude publications with 0 points
        .exclude(slot=0)  # Exclude publications with 0 slots
    )

    pubs = []
    for entry in tqdm(cache_entries):
        rekord = entry.rekord

        # Determine publication kind based on charakter_ogolny
        charakter_ogolny = rekord.charakter_formalny.charakter_ogolny
        if charakter_ogolny == const.CHARAKTER_OGOLNY_ARTYKUL:
            kind = "article"
        elif charakter_ogolny == const.CHARAKTER_OGOLNY_KSIAZKA:
            kind = "monography"
        else:
            # Skip other types (chapters, etc.)
            continue

        # Count authors with pinned disciplines
        author_count = rekord.original.autorzy_set.filter(
            dyscyplina_naukowa__isnull=False, przypieta=True
        ).count()

        pub = Pub(
            id=entry.rekord_id,  # This is already a tuple
            author=entry.autor_id,
            kind=kind,
            points=float(entry.pkdaut),
            base_slots=float(entry.slot),
            author_count=author_count,
        )
        pubs.append(pub)

    return pubs


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """Callback to report solver progress"""

    def __init__(self, variables, pubs, verbose=False):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.variables = variables
        self.pubs = pubs
        self.solution_count = 0
        self.verbose = verbose
        self.best_objective = 0

    def on_solution_callback(self):
        self.solution_count += 1
        current_objective = self.ObjectiveValue()

        if current_objective > self.best_objective:
            self.best_objective = current_objective
            if self.verbose:
                sys.stdout.write(
                    f"\rFound solution #{self.solution_count}: {int(current_objective)} points"
                )
                sys.stdout.flush()
            else:
                sys.stdout.write(".")
                sys.stdout.flush()


class Command(BaseCommand):
    help = """Solve evaluation optimization problem using CP-SAT solver.

    This command finds the optimal selection of publications for evaluation
    considering constraints on slots per author and institution-wide quotas.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "dyscyplina",
            type=str,
            help='Scientific discipline name (e.g., "nauki medyczne")',
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path for results (JSON format)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Show detailed progress during solving",
        )
        parser.add_argument(
            "--unpin-not-selected",
            action="store_true",
            default=False,
            help="Unpin disciplines for authors in publications that were not selected for reporting",
        )
        parser.add_argument(
            "--rerun-after-unpin",
            action="store_true",
            default=False,
            help="Re-run the optimization after unpinning (use with --unpin-not-selected)",
        )

    @transaction.atomic
    def handle(
        self,
        dyscyplina,
        output,
        verbose,
        unpin_not_selected,
        rerun_after_unpin,
        *args,
        **options,
    ):
        self.stdout.write(f"Loading publications for discipline: {dyscyplina}")
        self.stdout.write("Year range: 2022-2025")

        # Generate publication data from database
        try:
            pubs = generate_pub_data(dyscyplina)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        if not pubs:
            self.stdout.write(
                self.style.WARNING(
                    f"No publications found for discipline '{dyscyplina}' in years 2022-2025"
                )
            )
            return

        self.stdout.write(f"Found {len(pubs)} publications")

        # Get unique authors
        authors = sorted({p.author for p in pubs})
        self.stdout.write(f"Found {len(authors)} unique authors")

        # Get discipline object for loading slot limits
        try:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
        except Dyscyplina_Naukowa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Discipline '{dyscyplina}' not found"))
            return

        # Load per-author slot limits from database
        self.stdout.write("Loading author slot limits from database...")
        author_slot_limits = {}
        custom_limit_count = 0

        for author_id in authors:
            try:
                limits = IloscUdzialowDlaAutoraZaCalosc.objects.get(
                    autor_id=author_id, dyscyplina_naukowa=dyscyplina_obj
                )
                author_slot_limits[author_id] = {
                    "total": float(limits.ilosc_udzialow),
                    "mono": float(limits.ilosc_udzialow_monografie),
                }
                custom_limit_count += 1
            except IloscUdzialowDlaAutoraZaCalosc.DoesNotExist:
                # Use default limits if not specified
                author_slot_limits[author_id] = {"total": 4.0, "mono": 2.0}

        self.stdout.write(f"Found custom slot limits for {custom_limit_count} authors")

        # PHASE 1: Solve per-author knapsack problems
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("PHASE 1: Per-author optimization")
        self.stdout.write("=" * 80)

        # Group publications by author
        pubs_by_author = {}
        for p in pubs:
            if p.author not in pubs_by_author:
                pubs_by_author[p.author] = []
            pubs_by_author[p.author].append(p)

        # Solve knapsack for each author
        author_selections = {}
        total_phase1_points = 0

        for author_id in authors:
            author_pubs = pubs_by_author.get(author_id, [])
            if not author_pubs:
                continue

            limits = author_slot_limits[author_id]
            if verbose:
                self.stdout.write(
                    f"\nOptimizing for author {author_id}: {len(author_pubs)} publications"
                )
                self.stdout.write(
                    f"  Limits: {limits['total']} total slots, {limits['mono']} mono slots"
                )

            # Solve knapsack for this author
            selected = solve_author_knapsack(
                author_pubs, limits["total"], limits["mono"]
            )

            author_selections[author_id] = selected
            author_points = sum(p.points for p in selected)
            author_slots = sum(p.base_slots for p in selected)
            total_phase1_points += author_points

            if verbose:
                self.stdout.write(
                    f"  Selected: {len(selected)} pubs, {author_points:.1f} points, {author_slots:.2f} slots"
                )

        self.stdout.write(f"\nPhase 1 complete: {total_phase1_points:.1f} total points")

        # Collect all selected publications
        all_selected = []
        for selections in author_selections.values():
            all_selected.extend(selections)

        # PHASE 2: Check institution-level constraints
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("PHASE 2: Institution-level constraints")
        self.stdout.write("=" * 80)

        # Count low-point monographies
        low_mono_selected = [p for p in all_selected if is_low_mono(p)]
        low_mono_percentage = (
            (100.0 * len(low_mono_selected) / len(all_selected)) if all_selected else 0
        )

        self.stdout.write(
            f"Low-point monographies: {len(low_mono_selected)}/{len(all_selected)} ({low_mono_percentage:.1f}%)"
        )

        # If we exceed 20% low-point monographies, we need to adjust
        if low_mono_percentage > 20.0 and len(low_mono_selected) > 0:
            self.stdout.write(
                self.style.WARNING("Exceeds 20% limit - adjusting selection...")
            )

            # Use CP-SAT to globally optimize while respecting all constraints
            m = cp_model.CpModel()

            # Decision variables for all pre-selected publications
            y = {p.id: m.NewBoolVar(f"y_{p.id[0]}_{p.id[1]}") for p in all_selected}

            # Objective: maximize points from pre-selected items
            m.Maximize(sum(p.points * y[p.id] for p in all_selected))

            # Per-author constraints (ensure we don't exceed limits)
            for author_id in authors:
                author_pubs = [p for p in all_selected if p.author == author_id]
                if not author_pubs:
                    continue

                limits = author_slot_limits[author_id]

                # Total slots
                m.Add(
                    sum(slot_units(p) * y[p.id] for p in author_pubs)
                    <= int(limits["total"] * SCALE)
                )

                # Monography slots
                mono_pubs = [p for p in author_pubs if p.kind == "monography"]
                if mono_pubs:
                    m.Add(
                        sum(slot_units(p) * y[p.id] for p in mono_pubs)
                        <= int(limits["mono"] * SCALE)
                    )

            # Institution quota constraint
            low_mono_count = sum(y[p.id] for p in all_selected if is_low_mono(p))
            total_count = sum(y[p.id] for p in all_selected)
            m.Add(5 * low_mono_count <= total_count)  # 20% limit

            # Solve
            solver = cp_model.CpSolver()
            status = solver.Solve(m)

            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                self.stdout.write(
                    self.style.ERROR("Could not satisfy institution constraints!")
                )
                return

            # Update selections based on global optimization
            final_selected = []
            for p in all_selected:
                if solver.Value(y[p.id]) == 1:
                    final_selected.append(p)

            all_selected = final_selected
            total_points = sum(p.points for p in all_selected)
            self.stdout.write(
                f"Adjusted selection: {len(all_selected)} publications, {total_points:.1f} points"
            )
        else:
            total_points = total_phase1_points
            self.stdout.write(self.style.SUCCESS("Institution constraints satisfied"))

        # Organize final results by author
        by_author: dict[int, list[Pub]] = {a: [] for a in authors}
        for p in all_selected:
            by_author[p.author].append(p)

        # Validation: Check that no author exceeds their limits
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("VALIDATION: Checking slot limits")
        self.stdout.write("=" * 80)

        validation_passed = True
        for author_id in authors:
            chosen = by_author[author_id]
            if not chosen:
                continue

            total_slots = sum(p.base_slots for p in chosen)
            mono_slots = sum(p.base_slots for p in chosen if p.kind == "monography")
            limits = author_slot_limits[author_id]

            if (
                total_slots > limits["total"] + 0.001
            ):  # Small epsilon for floating point
                self.stdout.write(
                    self.style.ERROR(
                        f"Author {author_id}: {total_slots:.2f} slots > {limits['total']} limit!"
                    )
                )
                validation_passed = False

            if mono_slots > limits["mono"] + 0.001:
                self.stdout.write(
                    self.style.ERROR(
                        f"Author {author_id}: {mono_slots:.2f} mono slots > {limits['mono']} limit!"
                    )
                )
                validation_passed = False

        if validation_passed:
            self.stdout.write(self.style.SUCCESS("✓ All slot limits satisfied"))
        else:
            self.stdout.write(
                self.style.ERROR("✗ Validation failed - slot limits exceeded!")
            )

        self.stdout.write(self.style.SUCCESS(f"\nTotal points: {int(total_points)}"))

        # Load author names for better display
        from bpp.models import Autor

        author_names = {}
        for autor in Autor.objects.filter(pk__in=authors):
            author_names[autor.pk] = str(autor)

        # Display per-author results
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("RESULTS BY AUTHOR:")
        self.stdout.write("=" * 80)

        # Load all publication titles for selected and unselected multi-author items
        all_rekord_ids = [p.id for p in all_selected]
        # Also add unselected multi-author publication IDs
        all_rekord_ids.extend(
            [p.id for p in pubs if p.id not in {pub.id for pub in all_selected}]
        )
        # Remove duplicates
        all_rekord_ids = list(set(all_rekord_ids))

        rekords = {}
        for rekord in Rekord.objects.filter(pk__in=all_rekord_ids):
            rekords[rekord.pk] = rekord

        for author_id in authors:
            chosen = by_author[author_id]
            if not chosen:
                continue

            total_slots = sum(p.base_slots for p in chosen)
            mono_slots = sum(p.base_slots for p in chosen if p.kind == "monography")
            pts = sum(p.points for p in chosen)

            author_name = author_names.get(author_id, f"Author #{author_id}")
            limits = author_slot_limits.get(author_id, {"total": 4.0, "mono": 2.0})
            limit_info = f"(limit: {limits['total']}/{limits['mono']})"
            self.stdout.write(
                f"\n{author_name}: "
                f"points={pts:.1f}, slots={total_slots:.1f} (mono={mono_slots:.1f}) {limit_info}"
            )

            for p in chosen:
                tag = "LOW-MONO" if is_low_mono(p) else p.kind.upper()
                rekord = rekords.get(p.id)
                title = rekord.tytul_oryginalny[:60] if rekord else f"ID: {p.id}"
                self.stdout.write(
                    f"  - {tag}: pts={p.points:.1f}, slots={p.base_slots}, "
                    f"title: {title}..."
                )

        # Institution-level statistics
        sel_total = len(all_selected)
        sel_low = len([p for p in all_selected if is_low_mono(p)])
        share = (100.0 * sel_low / sel_total) if sel_total > 0 else 0.0

        # Calculate total slots used and points per slot
        total_slots_used = sum(p.base_slots for p in all_selected)
        points_per_slot = total_points / total_slots_used if total_slots_used > 0 else 0

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("INSTITUTION STATISTICS:")
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"Selected publications: {sel_total}\n"
            f"Low-point monographies: {sel_low} ({share:.1f}% ≤ 20%)\n"
            f"Total slots used: {total_slots_used:.2f}\n"
            f"Total points collected: {total_points:.1f}\n"
            f"Average points per slot: {points_per_slot:.2f}"
        )

        # Find unselected multi-author publications
        # Count how many times each publication ID appears in the original dataset
        pub_id_counts = {}
        for p in pubs:
            if p.id not in pub_id_counts:
                pub_id_counts[p.id] = 0
            pub_id_counts[p.id] += 1

        # Get IDs of selected publications
        selected_ids = {p.id for p in all_selected}

        # Find multi-author publications that were not selected
        unselected_multi_author = {}
        for p in pubs:
            if pub_id_counts[p.id] > 1 and p.id not in selected_ids:
                if p.id not in unselected_multi_author:
                    unselected_multi_author[p.id] = {
                        "publication": p,
                        "authors_detail": {},  # Store detailed info per author
                        "total_points": 0,
                        "total_slots": 0,
                        "efficiency": p.efficiency,
                        "author_count": p.author_count,
                    }
                # Store detailed info for each author
                unselected_multi_author[p.id]["authors_detail"][p.author] = {
                    "points": p.points,
                    "slots": p.base_slots,
                }
                unselected_multi_author[p.id]["total_points"] += p.points
                unselected_multi_author[p.id]["total_slots"] += p.base_slots

        # Sort by efficiency (descending) for better readability
        sorted_unselected = sorted(
            unselected_multi_author.values(),
            key=lambda x: x["efficiency"],
            reverse=True,
        )

        # Report unselected multi-author publications
        if unselected_multi_author:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("UNSELECTED MULTI-AUTHOR PUBLICATIONS:")
            self.stdout.write("=" * 80)
            self.stdout.write(
                f"Found {len(unselected_multi_author)} publications with multiple authors that were not selected:"
            )
            self.stdout.write(
                f"\nShowing ALL {len(sorted_unselected)} unselected multi-author publications\n"
            )

            for idx, item in enumerate(sorted_unselected, 1):  # Show ALL publications
                p = item["publication"]
                rekord = rekords.get(p.id)
                title = rekord.tytul_oryginalny[:60] if rekord else f"ID: {p.id}"

                self.stdout.write(
                    f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    f"\n[{idx}/{len(sorted_unselected)}] 📄 {title}..."
                    f"\n  Type: {p.kind}, Authors with discipline: {p.author_count}"
                    f"\n  Efficiency: {item['efficiency']:.2f} pts/slot"
                )

                # Show per-author details
                self.stdout.write("\n  Authors who could have selected this work:")
                for author_id, details in item["authors_detail"].items():
                    author_name = author_names.get(author_id, f"Author #{author_id}")

                    # Get what was actually selected for this author
                    selected_for_author = by_author.get(author_id, [])
                    selected_points = sum(pub.points for pub in selected_for_author)
                    selected_slots = sum(pub.base_slots for pub in selected_for_author)

                    # Calculate average points/slot for selected publications
                    avg_pts_per_slot = (
                        (selected_points / selected_slots) if selected_slots > 0 else 0
                    )

                    # Get author's slot limits
                    limits = author_slot_limits.get(
                        author_id, {"total": 4.0, "mono": 2.0}
                    )
                    slot_percentage = (
                        (selected_slots / limits["total"] * 100)
                        if limits["total"] > 0
                        else 0
                    )

                    self.stdout.write(
                        f"\n    • {author_name}:"
                        f"\n      - This work: {details['points']:.1f} pts, {details['slots']:.2f} slots "
                        f"(NOT SELECTED, efficiency: {details['points']/details['slots']:.2f} pts/slot)"
                        f"\n      - Actually selected: {selected_points:.1f} pts, "
                        f"{selected_slots:.2f}/{limits['total']:.1f} slots ({slot_percentage:.1f}% filled)"
                        f"\n      - Average efficiency of selected: {avg_pts_per_slot:.2f} pts/slot"
                        f"\n      - Selected {len(selected_for_author)} publication(s) instead"
                    )

            # Summary of unselected publications
            total_unselected_potential_points = sum(
                item["total_points"] for item in sorted_unselected
            )
            total_unselected_potential_slots = sum(
                item["total_slots"] for item in sorted_unselected
            )

            self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.stdout.write("\nSUMMARY OF UNSELECTED MULTI-AUTHOR PUBLICATIONS:")
            self.stdout.write(
                f"  - Total unselected publications: {len(sorted_unselected)}"
            )
            self.stdout.write(
                f"  - Total potential points not utilized: {total_unselected_potential_points:.1f}"
            )
            self.stdout.write(
                f"  - Total potential slots not utilized: {total_unselected_potential_slots:.2f}"
            )

        # Save results to file if requested
        if output:
            results = {
                "discipline": dyscyplina,
                "year_range": "2022-2025",
                "total_points": round(total_points, 2),
                "total_publications": sel_total,
                "total_slots_used": round(total_slots_used, 2),
                "average_points_per_slot": round(points_per_slot, 2),
                "low_point_monographies": sel_low,
                "low_point_percentage": round(share, 2),
                "authors": [],
                "unselected_multi_author_publications": [],
            }

            for author_id in authors:
                chosen = by_author[author_id]
                if not chosen:
                    continue

                author_data = {
                    "author_id": author_id,
                    "author_name": author_names.get(author_id, f"Author #{author_id}"),
                    "total_points": sum(p.points for p in chosen),
                    "total_slots": sum(p.base_slots for p in chosen),
                    "monography_slots": sum(
                        p.base_slots for p in chosen if p.kind == "monography"
                    ),
                    "publications": [],
                }

                for p in chosen:
                    rekord = rekords.get(p.id)
                    pub_data = {
                        "rekord_id": list(p.id),  # Convert tuple to list for JSON
                        "type": p.kind,
                        "points": p.points,
                        "slots": p.base_slots,
                        "low_point_mono": is_low_mono(p),
                        "title": rekord.tytul_oryginalny if rekord else None,
                    }
                    author_data["publications"].append(pub_data)

                results["authors"].append(author_data)

            # Add unselected multi-author publications to results
            for item in sorted_unselected:
                p = item["publication"]
                rekord = rekords.get(p.id)

                # Build author details for JSON
                authors_json = []
                for author_id, details in item["authors_detail"].items():
                    selected_for_author = by_author.get(author_id, [])
                    selected_points = sum(pub.points for pub in selected_for_author)
                    selected_slots = sum(pub.base_slots for pub in selected_for_author)
                    avg_pts_per_slot = (
                        (selected_points / selected_slots) if selected_slots > 0 else 0
                    )
                    unselected_efficiency = (
                        details["points"] / details["slots"]
                        if details["slots"] > 0
                        else 0
                    )
                    limits = author_slot_limits.get(
                        author_id, {"total": 4.0, "mono": 2.0}
                    )
                    slot_percentage = (
                        (selected_slots / limits["total"] * 100)
                        if limits["total"] > 0
                        else 0
                    )

                    authors_json.append(
                        {
                            "author_id": author_id,
                            "author_name": author_names.get(
                                author_id, f"Author #{author_id}"
                            ),
                            "unselected_points": round(details["points"], 2),
                            "unselected_slots": round(details["slots"], 2),
                            "unselected_efficiency": round(unselected_efficiency, 2),
                            "selected_points": round(selected_points, 2),
                            "selected_slots": round(selected_slots, 2),
                            "selected_avg_efficiency": round(avg_pts_per_slot, 2),
                            "slot_limit": round(limits["total"], 2),
                            "slot_usage_percentage": round(slot_percentage, 1),
                            "selected_publication_count": len(selected_for_author),
                        }
                    )

                unselected_data = {
                    "rekord_id": list(p.id),
                    "type": p.kind,
                    "efficiency": round(item["efficiency"], 2),
                    "total_points": round(item["total_points"], 2),
                    "total_slots": round(item["total_slots"], 2),
                    "author_count": p.author_count,
                    "authors_detail": authors_json,
                    "title": rekord.tytul_oryginalny if rekord else None,
                }
                results["unselected_multi_author_publications"].append(unselected_data)

            with open(output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            self.stdout.write(self.style.SUCCESS(f"\nResults saved to: {output}"))

        # Handle unpinning if requested
        if unpin_not_selected:
            self._handle_unpinning(
                all_selected,
                pubs,
                dyscyplina_obj,
                rerun_after_unpin,
                dyscyplina,
                output,
                verbose,
            )

    def _handle_unpinning(
        self,
        selected_pubs,
        all_pubs,
        dyscyplina_obj,
        rerun_after_unpin,
        dyscyplina_name,
        output,
        verbose,
    ):
        """Handle unpinning of disciplines for non-selected publications"""
        from denorm import denorms

        from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("UNPINNING NON-SELECTED PUBLICATIONS")
        self.stdout.write("=" * 80)

        # Get IDs of selected publications
        selected_ids = {p.id for p in selected_pubs}

        # Find all non-selected publications for this discipline
        non_selected_pubs = [p for p in all_pubs if p.id not in selected_ids]

        if not non_selected_pubs:
            self.stdout.write(self.style.WARNING("No publications to unpin"))
            return

        self.stdout.write(
            f"Found {len(non_selected_pubs)} non-selected publication-author pairs"
        )

        # Group by publication ID and author to unpin
        to_unpin = {}
        for p in non_selected_pubs:
            key = (p.id, p.author)
            to_unpin[key] = p

        self.stdout.write(
            f"Unpinning {len(to_unpin)} author-publication associations..."
        )

        unpinned_count = 0
        with transaction.atomic():
            for (rekord_id, autor_id), pub in to_unpin.items():
                content_type_id, object_id = rekord_id

                # Determine the model based on publication type
                if pub.kind == "article":
                    # Try Wydawnictwo_Ciagle_Autor
                    updated = Wydawnictwo_Ciagle_Autor.objects.filter(
                        rekord_id=object_id,
                        autor_id=autor_id,
                        dyscyplina_naukowa=dyscyplina_obj,
                        przypieta=True,
                    ).update(przypieta=False)
                    unpinned_count += updated
                elif pub.kind == "monography":
                    # Try Wydawnictwo_Zwarte_Autor
                    updated = Wydawnictwo_Zwarte_Autor.objects.filter(
                        rekord_id=object_id,
                        autor_id=autor_id,
                        dyscyplina_naukowa=dyscyplina_obj,
                        przypieta=True,
                    ).update(przypieta=False)
                    unpinned_count += updated
                # Patents could also be handled here if needed

        self.stdout.write(
            self.style.SUCCESS(
                f"Unpinned {unpinned_count} author-discipline associations"
            )
        )

        # Flush denorms to update cache
        self.stdout.write("Flushing denorms...")
        denorms.flush()
        self.stdout.write(self.style.SUCCESS("Denorms flushed"))

        # Re-run optimization if requested
        if rerun_after_unpin:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("RE-RUNNING OPTIMIZATION AFTER UNPINNING")
            self.stdout.write("=" * 80)

            # Import at the top of the method to avoid circular imports
            from django.core.management import call_command

            # Prepare arguments for re-run
            rerun_args = [dyscyplina_name]
            rerun_kwargs = {
                "verbose": verbose,
                "unpin_not_selected": False,  # Don't unpin again
                "rerun_after_unpin": False,  # Don't recurse
            }

            if output:
                # Modify output filename for re-run results
                import os

                base, ext = os.path.splitext(output)
                rerun_output = f"{base}_after_unpin{ext}"
                rerun_kwargs["output"] = rerun_output
                self.stdout.write(f"Re-run results will be saved to: {rerun_output}")

            # Call the command again
            call_command("solve_evaluation", *rerun_args, **rerun_kwargs)
