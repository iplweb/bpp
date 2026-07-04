"""Widoki OIDC dla BPP — na razie tylko backend-aware wylogowanie."""

from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LogoutView
from django.http import HttpResponseRedirect

from oidc_integration.logout import build_provider_logout_url

OIDC_BACKEND_PATH = "oidc_integration.backends.BppOIDCBackend"


class BppOIDCAwareLogoutView(LogoutView):
    """Wylogowanie świadome backendu logowania.

    Sesja zalogowana przez OIDC → wyloguj też z Keycloaka (RP-Initiated
    Logout). Każda inna sesja (hasło, ORCID) → standardowe wylogowanie Django.
    Bezpieczny nadzbiór ``LogoutView`` — gdy OIDC nieużyte, zachowuje się
    identycznie jak oryginał.
    """

    def post(self, request, *args, **kwargs):
        is_oidc_session = (
            request.user.is_authenticated
            and request.session.get(BACKEND_SESSION_KEY) == OIDC_BACKEND_PATH
        )
        if is_oidc_session:
            # URL musi powstać PRZED auth_logout (czyta id_token z sesji).
            logout_url = build_provider_logout_url(request)
            auth_logout(request)
            return HttpResponseRedirect(logout_url)

        return super().post(request, *args, **kwargs)
