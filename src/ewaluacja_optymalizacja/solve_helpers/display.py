"""Console display helpers for optimization results."""

from ewaluacja_optymalizacja.core import is_low_mono


def display_author_results(stdout, authors, by_author, author_names, rekords, results):
    """Print per-author selection summary."""
    stdout.write("\n" + "=" * 80)
    stdout.write("RESULTS BY AUTHOR:")
    stdout.write("=" * 80)

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
        stdout.write(
            f"\n{author_name}: "
            f"points={pts:.1f}, slots={total_slots:.1f} "
            f"(mono={mono_slots:.1f}) {limit_info}"
        )

        for p in chosen:
            tag = "LOW-MONO" if is_low_mono(p) else p.kind.upper()
            rekord = rekords.get(p.id)
            title = rekord.tytul_oryginalny[:60] if rekord else f"ID: {p.id}"
            stdout.write(
                f"  - {tag}: pts={p.points:.1f}, slots={p.base_slots}, "
                f"title: {title}..."
            )


def display_institution_statistics(stdout, all_selected, total_points):
    """Print institution-level summary statistics."""
    sel_total = len(all_selected)
    sel_low = len([p for p in all_selected if is_low_mono(p)])
    share = (100.0 * sel_low / sel_total) if sel_total > 0 else 0.0

    total_slots_used = sum(p.base_slots for p in all_selected)
    points_per_slot = total_points / total_slots_used if total_slots_used > 0 else 0

    stdout.write("\n" + "=" * 80)
    stdout.write("INSTITUTION STATISTICS:")
    stdout.write("=" * 80)
    stdout.write(
        f"Selected publications: {sel_total}\n"
        f"Low-point monographies: {sel_low} ({share:.1f}% ≤ 20%)\n"
        f"Total slots used: {total_slots_used:.2f}\n"
        f"Total points collected: {total_points:.1f}\n"
        f"Average points per slot: {points_per_slot:.2f}"
    )


def find_unselected_multi_author_pubs(
    stdout,
    results,
    all_selected,
    by_author,
    author_names,
    author_slot_limits,
    rekords,
):
    """Group unselected multi-author publications and (if any) print them.

    Returns the sorted list of unselected publication detail dicts.
    """
    pubs = results.all_pubs

    pub_id_counts = {}
    for p in pubs:
        if p.id not in pub_id_counts:
            pub_id_counts[p.id] = 0
        pub_id_counts[p.id] += 1

    selected_ids = {p.id for p in all_selected}

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

    if unselected_multi_author:
        _display_unselected_multi_author_pubs(
            stdout,
            sorted_unselected,
            rekords,
            author_names,
            by_author,
            author_slot_limits,
        )

    return sorted_unselected


def _display_unselected_multi_author_pubs(
    stdout, sorted_unselected, rekords, author_names, by_author, author_slot_limits
):
    """Render the unselected-multi-author block."""
    stdout.write("\n" + "=" * 80)
    stdout.write("UNSELECTED MULTI-AUTHOR PUBLICATIONS:")
    stdout.write("=" * 80)
    stdout.write(
        f"Found {len(sorted_unselected)} publications with multiple authors "
        "that were not selected:"
    )
    stdout.write(
        f"\nShowing ALL {len(sorted_unselected)} unselected multi-author publications\n"
    )

    for idx, item in enumerate(sorted_unselected, 1):
        p = item["publication"]
        rekord = rekords.get(p.id)
        title = rekord.tytul_oryginalny[:60] if rekord else f"ID: {p.id}"

        stdout.write(
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            f"\n[{idx}/{len(sorted_unselected)}] 📄 {title}..."
            f"\n  Type: {p.kind}, Authors with discipline: {p.author_count}"
            f"\n  Efficiency: {item['efficiency']:.2f} pts/slot"
        )

        stdout.write("\n  Authors who could have selected this work:")
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
                (selected_slots / limits["total"] * 100) if limits["total"] > 0 else 0
            )

            stdout.write(
                f"\n    • {author_name}:"
                f"\n      - This work: {details['points']:.1f} pts, "
                f"{details['slots']:.2f} slots "
                f"(NOT SELECTED, "
                f"efficiency: {details['points'] / details['slots']:.2f} "
                "pts/slot)"
                f"\n      - Actually selected: {selected_points:.1f} pts, "
                f"{selected_slots:.2f}/{limits['total']:.1f} slots "
                f"({slot_percentage:.1f}% filled)"
                f"\n      - Average efficiency of selected: "
                f"{avg_pts_per_slot:.2f} pts/slot"
                f"\n      - Selected {len(selected_for_author)} "
                "publication(s) instead"
            )

    total_unselected_potential_points = sum(
        item["total_points"] for item in sorted_unselected
    )
    total_unselected_potential_slots = sum(
        item["total_slots"] for item in sorted_unselected
    )

    stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    stdout.write("\nSUMMARY OF UNSELECTED MULTI-AUTHOR PUBLICATIONS:")
    stdout.write(f"  - Total unselected publications: {len(sorted_unselected)}")
    stdout.write(
        "  - Total potential points not utilized: "
        f"{total_unselected_potential_points:.1f}"
    )
    stdout.write(
        "  - Total potential slots not utilized: "
        f"{total_unselected_potential_slots:.2f}"
    )
