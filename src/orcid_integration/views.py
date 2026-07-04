import logging

from django.contrib.auth import authenticate, login
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from bpp.models import Uczelnia

from .client import OrcidClient

logger = logging.getLogger(__name__)


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

    # Pass username for django-easy-audit compatibility (its
    # user_login_failed signal handler expects credentials["username"]).
    user = authenticate(request, orcid_id=orcid_id, username=orcid_id)
    if user is None:
        return render(
            request,
            "orcid_integration/error.html",
            {
                "message": f"Nie znaleziono konta powiązanego "
                f"z ORCID {orcid_id}. Upewnij się, że Twój "
                f"identyfikator ORCID jest wpisany w profilu "
                f"autora w systemie BPP, a adres e-mail autora "
                f"odpowiada adresowi konta użytkownika."
            },
        )

    login(
        request,
        user,
        backend="orcid_integration.backends.OrcidAuthenticationBackend",
    )

    next_url = _safe_next_url(request.session.pop("orcid_next", "/"), request)
    return redirect(next_url)
