from django.conf import settings

from django_bpp.freshdesk import WIDGET_SCRIPT_URL, jwt_enabled


def freshdesk_widget(request):
    """Konfiguracja widgetu wsparcia Freshdesk dla bieżącego użytkownika.

    Zalogowani dostają widget ``FRESHDESK_WIDGET_ID`` (z uwierzytelnieniem JWT,
    jeżeli skonfigurowano sekret), anonimowi — osobny widget
    ``FRESHDESK_WIDGET_ID_ANON``. Pusty ID = brak widgetu (``None``).
    Zalogowany przy JWT dostaje też dane widgetu anonimowego — ładuje się on,
    gdy tokenu nie da się uzyskać (np. konto bez e-maila).
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

    jwt = authenticated and jwt_enabled()
    anon_id = settings.FRESHDESK_WIDGET_ID_ANON if jwt else ""

    return {
        "FRESHDESK_WIDGET": {
            "widget_id": widget_id,
            "script_url": WIDGET_SCRIPT_URL.format(widget_id),
            "authenticated": authenticated,
            "jwt": jwt,
            "anon_widget_id": anon_id or None,
            "anon_script_url": WIDGET_SCRIPT_URL.format(anon_id) if anon_id else None,
        }
    }
