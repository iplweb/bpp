"""Charakter formalny statistics views for admin dashboard."""

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F
from django.http import JsonResponse
from django.views.decorators.cache import cache_page

from bpp.models import Charakter_Formalny


def _get_admin_url_for_charakter(skrot, charakter_id, ciagle_count, zwarte_count):
    """
    Determine appropriate admin URL for a given charakter formalny.

    Args:
        skrot: Charakter skrót (e.g., "PAT", "D", "H", "AC")
        charakter_id: ID of the Charakter_Formalny
        ciagle_count: Number of Wydawnictwo_Ciagle records
        zwarte_count: Number of Wydawnictwo_Zwarte records

    Returns:
        str: Admin URL with charakter_formalny filter
    """
    # Specjalne przypadki - modele dedykowane
    if skrot == "PAT":
        return f"/admin/bpp/patent/?charakter_formalny__id__exact={charakter_id}"
    elif skrot == "D":
        return (
            f"/admin/bpp/praca_doktorska/?charakter_formalny__id__exact={charakter_id}"
        )
    elif skrot == "H":
        return f"/admin/bpp/praca_habilitacyjna/?charakter_formalny__id__exact={charakter_id}"

    # Dla pozostałych - wybierz model z większą liczbą rekordów
    if ciagle_count >= zwarte_count:
        return f"/admin/bpp/wydawnictwo_ciagle/?charakter_formalny__id__exact={charakter_id}"
    else:
        return f"/admin/bpp/wydawnictwo_zwarte/?charakter_formalny__id__exact={charakter_id}"


