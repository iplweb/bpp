from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.cache import cache_page

from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

User = get_user_model()


@staff_member_required
def recent_logins_view(request):
    """HTMX endpoint dla ostatnich logowań"""
    user = request.user
    limit = 10
    from easyaudit.models import LoginEvent

    if user.is_superuser:
        # Superuserzy widzą wszystkich - tylko udane logowania
        logins = (
            LoginEvent.objects.filter(login_type=LoginEvent.LOGIN)
            .select_related("user")
            .all()[:limit]
        )
    else:
        # Zwykli użytkownicy widzą tylko swoje - tylko udane logowania
        logins = LoginEvent.objects.filter(user=user, login_type=LoginEvent.LOGIN)[
            :limit
        ]

    return TemplateResponse(
        request,
        "admin_dashboard/partials/recent_logins.html",
        {"logins": logins, "is_superuser": user.is_superuser},
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def weekday_stats(request):
    """JSON endpoint dla statystyk edycji według dni tygodnia (ostatni miesiąc, Pon-Czw)"""
    from django.db.models.functions import ExtractWeekDay

    # Ostatni miesiąc
    one_month_ago = timezone.now() - timedelta(days=30)

    # Agregacja według dnia tygodnia dla LogEntry (wszystkie edycje)
    weekday_data = (
        LogEntry.objects.filter(action_time__gte=one_month_ago)
        .annotate(weekday=ExtractWeekDay("action_time"))
        .values("weekday")
        .annotate(count=Count("id"))
        .order_by("weekday")
    )

    # Mapowanie numerów dni na nazwy (PostgreSQL: 1=Niedziela, 2=Pon, ..., 7=Sobota)
    weekday_names = {
        2: "Poniedziałek",
        3: "Wtorek",
        4: "Środa",
        5: "Czwartek",
        6: "Piątek",
    }

    # Przygotowanie danych dla dni Pon-Pt
    weekdays_dict = {entry["weekday"]: entry["count"] for entry in weekday_data}

    # Tylko Pon-Pt
    days_order = [2, 3, 4, 5, 6]
    x_labels = [weekday_names[day] for day in days_order]
    y_values = [weekdays_dict.get(day, 0) for day in days_order]

    data = [
        {
            "x": x_labels,
            "y": y_values,
            "type": "bar",
            "name": "Edycje",
            "marker": {"color": "#417690"},
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Edycje w dni tygodnia (ostatni miesiąc)",
                "xaxis": {"title": "Dzień tygodnia"},
                "yaxis": {"title": "Liczba edycji"},
                "legend": {
                    "orientation": "h",
                    "y": -0.2,
                    "x": 0.5,
                    "xanchor": "center",
                },
                "height": 500,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def day_of_month_activity_stats(request):
    """
    JSON endpoint dla aktywności w dniach miesiąca (ostatnie 6 miesięcy).
    Pokazuje prace dodane LUB wyedytowane w kolejnych dniach miesiąca (1-31).
    """
    from django.db.models.functions import ExtractDay

    # Ostatnie 6 miesięcy
    six_months_ago = timezone.now() - timedelta(days=6 * 30)

    # Agregacja według dnia miesiąca dla LogEntry (wszystkie operacje: dodanie + edycja)
    day_of_month_data = (
        LogEntry.objects.filter(action_time__gte=six_months_ago)
        .annotate(day=ExtractDay("action_time"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Przygotowanie danych - dni od 1 do 31
    days_dict = {entry["day"]: entry["count"] for entry in day_of_month_data}
    days = list(range(1, 32))
    counts = [days_dict.get(day, 0) for day in days]

    data = [
        {
            "x": days,
            "y": counts,
            "type": "bar",
            "name": "Operacje na publikacjach",
            "marker": {"color": "#d9831f"},
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Aktywność w dniach miesiąca<br>(ostatnie 6 miesięcy)",
                "xaxis": {"title": "Dzień miesiąca"},
                "yaxis": {"title": "Liczba operacji (dodane + wyedytowane)"},
                "legend": {
                    "orientation": "h",
                    "y": -0.2,
                    "x": 0.5,
                    "xanchor": "center",
                },
                "height": 500,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def new_publications_stats(request):
    """JSON endpoint dla nowo dodanych prac - trend w czasie (ostatnie 5 lat)"""

    # Ostatnie 5 lat (60 miesięcy)
    twelve_months_ago = timezone.now() - timedelta(days=365 * 5)

    monthly_trend_ciagle = []
    monthly_trend_zwarte = []

    if hasattr(Wydawnictwo_Ciagle, "utworzono"):
        monthly_trend_ciagle = (
            Wydawnictwo_Ciagle.objects.filter(utworzono__gte=twelve_months_ago)
            .annotate(month=TruncMonth("utworzono"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

    if hasattr(Wydawnictwo_Zwarte, "utworzono"):
        monthly_trend_zwarte = (
            Wydawnictwo_Zwarte.objects.filter(utworzono__gte=twelve_months_ago)
            .annotate(month=TruncMonth("utworzono"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

    # Przygotowanie danych
    months_ciagle = {
        entry["month"].isoformat(): entry["count"] for entry in monthly_trend_ciagle
    }
    months_zwarte = {
        entry["month"].isoformat(): entry["count"] for entry in monthly_trend_zwarte
    }

    all_months = sorted(set(list(months_ciagle.keys()) + list(months_zwarte.keys())))

    data = [
        {
            "x": all_months,
            "y": [months_ciagle.get(month, 0) for month in all_months],
            "name": "Wydawnictwa ciągłe",
            "type": "scatter",
            "mode": "lines",
            "line": {"shape": "spline", "smoothing": 1.3},
        },
        {
            "x": all_months,
            "y": [months_zwarte.get(month, 0) for month in all_months],
            "name": "Wydawnictwa zwarte",
            "type": "scatter",
            "mode": "lines",
            "line": {"shape": "spline", "smoothing": 1.3},
        },
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Nowo dodane prace (ostatnie 5 lat)",
                "xaxis": {"title": "Miesiąc"},
                "yaxis": {"title": "Liczba nowych publikacji"},
                "legend": {
                    "orientation": "h",
                    "y": -0.2,
                    "x": 0.5,
                    "xanchor": "center",
                },
                "height": 500,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def cumulative_publications_stats(request):
    """JSON endpoint dla cumulative wykresu prac w bazie (od 1980)"""

    # Pobierz wszystkie prace z rokiem >= 1980
    publications_by_year = (
        Wydawnictwo_Ciagle.objects.filter(rok__gte=1980)
        .values("rok")
        .annotate(count=Count("id"))
        .order_by("rok")
    )

    publications_zwarte_by_year = (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=1980)
        .values("rok")
        .annotate(count=Count("id"))
        .order_by("rok")
    )

    # Połącz dane z obu typów publikacji
    years_ciagle = {entry["rok"]: entry["count"] for entry in publications_by_year}
    years_zwarte = {
        entry["rok"]: entry["count"] for entry in publications_zwarte_by_year
    }

    # Utwórz pełny zakres lat
    all_years = sorted(set(list(years_ciagle.keys()) + list(years_zwarte.keys())))

    if not all_years:
        # Brak danych
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Prace w bazie (cumulative)",
                    "xaxis": {"title": "Rok"},
                    "yaxis": {"title": "Łączna liczba prac"},
                    "height": 400,
                },
            }
        )

    # Oblicz cumulative sum
    cumulative_count = 0
    years_list = []
    cumulative_list = []

    for year in range(all_years[0], all_years[-1] + 1):
        count = years_ciagle.get(year, 0) + years_zwarte.get(year, 0)
        cumulative_count += count
        years_list.append(year)
        cumulative_list.append(cumulative_count)

    data = [
        {
            "x": years_list,
            "y": cumulative_list,
            "type": "scatter",
            "mode": "lines",
            "name": "Cumulative",
            "line": {"color": "#417690", "width": 2},
            "fill": "tozeroy",
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Prace w bazie (cumulative)",
                "xaxis": {"title": "Rok"},
                "yaxis": {"title": "Łączna liczba prac"},
                "height": 400,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def cumulative_impact_factor_stats(request):
    """JSON endpoint dla łącznego impact factor (od 2010)"""
    from django.db.models import Sum

    # Pobierz sumę impact factor po latach dla ciągłych
    if_by_year_ciagle = (
        Wydawnictwo_Ciagle.objects.filter(rok__gte=2010, impact_factor__isnull=False)
        .values("rok")
        .annotate(total_if=Sum("impact_factor"))
        .order_by("rok")
    )

    if_by_year_zwarte = (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=2010, impact_factor__isnull=False)
        .values("rok")
        .annotate(total_if=Sum("impact_factor"))
        .order_by("rok")
    )

    # Połącz dane
    years_ciagle = {
        entry["rok"]: float(entry["total_if"]) for entry in if_by_year_ciagle
    }
    years_zwarte = {
        entry["rok"]: float(entry["total_if"]) for entry in if_by_year_zwarte
    }

    all_years = sorted(set(list(years_ciagle.keys()) + list(years_zwarte.keys())))

    if not all_years:
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Łączny Impact Factor",
                    "xaxis": {"title": "Rok"},
                    "yaxis": {"title": "Suma IF"},
                    "height": 400,
                },
            }
        )

    # Oblicz cumulative IF
    cumulative_if = 0
    years_list = []
    cumulative_list = []

    for year in range(all_years[0], all_years[-1] + 1):
        if_sum = years_ciagle.get(year, 0) + years_zwarte.get(year, 0)
        cumulative_if += if_sum
        years_list.append(year)
        cumulative_list.append(round(cumulative_if, 2))

    data = [
        {
            "x": years_list,
            "y": cumulative_list,
            "type": "scatter",
            "mode": "lines",
            "name": "Impact Factor",
            "line": {"color": "#d9831f", "width": 2},
            "fill": "tozeroy",
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Łączny Impact Factor",
                "xaxis": {"title": "Rok"},
                "yaxis": {"title": "Suma IF"},
                "height": 400,
            },
        }
    )


@staff_member_required
@cache_page(60 * 60 * 24)  # Cache for 24 hours
def cumulative_points_kbn_stats(request):
    """JSON endpoint dla łącznych punktów MNiSW (od 2010)"""
    from django.db.models import Sum

    # Pobierz sumę punktów KBN po latach
    points_by_year_ciagle = (
        Wydawnictwo_Ciagle.objects.filter(rok__gte=2010, punkty_kbn__isnull=False)
        .values("rok")
        .annotate(total_points=Sum("punkty_kbn"))
        .order_by("rok")
    )

    points_by_year_zwarte = (
        Wydawnictwo_Zwarte.objects.filter(rok__gte=2010, punkty_kbn__isnull=False)
        .values("rok")
        .annotate(total_points=Sum("punkty_kbn"))
        .order_by("rok")
    )

    # Połącz dane
    years_ciagle = {
        entry["rok"]: float(entry["total_points"]) for entry in points_by_year_ciagle
    }
    years_zwarte = {
        entry["rok"]: float(entry["total_points"]) for entry in points_by_year_zwarte
    }

    all_years = sorted(set(list(years_ciagle.keys()) + list(years_zwarte.keys())))

    if not all_years:
        return JsonResponse(
            {
                "data": [],
                "layout": {
                    "title": "Łączne punkty MNiSW",
                    "xaxis": {"title": "Rok"},
                    "yaxis": {"title": "Suma punktów"},
                    "height": 400,
                },
            }
        )

    # Oblicz cumulative points
    cumulative_points = 0
    years_list = []
    cumulative_list = []

    for year in range(all_years[0], all_years[-1] + 1):
        points_sum = years_ciagle.get(year, 0) + years_zwarte.get(year, 0)
        cumulative_points += points_sum
        years_list.append(year)
        cumulative_list.append(round(cumulative_points, 2))

    data = [
        {
            "x": years_list,
            "y": cumulative_list,
            "type": "scatter",
            "mode": "lines",
            "name": "Punkty MNiSW",
            "line": {"color": "#9b59b6", "width": 2},
            "fill": "tozeroy",
        }
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Łączne punkty MNiSW",
                "xaxis": {"title": "Rok"},
                "yaxis": {"title": "Suma punktów"},
                "height": 400,
            },
        }
    )


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
        return f"/admin/bpp/patent/?charakter_formalny={charakter_id}"
    elif skrot == "D":
        return f"/admin/bpp/praca_doktorska/?charakter_formalny={charakter_id}"
    elif skrot == "H":
        return f"/admin/bpp/praca_habilitacyjna/?charakter_formalny={charakter_id}"

    # Dla pozostałych - wybierz model z większą liczbą rekordów
    if ciagle_count >= zwarte_count:
        return f"/admin/bpp/wydawnictwo_ciagle/?charakter_formalny={charakter_id}"
    else:
        return f"/admin/bpp/wydawnictwo_zwarte/?charakter_formalny={charakter_id}"


def _get_charakter_counts():
    """
    Helper function to get charakter formalny counts from database.
    Returns list of tuples: (nazwa, count, skrot, id, ciagle_count, zwarte_count)
    """
    # Agreguj dane z obu typów publikacji z dodatkowymi polami
    ciagle_by_char = (
        Wydawnictwo_Ciagle.objects.exclude(charakter_formalny__isnull=True)
        .values(
            "charakter_formalny__nazwa",
            "charakter_formalny__skrot",
            "charakter_formalny__id",
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    zwarte_by_char = (
        Wydawnictwo_Zwarte.objects.exclude(charakter_formalny__isnull=True)
        .values(
            "charakter_formalny__nazwa",
            "charakter_formalny__skrot",
            "charakter_formalny__id",
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Połącz dane z obu typów
    # Struktura: {id: {'nazwa': str, 'skrot': str, 'ciagle': int, 'zwarte': int}}
    char_data = {}

    for entry in ciagle_by_char:
        char_id = entry["charakter_formalny__id"]
        if char_id not in char_data:
            char_data[char_id] = {
                "nazwa": entry["charakter_formalny__nazwa"],
                "skrot": entry["charakter_formalny__skrot"],
                "ciagle": 0,
                "zwarte": 0,
            }
        char_data[char_id]["ciagle"] += entry["count"]

    for entry in zwarte_by_char:
        char_id = entry["charakter_formalny__id"]
        if char_id not in char_data:
            char_data[char_id] = {
                "nazwa": entry["charakter_formalny__nazwa"],
                "skrot": entry["charakter_formalny__skrot"],
                "ciagle": 0,
                "zwarte": 0,
            }
        char_data[char_id]["zwarte"] += entry["count"]

    # Konwertuj do listy tupli i posortuj według łącznej liczby
    result = [
        (
            data["nazwa"],
            data["ciagle"] + data["zwarte"],
            data["skrot"],
            char_id,
            data["ciagle"],
            data["zwarte"],
        )
        for char_id, data in char_data.items()
    ]

    return sorted(result, key=lambda x: x[1], reverse=True)


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
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: %{percent}<extra></extra>",
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
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: %{percent}<extra></extra>",
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
            "hovertemplate": "<b>%{label}</b><br>Liczba: %{value}<br>Udział: %{percent}<extra></extra>",
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


@staff_member_required
def database_stats(request):
    """JSON endpoint dla szczegółowych statystyk bazy danych"""

    # Statystyki jakościowe publikacji
    try:
        pass

        # Rozkład publikacji wg typu
        ciagle_by_type = (
            Wydawnictwo_Ciagle.objects.values("charakter_formalny__nazwa")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        zwarte_by_type = (
            Wydawnictwo_Zwarte.objects.values("charakter_formalny__nazwa")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        type_distribution = {
            "ciagle": list(ciagle_by_type),
            "zwarte": list(zwarte_by_type),
        }
    except Exception as e:
        type_distribution = {"error": str(e)}

    # Trend publikacji w czasie (ostatnie 12 miesięcy)
    twelve_months_ago = timezone.now() - timedelta(days=365)

    monthly_trend_ciagle = []
    monthly_trend_zwarte = []

    if hasattr(Wydawnictwo_Ciagle, "utworzono"):
        monthly_trend_ciagle = (
            Wydawnictwo_Ciagle.objects.filter(utworzono__gte=twelve_months_ago)
            .annotate(month=TruncMonth("utworzono"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

    if hasattr(Wydawnictwo_Zwarte, "utworzono"):
        monthly_trend_zwarte = (
            Wydawnictwo_Zwarte.objects.filter(utworzono__gte=twelve_months_ago)
            .annotate(month=TruncMonth("utworzono"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

    # Przygotowanie danych dla trendu czasowego
    trend_data = []
    if monthly_trend_ciagle or monthly_trend_zwarte:
        months_ciagle = {
            entry["month"].isoformat(): entry["count"] for entry in monthly_trend_ciagle
        }
        months_zwarte = {
            entry["month"].isoformat(): entry["count"] for entry in monthly_trend_zwarte
        }

        all_months = sorted(
            set(list(months_ciagle.keys()) + list(months_zwarte.keys()))
        )

        trend_data = [
            {
                "x": all_months,
                "y": [months_ciagle.get(month, 0) for month in all_months],
                "name": "Wydawnictwa ciągłe",
                "type": "scatter",
            },
            {
                "x": all_months,
                "y": [months_zwarte.get(month, 0) for month in all_months],
                "name": "Wydawnictwa zwarte",
                "type": "scatter",
            },
        ]

    return JsonResponse(
        {
            "type_distribution": type_distribution,
            "trend_data": trend_data,
            "trend_layout": {
                "title": "Trend publikacji (ostatnie 12 miesięcy)",
                "xaxis": {"title": "Miesiąc"},
                "yaxis": {"title": "Liczba publikacji"},
            },
        }
    )
