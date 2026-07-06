from django.contrib.auth import BACKEND_SESSION_KEY

from django_bpp.external_auth import EXTERNAL_AUTH_BACKENDS


def external_auth_status(request):
    """Czy bieżąca sesja zalogowała się backendem zarządzającym hasłem
    zewnętrznie (Microsoft / ORCID / OIDC-Keycloak).

    Decyzja jest **per-użytkownik** — wynika z backendu zapisanego w sesji przy
    logowaniu (``BACKEND_SESSION_KEY``), nie z globalnej konfiguracji procesu.
    Dzięki temu na tej samej instalacji superuser logujący się hasłem BPP nadal
    widzi „zmianę hasła", a osoba zalogowana przez Keycloaka — nie (jej hasło
    jest po stronie dostawcy tożsamości, więc ``/password_change/`` nie ma dla
    niej sensu i kończyło się błędem).
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"logged_in_via_external_auth": False}

    backend = request.session.get(BACKEND_SESSION_KEY, "")
    return {"logged_in_via_external_auth": backend in EXTERNAL_AUTH_BACKENDS}
