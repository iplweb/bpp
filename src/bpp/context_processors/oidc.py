from django.conf import settings


def oidc_auth_status(request):
    """Udostępnia szablonom status logowania OIDC (bez ruchu sieciowego).

    ``oidc_login_enabled`` jest **per-uczelnia**: w instalacji wielouczelnianej
    OIDC to jeden realm na proces, więc przycisk pokazujemy tylko na domenie
    uczelni o skrócie == ``OIDC_LOGIN_SKROT`` (patrz
    ``oidc_integration.access.oidc_enabled_for_request``). Gdy OIDC jest w
    procesie wyłączone, krótkie spięcie bez importu apki.
    """
    if not getattr(settings, "OIDC_LOGIN_ENABLED", False):
        return {"oidc_login_enabled": False, "oidc_login_skrot": ""}

    from oidc_integration.access import oidc_enabled_for_request

    return {
        "oidc_login_enabled": oidc_enabled_for_request(request),
        "oidc_login_skrot": getattr(settings, "OIDC_LOGIN_SKROT", ""),
    }
