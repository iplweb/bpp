from django.conf import settings


def _pop_oidc_error(request):
    """Wyjmij (flash-once) komunikat odmowy OIDC z sesji, jeśli jest.

    Backend (``BppOIDCBackend._fail``) zapisuje powód fail-closed do
    ``session["oidc_error_message"]`` tuż przed ``SuspiciousOperation``
    (którą ``mozilla_django_oidc`` degraduje do cichego login failure).
    Tu go POP-ujemy, żeby strona logowania pokazała go RAZ i nie wisiał
    w sesji przy kolejnych odsłonach. ``SessionBase.pop`` sam ustawia
    ``modified``, gdy klucz istniał.
    """
    session = getattr(request, "session", None)
    if session is None:
        return None
    return session.pop("oidc_error_message", None)


def oidc_auth_status(request):
    """Udostępnia szablonom status logowania OIDC (bez ruchu sieciowego).

    ``oidc_login_enabled`` jest **per-uczelnia**: w instalacji wielouczelnianej
    OIDC to jeden realm na proces, więc przycisk pokazujemy tylko na domenie
    uczelni o skrócie == ``OIDC_LOGIN_SKROT`` (patrz
    ``oidc_integration.access.oidc_enabled_for_request``). Gdy OIDC jest w
    procesie wyłączone, krótkie spięcie bez importu apki.

    ``oidc_error_message`` (flash-once) pokazuje na stronie logowania powód
    odmowy fail-closed — POP-ujemy go zawsze, także gdy przycisk OIDC jest w
    tym procesie wyłączony (komunikat mógł zostać zapisany, zanim sesja
    trafiła na tę odsłonę).
    """
    oidc_error_message = _pop_oidc_error(request)

    if not getattr(settings, "OIDC_LOGIN_ENABLED", False):
        return {
            "oidc_login_enabled": False,
            "oidc_login_skrot": "",
            "oidc_error_message": oidc_error_message,
        }

    from oidc_integration.access import oidc_enabled_for_request

    return {
        "oidc_login_enabled": oidc_enabled_for_request(request),
        "oidc_login_skrot": getattr(settings, "OIDC_LOGIN_SKROT", ""),
        "oidc_error_message": oidc_error_message,
    }
