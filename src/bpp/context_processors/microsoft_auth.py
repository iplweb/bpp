from django.apps import apps
from django.conf import settings


def microsoft_auth_status(request):
    """
    Provides Microsoft authentication status to templates.
    This is a lightweight context processor that only checks configuration,
    without making any network requests.
    """
    microsoft_auth_enabled = apps.is_installed("microsoft_auth") and getattr(
        settings, "MICROSOFT_AUTH_CLIENT_ID", None
    )

    return {
        "microsoft_login_enabled": microsoft_auth_enabled,
    }