def _get_charakter_counts():
    """
    Helper function to get charakter formalny counts from database.
    Returns list of tuples: (nazwa, count, skrot, id, ciagle_count, zwarte_count)

    Optimized version using Django ORM with conditional aggregation.
    Queries from Charakter_Formalny and counts related publications in single query.
    """
    # Query from Charakter_Formalny and count related publications
    results = (
        Charakter_Formalny.objects.annotate(
            ciagle_count=Count("wydawnictwo_ciagle"),
            zwarte_count=Count("wydawnictwo_zwarte"),
        )
        .annotate(total_count=F("ciagle_count") + F("zwarte_count"))
        .filter(total_count__gt=0)
        .values("nazwa", "skrot", "id", "ciagle_count", "zwarte_count", "total_count")
        .order_by("-total_count")
    )

    # Convert to list of tuples matching the expected format
    # (nazwa, total_count, skrot, id, ciagle_count, zwarte_count)
    return [
        (
            row["nazwa"],
            row["total_count"],
            row["skrot"],
            row["id"],
            row["ciagle_count"],
            row["zwarte_count"],
        )
        for row in results
    ]


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def charakter_formalny_stats_top90(request):
    """JSON endpoint - Donut chart z charakterami stanowiącymi kumulatywnie 90% publikacji"""
    sorted_chars = _get_charakter_counts()

    # Oblicz total i znajdź charaktery stanowiące kumulatywnie 90%
    total = sum(char[1] for char in sorted_chars)
    threshold = total * 0.9
    cumulative = 0
    top_chars = []

    for char in sorted_chars:
        if cumulative < threshold:
            top_chars.append(char)
            cumulative += char[1]
        else:
            break

    # Pozostałe jako "Inne"
    rest_chars = sorted_chars[len(top_chars) :]

    labels = [char[0] for char in top_chars]
    values = [char[1] for char in top_chars]
    # Generuj URL dla każdego charakteru: (nazwa, count, skrot, id, ciagle_count, zwarte_count)
    customdata = [
        _get_admin_url_for_charakter(char[2], char[3], char[4], char[5])
        for char in top_chars
    ]

    if rest_chars:
        rest_count = sum(char[1] for char in rest_chars)
        labels.append("Inne")
        values.append(rest_count)
        customdata.append(None)  # Brak URL dla "Inne"

    data = [
        {
            "labels": labels,
            "values": values,
            "type": "pie",
            "hole": 0.4,
            "textinfo": "label+percent",
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: "
            "%{percent}<extra></extra>",
            "customdata": customdata,
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Charaktery formalne - Top 90%",
                "height": 500,
                "showlegend": False,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def charakter_formalny_stats_remaining10(request):
    """JSON endpoint - Donut chart z pozostałymi 10%, podzielonymi na 90% + 10%"""
    sorted_chars = _get_charakter_counts()

    # Oblicz total i znajdź charaktery stanowiące kumulatywnie 90%
    total = sum(char[1] for char in sorted_chars)
    threshold = total * 0.9
    cumulative = 0
    skip_count = 0

    for char in sorted_chars:
        if cumulative < threshold:
            cumulative += char[1]
            skip_count += 1
        else:
            break

    # Pozostałe 10%
    rest_chars = sorted_chars[skip_count:]

    if not rest_chars:
        # Jeśli nie ma danych dla pozostałych 10%, zwróć pusty wykres
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Charaktery formalne - Pozostałe 10%",
                    "height": 500,
                    "showlegend": False,
                    "annotations": [
                        {
                            "text": "Brak danych",
                            "x": 0.5,
                            "y": 0.5,
                            "showarrow": False,
                            "font": {"size": 20},
                        }
                    ],
                },
            }
        )

    # Z pozostałych 10%, weź kumulatywnie 90%
    rest_total = sum(char[1] for char in rest_chars)
    rest_threshold = rest_total * 0.9
    rest_cumulative = 0
    top_rest_chars = []

    for char in rest_chars:
        if rest_cumulative < rest_threshold:
            top_rest_chars.append(char)
            rest_cumulative += char[1]
        else:
            break

    # Pozostałe z pozostałych (1% całości)
    final_rest_chars = rest_chars[len(top_rest_chars) :]

    labels = [char[0] for char in top_rest_chars]
    values = [char[1] for char in top_rest_chars]
    # Generuj URL dla każdego charakteru
    customdata = [
        _get_admin_url_for_charakter(char[2], char[3], char[4], char[5])
        for char in top_rest_chars
    ]

    if final_rest_chars:
        final_rest_count = sum(char[1] for char in final_rest_chars)
        labels.append("Inne")
        values.append(final_rest_count)
        customdata.append(None)  # Brak URL dla "Inne"

    data = [
        {
            "labels": labels,
            "values": values,
            "type": "pie",
            "hole": 0.4,
            "textinfo": "label+percent",
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: "
            "%{percent}<extra></extra>",
            "customdata": customdata,
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Charaktery formalne - Pozostałe 10%",
                "height": 500,
                "showlegend": False,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def charakter_formalny_stats_remaining1(request):
    """JSON endpoint - Donut chart z ostatnim 1% (10% z 10%)"""
    sorted_chars = _get_charakter_counts()

    # Oblicz total i znajdź charaktery stanowiące kumulatywnie 90%
    total = sum(char[1] for char in sorted_chars)
    threshold = total * 0.9
    cumulative = 0
    skip_count = 0

    for char in sorted_chars:
        if cumulative < threshold:
            cumulative += char[1]
            skip_count += 1
        else:
            break

    # Pozostałe 10%
    rest_chars = sorted_chars[skip_count:]

    if not rest_chars:
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Charaktery formalne - Ostatni 1%",
                    "height": 500,
                    "showlegend": False,
                    "annotations": [
                        {
                            "text": "Brak danych",
                            "x": 0.5,
                            "y": 0.5,
                            "showarrow": False,
                            "font": {"size": 20},
                        }
                    ],
                },
            }
        )

    # Z pozostałych 10%, znajdź kumulatywnie 90%
    rest_total = sum(char[1] for char in rest_chars)
    rest_threshold = rest_total * 0.9
    rest_cumulative = 0
    skip_rest_count = 0

    for char in rest_chars:
        if rest_cumulative < rest_threshold:
            rest_cumulative += char[1]
            skip_rest_count += 1
        else:
            break

    # Ostatni 1% całości (10% z 10%)
    final_chars = rest_chars[skip_rest_count:]

    if not final_chars:
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Charaktery formalne - Ostatni 1%",
                    "height": 500,
                    "showlegend": False,
                    "annotations": [
                        {
                            "text": "Brak danych",
                            "x": 0.5,
                            "y": 0.5,
                            "showarrow": False,
                            "font": {"size": 20},
                        }
                    ],
                },
            }
        )

    labels = [char[0] for char in final_chars]
    values = [char[1] for char in final_chars]
    # Generuj URL dla każdego charakteru
    customdata = [
        _get_admin_url_for_charakter(char[2], char[3], char[4], char[5])
        for char in final_chars
    ]

    data = [
        {
            "labels": labels,
            "values": values,
            "type": "pie",
            "hole": 0.4,
            "textinfo": "label+percent",
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: "
            "%{percent}<extra></extra>",
            "customdata": customdata,
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Charaktery formalne - Ostatni 1%",
                "height": 500,
                "showlegend": False,
            },
        }
    )
