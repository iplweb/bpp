from django.conf import settings


def oidc_auth_status(request):
    """Udostępnia szablonom status logowania OIDC (bez ruchu sieciowego).

    Flagi ustawia ``settings/base.py`` tylko gdy konfiguracja OIDC jest
    obecna w środowisku; w przeciwnym razie zwracamy wartości domyślne
    (wyłączone), jak robią to context processory ORCID/Microsoft.
    """
    return {
        "oidc_login_enabled": getattr(settings, "OIDC_LOGIN_ENABLED", False),
        "oidc_login_skrot": getattr(settings, "OIDC_LOGIN_SKROT", ""),
    }
