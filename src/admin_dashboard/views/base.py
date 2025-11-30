"""Base views for admin dashboard."""

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone

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
