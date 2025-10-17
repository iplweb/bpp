from django.contrib import admin
from django.utils.html import format_html

from .models import SiteCountdown


@admin.register(SiteCountdown)
class SiteCountdownAdmin(admin.ModelAdmin):
    list_display = [
        "site",
        "message",
        "countdown_time",
        "maintenance_until",
        "is_expired",
        "time_remaining_display",
        "created_at",
    ]
    list_filter = ["site", "countdown_time"]
    search_fields = ["message", "long_description"]
    readonly_fields = ["created_at", "updated_at", "time_remaining_display"]

    fieldsets = [
        (
            "Podstawowe informacje",
            {
                "fields": ["site", "countdown_time", "maintenance_until"],
            },
        ),
        (
            "Komunikaty",
            {
                "fields": ["message", "long_description"],
            },
        ),
        (
            "Metadane",
            {
                "fields": ["created_at", "updated_at", "time_remaining_display"],
                "classes": ["collapse"],
            },
        ),
    ]

    def time_remaining_display(self, obj):
        """Wyświetla pozostały czas w czytelnym formacie z kolorowym wskaźnikiem."""
        if obj.countdown_time is None:
            return format_html(
                '<span style="color: gray; font-weight: bold;">Nie ustawiono</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="color: red; font-weight: bold;">Wygasło</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                obj.time_remaining(),
            )

    time_remaining_display.short_description = "Pozostały czas"
