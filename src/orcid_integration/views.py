import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from bpp.models import Uczelnia

from .client import OrcidClient
from .models import ORCIDIdentity

logger = logging.getLogger(__name__)


def _clear_orcid_link_session(request):
    """Usuń flagi trybu linkowania z sesji (po zakończeniu lub porzuceniu)."""
    request.session.pop("orcid_link_mode", None)
    request.session.pop("orcid_link_target", None)
    request.session.save()


class ORCIDLinkInitView(LoginRequiredMixin, View):
    """Start wiązania konta z tożsamością ORCID — wymaga re-auth hasłem.

    Konto bez używalnego hasła (LDAP/OIDC) nie może linkować tą drogą —
    świadoma decyzja. Po poprawnym re-auth ustawiamy w sesji tryb linkowania
    i odbijamy na standardowy start ORCID; ``orcid_callback`` wychwytuje tryb
    i wiąże ``(issuer, ORCID iD)`` z tym kontem zamiast logować.
    """

    template_name = "orcid_integration/polacz.html"

    @staticmethod
    def _clear_stale_link_flags(request):
        """Usuń pozostałości po przerwanym wcześniej linkowaniu (GET i POST),
        żeby następne *zwykłe* logowanie ORCID nie zostało błędnie potraktowane
        jako linkowanie."""
        _clear_orcid_link_session(request)

    def get(self, request):
        self._clear_stale_link_flags(request)
        return render(request, self.template_name, {})

    def post(self, request):
        self._clear_stale_link_flags(request)
        user = request.user
        password = request.POST.get("password", "")
        if not user.has_usable_password() or not user.check_password(password):
            return render(
                request,
                self.template_name,
                {"error": "Nieprawidłowe hasło lub konto bez hasła lokalnego."},
            )
        request.session["orcid_link_mode"] = True
        request.session["orcid_link_target"] = user.pk
        request.session.save()
        return redirect(reverse("orcid_integration:login"))


def _handle_link_callback(request, uczelnia, orcid_id):
    """W trybie link zwiąż ``(issuer, ORCID iD)`` z zalogowanym kontem.

    Guardy (jak w OIDC): cel linkowania musi być bieżącym userem; istniejąca
    tożsamość należąca do innego konta NIE jest przejmowana; ``IntegrityError``
    (konto ma już tożsamość z tego środowiska) → komunikat, bez zmiany.
    ``finally`` zawsze czyści flagi trybu link.
    """
    try:
        user = request.user
        target_pk = request.session.get("orcid_link_target")
        if not user.is_authenticated or not target_pk or user.pk != target_pk:
            messages.error(request, "Cel linkowania ORCID niezgodny z kontem.")
            return redirect(reverse("bpp:profil-uzytkownika"))

        issuer = uczelnia.orcid_base_url
        try:
            with transaction.atomic():
                identity, created = ORCIDIdentity.objects.get_or_create(
                    issuer=issuer, sub=orcid_id, defaults={"user": user}
                )
        except IntegrityError:
            messages.error(
                request,
                "To konto ma już powiązaną tożsamość ORCID z tego środowiska.",
            )
            return redirect(reverse("bpp:profil-uzytkownika"))

        if not created and identity.user_id != user.pk:
            messages.error(
                request,
                "Ta tożsamość ORCID jest już powiązana z innym kontem.",
            )
            return redirect(reverse("bpp:profil-uzytkownika"))

        messages.success(request, f"Konto zostało powiązane z ORCID {orcid_id}.")
        return redirect(reverse("bpp:profil-uzytkownika"))
    finally:
        _clear_orcid_link_session(request)


def _safe_next_url(next_url, request):
    """Return *next_url* only when it points to our own host."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return "/"


def _get_orcid_client(request):
    """Return ``(uczelnia, OrcidClient)`` or raise Http404.

    Uczelnia z requestu (multi-hosted): credentiale ORCID są per-uczelnia,
    więc NIE wolno zgadywać ``get_default()`` — inaczej w instalacji
    wielouczelnianej logowalibyśmy do konta ORCID złej uczelni.
    """
    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None or not uczelnia.orcid_enabled:
        raise Http404

    redirect_uri = request.build_absolute_uri(reverse("orcid_integration:callback"))
    client = OrcidClient(
        client_id=uczelnia.orcid_client_id,
        client_secret=uczelnia.orcid_client_secret,
        base_url=uczelnia.orcid_base_url,
        redirect_uri=redirect_uri,
    )
    return uczelnia, client


def orcid_login(request):
    """Initiate the ORCID OAuth 2.0 authorization flow."""
    _uczelnia, client = _get_orcid_client(request)
    url, state = client.get_authorization_url()

    request.session["orcid_oauth_state"] = state
    next_url = _safe_next_url(request.GET.get("next", "/"), request)
    request.session["orcid_next"] = next_url

    return redirect(url)


def orcid_callback(request):
    """Handle the ORCID OAuth 2.0 callback."""
    saved_state = request.session.pop("orcid_oauth_state", None)
    received_state = request.GET.get("state")

    if not saved_state or saved_state != received_state:
        return HttpResponseBadRequest("Nieprawidłowy parametr state.")

    error = request.GET.get("error")
    if error:
        logger.warning("ORCID callback error: %s", error)
        return render(
            request,
            "orcid_integration/error.html",
            {"message": f"ORCID zwrócił błąd: {error}"},
        )

    _uczelnia, client = _get_orcid_client(request)

    try:
        token = client.fetch_token(request.build_absolute_uri())
    except Exception:
        logger.exception("ORCID token exchange failed")
        return render(
            request,
            "orcid_integration/error.html",
            {"message": "Nie udało się uzyskać tokenu z ORCID."},
        )

    orcid_id = token.get("orcid")
    if not orcid_id:
        return render(
            request,
            "orcid_integration/error.html",
            {"message": "Odpowiedź z ORCID nie zawiera identyfikatora ORCID."},
        )

    # Tryb linkowania (re-auth hasłem w ORCIDLinkInitView) — wiąż tożsamość
    # z zalogowanym kontem zamiast logować/dopasowywać.
    if request.session.get("orcid_link_mode"):
        return _handle_link_callback(request, _uczelnia, orcid_id)

    # Pass username for django-easy-audit compatibility (its
    # user_login_failed signal handler expects credentials["username"]).
    user = authenticate(
        request,
        orcid_id=orcid_id,
        orcid_issuer=_uczelnia.orcid_base_url,
        username=orcid_id,
    )
    if user is None:
        return render(
            request,
            "orcid_integration/error.html",
            {
                "message": f"Nie znaleziono konta powiązanego "
                f"z ORCID {orcid_id}. Aby logować się przez ORCID, "
                f"najpierw powiąż swój identyfikator ORCID z kontem "
                f"na stronie „Mój profil” (wymaga zalogowania hasłem)."
            },
        )

    login(
        request,
        user,
        backend="orcid_integration.backends.OrcidAuthenticationBackend",
    )

    next_url = _safe_next_url(request.session.pop("orcid_next", "/"), request)
    return redirect(next_url)
