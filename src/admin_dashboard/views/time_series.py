"""Time series statistics views for admin dashboard."""

from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import cache_page

from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
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
