"""Widoki OIDC dla BPP — backend-aware wylogowanie oraz linkowanie konta."""

from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from oidc_integration.logout import build_provider_logout_url

OIDC_BACKEND_PATH = "oidc_integration.backends.BppOIDCBackend"


class SSOLinkInitView(LoginRequiredMixin, View):
    """Start linkowania konta z SSO — wymaga potwierdzenia hasła (re-auth).

    Konto bez używalnego hasła (LDAP/Microsoft/OIDC) nie może linkować tą
    drogą — świadoma decyzja. Po poprawnym re-auth ustawiamy w sesji tryb
    linkowania i odbijamy na standardowy start OIDC; backend
    ``get_or_create_user`` wychwytuje tryb i wiąże ``(issuer, sub)`` z tym
    kontem zamiast tworzyć/dopasowywać nowe.
    """

    template_name = "oidc_integration/polacz.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        user = request.user
        password = request.POST.get("password", "")
        if not user.has_usable_password() or not user.check_password(password):
            return render(
                request,
                self.template_name,
                {"error": "Nieprawidłowe hasło lub konto bez hasła lokalnego."},
            )
        request.session["oidc_link_mode"] = True
        request.session["oidc_link_target"] = user.pk
        request.session.save()
        return redirect(reverse("oidc_authentication_init"))


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
