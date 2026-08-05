from django.conf import settings


def rollbar_client(request):
    """Konfiguracja frontendowego Rollbara dla szablonu.

    Zwraca dane tylko gdy ustawiony jest publiczny token klienta
    (``post_client_item``). Bez tokenu — no-op (pusty kontekst), więc
    integracja jest domyślnie wyłączona. NIE dołącza danych użytkownika.
    """
    token = getattr(settings, "ROLLBAR_CLIENT_ACCESS_TOKEN", "")
    if not token:
        return {}
    return {
        "ROLLBAR_CLIENT": {
            "accessToken": token,
            "environment": settings.ROLLBAR.get("environment", "development"),
            "codeVersion": str(settings.ROLLBAR.get("code_version", "")),
        }
    }
