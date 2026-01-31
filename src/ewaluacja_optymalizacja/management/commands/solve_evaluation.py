import json
from datetime import datetime
from decimal import Decimal

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Autor,
    Dyscyplina_Naukowa,
    Rekord,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    LiczbaNDlaUczelni,
)
from ewaluacja_optymalizacja.core import is_low_mono, solve_discipline
from ewaluacja_optymalizacja.models import (
    OptimizationAuthorResult,
    OptimizationPublication,
    OptimizationRun,
)


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
        parser.add_argument(
            "--algorithm-mode",
            type=str,
            default="two-phase",
            choices=["two-phase", "single-phase"],
            help='Algorithm mode: "two-phase" (default) or "single-phase"',
        )
        parser.add_argument(
            "--show-publications",
            action="store_true",
            default=False,
            help="Show detailed publication list per author at the end",
        )
        parser.add_argument(
            "--analyze-unpinning",
            action="store_true",
            default=False,
            help="Analyze optimal unpinning based on capacity rule, show recommendations",
        )
        parser.add_argument(
            "--auto-unpin",
            action="store_true",
            default=False,
            help="Apply capacity-based unpinning before optimization (with preview)",
        )
        parser.add_argument(
            "--analyze-pinning",
            action="store_true",
            default=False,
            help=(
                "After optimization, analyze which unpinned authors could be re-pinned "
                "to utilize free slots (Phase 3 analysis only, no changes)"
            ),
        )
        parser.add_argument(
            "--enable-pinning",
            action="store_true",
            default=False,
            help=(
                "Apply Phase 3 capacity-based pinning after optimization: "
                "re-pin authors who have free slots to unselected publications"
            ),
        )

    @transaction.atomic
    def handle(  # noqa: C901
        self,
        dyscyplina,
        output,
        verbose,
        unpin_not_selected,
        rerun_after_unpin,
        algorithm_mode,
        show_publications,
        analyze_unpinning,
        auto_unpin,
        analyze_pinning,
        enable_pinning,
        *args,
        **options,
    ):
        # Create log callback for core.solve_discipline
        def log_callback(msg, style=None):
            if style == "ERROR":
                self.stdout.write(self.style.ERROR(msg))
            elif style == "WARNING":
                self.stdout.write(self.style.WARNING(msg))
            elif style == "SUCCESS":
                self.stdout.write(self.style.SUCCESS(msg))
            else:
                self.stdout.write(msg)

        # Retrieve liczba_n for this discipline
        liczba_n = None
        try:
            uczelnia = Uczelnia.objects.first()
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            if uczelnia and dyscyplina_obj:
                liczba_n_obj = LiczbaNDlaUczelni.objects.get(
                    uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina_obj
                )
                liczba_n = float(liczba_n_obj.liczba_n_ostateczna)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Found for {dyscyplina}: N={liczba_n_obj.liczba_n}, "
                        f"sankcje={liczba_n_obj.sankcje}, "
                        f"3×N - sankcje = {liczba_n}"
                    )
                )
        except (Dyscyplina_Naukowa.DoesNotExist, LiczbaNDlaUczelni.DoesNotExist):
            self.stdout.write(
                self.style.WARNING(
                    f"No liczba_n found for discipline '{dyscyplina}'. "
                    "Institution constraint will not be applied."
                )
            )

        # Handle capacity-based unpinning analysis/application (PRE-optimization)
        if analyze_unpinning or auto_unpin:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            self._handle_capacity_based_unpinning(
                dyscyplina_obj,
                dry_run=not auto_unpin,  # If auto_unpin, apply changes
            )

            # If only analyzing (not applying), stop here
            if analyze_unpinning and not auto_unpin:
                self.stdout.write(
                    self.style.WARNING(
                        "\nAnalysis complete. Use --auto-unpin to apply changes "
                        "and run optimization."
                    )
                )
                return

        # Run optimization using core logic
        self.stdout.write(f"Using algorithm mode: {algorithm_mode}")
        try:
            results = solve_discipline(
                dyscyplina_nazwa=dyscyplina,
                verbose=verbose,
                log_callback=log_callback,
                liczba_n=liczba_n,
                algorithm_mode=algorithm_mode,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Optimization failed: {e}"))
            return

        if not results.all_pubs:
            self.stdout.write(
                self.style.WARNING(
                    f"No publications found for discipline '{dyscyplina}'"
                )
            )
            return

        # Save results to database
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("Saving results to database...")
        self.stdout.write("=" * 80)

        self._save_optimization_to_database(results, dyscyplina)

        # Load author names and publication records
        (
            authors,
            by_author,
            all_selected,
            author_names,
            rekords,
        ) = self._load_author_names_and_records(results)

        author_slot_limits = {
            author_id: data["limits"] for author_id, data in results.authors.items()
        }
        total_points = results.total_points

        # Display results
        if show_publications:
            self._display_author_results(
                authors, by_author, author_names, rekords, results
            )
        self._display_institution_statistics(all_selected, total_points)

        # Find and display unselected multi-author publications
        sorted_unselected = self._find_unselected_multi_author_pubs(
            results, all_selected, by_author, author_names, author_slot_limits, rekords
        )

        # Save results to file if requested
        if output:
            self._save_results_to_json_file(
                output,
                dyscyplina,
                total_points,
                all_selected,
                authors,
                by_author,
                author_names,
                rekords,
                sorted_unselected,
                author_slot_limits,
            )

        # Handle Phase 3: Capacity-based pinning (analyze or apply)
        if analyze_pinning or enable_pinning:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            self._handle_phase3_pinning(
                results,
                all_selected,
                author_slot_limits,
                dyscyplina_obj,
                log_callback,
                dry_run=not enable_pinning,  # If enable_pinning, apply changes
                rerun_after_pinning=enable_pinning,  # Re-run optimization after pinning
                algorithm_mode=algorithm_mode,
                verbose=verbose,
            )

        # Handle unpinning if requested
        if unpin_not_selected:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            self._handle_unpinning(
                all_selected,
                results.all_pubs,
                dyscyplina_obj,
                rerun_after_unpin,
                dyscyplina,
                output,
                verbose,
                algorithm_mode,
            )

    def _save_optimization_to_database(self, results, dyscyplina):
        """Save optimization results to database."""
        dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)

        # Usuń stare optymalizacje dla tej dyscypliny
        OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina_obj).delete()

        # Create OptimizationRun
        opt_run = OptimizationRun.objects.create(
            dyscyplina_naukowa=dyscyplina_obj,
            status="completed",
            total_points=Decimal(str(results.total_points)),
            total_slots=Decimal(str(results.total_slots)),
            total_publications=results.total_publications,
            low_mono_count=results.low_mono_count,
            low_mono_percentage=Decimal(str(results.low_mono_percentage)),
            validation_passed=results.validation_passed,
            finished_at=datetime.now(),
        )

        # Save author results
        for author_id, author_data in results.authors.items():
            selected_pubs = author_data["selected_pubs"]
            limits = author_data["limits"]

            # Get rodzaj_autora for this author
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
            mono_slots = sum(
                p.base_slots for p in selected_pubs if p.kind == "monography"
            )

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

            # Save publications for this author
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

        self.stdout.write(
            self.style.SUCCESS(f"Saved optimization run #{opt_run.pk} to database")
        )
        return opt_run

    def _load_author_names_and_records(self, results):
        """Load author names and publication records."""
        authors = sorted(results.authors.keys())
        by_author = {
            author_id: data["selected_pubs"]
            for author_id, data in results.authors.items()
        }
        all_selected = []
        for selections in by_author.values():
            all_selected.extend(selections)

        # Load author names
        author_names = {}
        for autor in Autor.objects.filter(pk__in=authors):
            author_names[autor.pk] = str(autor)

        # Load all publication titles
        all_rekord_ids = [p.id for p in all_selected]
        all_rekord_ids.extend(
            [
                p.id
                for p in results.all_pubs
                if p.id not in {pub.id for pub in all_selected}
            ]
        )
        all_rekord_ids = list(set(all_rekord_ids))

        rekords = {}
        for rekord in Rekord.objects.filter(pk__in=all_rekord_ids):
            rekords[rekord.pk] = rekord

        return authors, by_author, all_selected, author_names, rekords

    def _display_author_results(
        self, authors, by_author, author_names, rekords, results
    ):
        """Display per-author results."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("RESULTS BY AUTHOR:")
        self.stdout.write("=" * 80)

        author_slot_limits = {
            author_id: data["limits"] for author_id, data in results.authors.items()
        }

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

    def _display_institution_statistics(self, all_selected, total_points):
        """Display institution-level statistics."""
        sel_total = len(all_selected)
        sel_low = len([p for p in all_selected if is_low_mono(p)])
        share = (100.0 * sel_low / sel_total) if sel_total > 0 else 0.0

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

    def _find_unselected_multi_author_pubs(
        self,
        results,
        all_selected,
        by_author,
        author_names,
        author_slot_limits,
        rekords,
    ):
        """Find and organize unselected multi-author publications."""
        pubs = results.all_pubs

        # Count how many times each publication ID appears
        pub_id_counts = {}
        for p in pubs:
            if p.id not in pub_id_counts:
                pub_id_counts[p.id] = 0
            pub_id_counts[p.id] += 1

        selected_ids = {p.id for p in all_selected}

        # Find multi-author publications that were not selected
        unselected_multi_author = {}
        for p in pubs:
            if pub_id_counts[p.id] > 1 and p.id not in selected_ids:
                if p.id not in unselected_multi_author:
                    unselected_multi_author[p.id] = {
                        "publication": p,
                        "authors_detail": {},
                        "total_points": 0,
                        "total_slots": 0,
                        "efficiency": p.efficiency,
                        "author_count": p.author_count,
                    }
                unselected_multi_author[p.id]["authors_detail"][p.author] = {
                    "points": p.points,
                    "slots": p.base_slots,
                }
                unselected_multi_author[p.id]["total_points"] += p.points
                unselected_multi_author[p.id]["total_slots"] += p.base_slots

        sorted_unselected = sorted(
            unselected_multi_author.values(),
            key=lambda x: x["efficiency"],
            reverse=True,
        )

        # Display results
        if unselected_multi_author:
            self._display_unselected_multi_author_pubs(
                sorted_unselected,
                rekords,
                author_names,
                by_author,
                author_slot_limits,
            )

        return sorted_unselected

    def _display_unselected_multi_author_pubs(
        self, sorted_unselected, rekords, author_names, by_author, author_slot_limits
    ):
        """Display unselected multi-author publications."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("UNSELECTED MULTI-AUTHOR PUBLICATIONS:")
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"Found {len(sorted_unselected)} publications with multiple authors that were not selected:"
        )
        self.stdout.write(
            f"\nShowing ALL {len(sorted_unselected)} unselected multi-author publications\n"
        )

        for idx, item in enumerate(sorted_unselected, 1):
            p = item["publication"]
            rekord = rekords.get(p.id)
            title = rekord.tytul_oryginalny[:60] if rekord else f"ID: {p.id}"

            self.stdout.write(
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                f"\n[{idx}/{len(sorted_unselected)}] 📄 {title}..."
                f"\n  Type: {p.kind}, Authors with discipline: {p.author_count}"
                f"\n  Efficiency: {item['efficiency']:.2f} pts/slot"
            )

            self.stdout.write("\n  Authors who could have selected this work:")
            for author_id, details in item["authors_detail"].items():
                author_name = author_names.get(author_id, f"Author #{author_id}")
                selected_for_author = by_author.get(author_id, [])
                selected_points = sum(pub.points for pub in selected_for_author)
                selected_slots = sum(pub.base_slots for pub in selected_for_author)
                avg_pts_per_slot = (
                    (selected_points / selected_slots) if selected_slots > 0 else 0
                )
                limits = author_slot_limits.get(author_id, {"total": 4.0, "mono": 2.0})
                slot_percentage = (
                    (selected_slots / limits["total"] * 100)
                    if limits["total"] > 0
                    else 0
                )

                self.stdout.write(
                    f"\n    • {author_name}:"
                    f"\n      - This work: {details['points']:.1f} pts, {details['slots']:.2f} slots "
                    f"(NOT SELECTED, efficiency: {details['points'] / details['slots']:.2f} pts/slot)"
                    f"\n      - Actually selected: {selected_points:.1f} pts, "
                    f"{selected_slots:.2f}/{limits['total']:.1f} slots ({slot_percentage:.1f}% filled)"
                    f"\n      - Average efficiency of selected: {avg_pts_per_slot:.2f} pts/slot"
                    f"\n      - Selected {len(selected_for_author)} publication(s) instead"
                )

        # Summary
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

    def _save_results_to_json_file(
        self,
        output,
        dyscyplina,
        total_points,
        all_selected,
        authors,
        by_author,
        author_names,
        rekords,
        sorted_unselected,
        author_slot_limits,
    ):
        """Save results to JSON file."""
        sel_total = len(all_selected)
        sel_low = len([p for p in all_selected if is_low_mono(p)])
        share = (100.0 * sel_low / sel_total) if sel_total > 0 else 0.0
        total_slots_used = sum(p.base_slots for p in all_selected)
        points_per_slot = total_points / total_slots_used if total_slots_used > 0 else 0

        results_dict = {
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
                    "rekord_id": list(p.id),
                    "type": p.kind,
                    "points": p.points,
                    "slots": p.base_slots,
                    "low_point_mono": is_low_mono(p),
                    "title": rekord.tytul_oryginalny if rekord else None,
                }
                author_data["publications"].append(pub_data)

            results_dict["authors"].append(author_data)

        # Add unselected multi-author publications
        for item in sorted_unselected:
            p = item["publication"]
            rekord = rekords.get(p.id)

            authors_json = []
            for author_id, details in item["authors_detail"].items():
                selected_for_author = by_author.get(author_id, [])
                selected_points = sum(pub.points for pub in selected_for_author)
                selected_slots = sum(pub.base_slots for pub in selected_for_author)
                avg_pts_per_slot = (
                    (selected_points / selected_slots) if selected_slots > 0 else 0
                )
                unselected_efficiency = (
                    details["points"] / details["slots"] if details["slots"] > 0 else 0
                )
                limits = author_slot_limits.get(author_id, {"total": 4.0, "mono": 2.0})
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
            results_dict["unselected_multi_author_publications"].append(unselected_data)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"\nResults saved to: {output}"))

    def _handle_phase3_pinning(
        self,
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
        """
        Phase 3: Analyze and optionally apply capacity-based pinning.

        This finds unpinned authors who have free slots and can be re-pinned
        to unselected publications to utilize remaining capacity.

        Args:
            results: OptimizationResults from Phase 1+2
            all_selected: List of selected publications
            author_slot_limits: Dictionary of slot limits per author
            dyscyplina_obj: Dyscyplina_Naukowa object
            log_callback: Logging function
            dry_run: If True, show preview without applying changes
            rerun_after_pinning: If True, re-run optimization after pinning
            algorithm_mode: Algorithm mode for re-run
            verbose: Verbose output for re-run
        """
        from denorm import denorms

        from ewaluacja_optymalizacja.core import (
            analyze_pinning_candidates,
            apply_pinning_candidates,
        )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("PHASE 3: CAPACITY-BASED PINNING ANALYSIS")
        self.stdout.write("=" * 80)

        # Find pinning candidates
        candidates = analyze_pinning_candidates(
            all_selected=all_selected,
            all_pubs=results.all_pubs,
            author_slot_limits=author_slot_limits,
            dyscyplina_id=dyscyplina_obj.pk,
            log_func=log_callback,
        )

        if not candidates:
            self.stdout.write(self.style.WARNING("No pinning candidates found."))
            return

        # Calculate potential gains
        total_potential_points = sum(c.points for c in candidates)
        total_potential_slots = sum(c.slots for c in candidates)

        self.stdout.write("\n" + "-" * 40)
        self.stdout.write(f"Total candidates: {len(candidates)}")
        self.stdout.write(f"Potential points gain: {total_potential_points:.1f}")
        self.stdout.write(f"Potential slots used: {total_potential_slots:.2f}")
        self.stdout.write("-" * 40)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nAnalysis complete (dry-run). Use --enable-pinning to apply "
                    f"changes for {len(candidates)} candidates."
                )
            )
            return

        # Apply pinning changes
        self.stdout.write("\nApplying pinning changes...")
        result = apply_pinning_candidates(
            candidates=candidates,
            dyscyplina_obj=dyscyplina_obj,
            log_func=log_callback,
            dry_run=False,
        )

        if result["errors"]:
            for error in result["errors"]:
                self.stdout.write(self.style.ERROR(f"  Error: {error}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Applied pinning: {result['pinned_count']} assignments modified"
            )
        )

        # Flush denorms to update cache
        self.stdout.write("Flushing denorms...")
        denorms.flush()
        self.stdout.write(self.style.SUCCESS("Denorms flushed"))

        # Re-run optimization if requested
        if rerun_after_pinning and result["pinned_count"] > 0:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("RE-RUNNING OPTIMIZATION AFTER PINNING")
            self.stdout.write("=" * 80)

            from django.core.management import call_command

            # Prepare arguments for re-run
            rerun_args = [dyscyplina_obj.nazwa]
            rerun_kwargs = {
                "verbose": verbose,
                "algorithm_mode": algorithm_mode,
                "unpin_not_selected": False,
                "rerun_after_unpin": False,
                "analyze_unpinning": False,
                "auto_unpin": False,
                "analyze_pinning": False,
                "enable_pinning": False,  # Don't recurse
                "show_publications": False,
            }

            # Save old points for comparison
            old_points = results.total_points

            try:
                call_command("solve_evaluation", *rerun_args, **rerun_kwargs)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nPhase 3 complete. Previous points: {old_points:.1f}"
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error during re-run: {e}"))

    def _handle_capacity_based_unpinning(self, dyscyplina_obj, dry_run=True):
        """
        Analyze and optionally apply capacity-based unpinning.

        This implements the "capacity rule" algorithm (84% accuracy):
        For each multi-author publication, keep the author with
        MOST REMAINING CAPACITY (= 4.0 - current_slots), unpin others.

        Args:
            dyscyplina_obj: Dyscyplina_Naukowa object
            dry_run: If True, show preview without applying changes

        Returns:
            List of UnpinningCandidate objects
        """
        from denorm import denorms

        from ewaluacja_optymalizacja.tasks.unpinning.capacity_analysis import (
            apply_unpinning,
            format_unpinning_preview,
            identify_unpinning_candidates,
        )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("CAPACITY-BASED UNPINNING ANALYSIS")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Analyzing discipline: {dyscyplina_obj.nazwa}")

        # Find unpinning candidates
        candidates = identify_unpinning_candidates(dyscyplina_obj)

        # Display preview
        preview_text = format_unpinning_preview(candidates)
        self.stdout.write(preview_text)

        if not candidates:
            self.stdout.write(self.style.WARNING("No unpinning candidates found."))
            return candidates

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDry-run mode: {len(candidates)} publications would be modified."
                )
            )
        else:
            self.stdout.write("\nApplying unpinning decisions...")
            result = apply_unpinning(candidates, dyscyplina_obj, dry_run=False)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Applied unpinning: {result['unpinned_count']} assignments modified"
                )
            )

            if result["errors"]:
                for error in result["errors"]:
                    self.stdout.write(self.style.ERROR(f"  Error: {error}"))

            # Flush denorms to update cache
            self.stdout.write("Flushing denorms...")
            denorms.flush()
            self.stdout.write(self.style.SUCCESS("Denorms flushed"))

        return candidates

    def _handle_unpinning(
        self,
        selected_pubs,
        all_pubs,
        dyscyplina_obj,
        rerun_after_unpin,
        dyscyplina_name,
        output,
        verbose,
        algorithm_mode="two-phase",
    ):
        """Handle unpinning of disciplines for non-selected publications"""
        from denorm import denorms

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
                "algorithm_mode": algorithm_mode,  # Use same algorithm mode
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
