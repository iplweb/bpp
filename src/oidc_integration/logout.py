"""Budowanie URL-a wylogowania z serwera OIDC (Keycloak end_session).

RP-Initiated Logout: po lokalnym wylogowaniu Django przekierowujemy usera na
``end_session_endpoint`` Keycloaka z ``id_token_hint`` (z sesji) i
``post_logout_redirect_uri``. Dzięki temu wylogowanie z BPP kończy też sesję
SSO w Keycloaku — inaczej kolejne „Zaloguj przez UAFM" logowałoby bez pytania
o hasło (cicha re-autoryzacja z żywej sesji KC).
"""

from urllib.parse import urlencode

from django.conf import settings


def build_provider_logout_url(request):
    """Zwróć URL wylogowania z OP albo lokalny redirect (gdy brak end_session).

    Czyta ``oidc_id_token`` z sesji — MUSI być wywołane PRZED ``auth.logout``
    (który czyści sesję). ``OIDC_STORE_ID_TOKEN=True`` zapewnia obecność tokenu.
    """
    fallback = getattr(settings, "LOGOUT_REDIRECT_URL", None) or "/"
    end_session = getattr(settings, "OIDC_OP_LOGOUT_ENDPOINT", "")
    if not end_session:
        return fallback

    params = {"post_logout_redirect_uri": request.build_absolute_uri(fallback)}
    id_token = request.session.get("oidc_id_token")
    if id_token:
        params["id_token_hint"] = id_token

    return f"{end_session}?{urlencode(params)}"
