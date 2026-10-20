from django.conf import settings

from django_bpp.freshdesk import WIDGET_SCRIPT_URL, jwt_enabled


def freshdesk_widget(request):
    """Konfiguracja widgetu wsparcia Freshdesk dla bieżącego użytkownika.

    Zalogowani dostają widget ``FRESHDESK_WIDGET_ID`` (z uwierzytelnieniem JWT,
    jeżeli skonfigurowano sekret), anonimowi — osobny widget
    ``FRESHDESK_WIDGET_ID_ANON``. Pusty ID = brak widgetu (``None``).
    Sam sekret nigdy nie trafia do kontekstu szablonu.
    """
    user = getattr(request, "user", None)
    authenticated = bool(user is not None and user.is_authenticated)

    if authenticated:
        widget_id = settings.FRESHDESK_WIDGET_ID
    else:
        widget_id = settings.FRESHDESK_WIDGET_ID_ANON

    if not widget_id:
        return {"FRESHDESK_WIDGET": None}

    return {
        "FRESHDESK_WIDGET": {
            "widget_id": widget_id,
            "script_url": WIDGET_SCRIPT_URL.format(widget_id),
            "authenticated": authenticated,
            "jwt": authenticated and jwt_enabled(),
        }
    }
