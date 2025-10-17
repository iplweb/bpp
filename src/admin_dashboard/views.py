from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

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
    }

    # Przygotowanie danych dla dni Pon-Czw
    weekdays_dict = {entry["weekday"]: entry["count"] for entry in weekday_data}

    # Tylko Pon-Czw
    days_order = [2, 3, 4, 5]
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
def new_publications_stats(request):
    """JSON endpoint dla nowo dodanych prac - trend w czasie (ostatnie 12 miesięcy)"""

    # Ostatnie 12 miesięcy
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
            "mode": "lines+markers",
        },
        {
            "x": all_months,
            "y": [months_zwarte.get(month, 0) for month in all_months],
            "name": "Wydawnictwa zwarte",
            "type": "scatter",
            "mode": "lines+markers",
        },
    ]

    return JsonResponse(
        {
            "data": data,
            "layout": {
                "title": "Nowo dodane prace (ostatnie 12 miesięcy)",
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
