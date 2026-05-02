"""JSON serialization of optimization results to disk."""

import json

from ewaluacja_optymalizacja.core import is_low_mono


def save_results_to_json_file(
    stdout,
    style,
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
    """Write a structured JSON dump of the optimization to ``output``."""
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
                (selected_slots / limits["total"] * 100) if limits["total"] > 0 else 0
            )

            authors_json.append(
                {
                    "author_id": author_id,
                    "author_name": author_names.get(author_id, f"Author #{author_id}"),
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

    stdout.write(style.SUCCESS(f"\nResults saved to: {output}"))
