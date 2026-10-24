# Create your views here.
import base64
import json
import secrets
import sys

import rollbar
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import RedirectView
from pbn_client.conf import settings as pbn_defaults

from bpp.models import Uczelnia

from .client import OAuthMixin
from .exceptions import AuthenticationConfigurationError, AuthenticationResponseError
from .signals import token_set_successfully

# PBN wraca na callback wyłącznie z ``?ott=<uuid>`` — parametru ``state`` NIE
# zwraca. Powiązanie callbacku z autoryzacją rozpoczętą przez tego samego
# użytkownika opiera się więc na sesji: /pbn_api/authorize zapisuje w niej
# "oczekującą autoryzację", a callback ją zużywa (jednorazowo, z limitem
# czasu). Trzymamy jeden wpis — ostatnio rozpoczętą autoryzację.
PBN_PENDING_AUTH_SESSION_KEY = "pbn_api_pending_auth"
PBN_PENDING_AUTH_MAX_AGE_SECONDS = 10 * 60

PBN_AUTH_REJECTED_MESSAGE = (
    "Nie można zakończyć autoryzacji w PBN API - nie znaleziono aktualnej "
    "autoryzacji rozpoczętej w tej sesji (mogła wygasnąć albo została już "
    "użyta). Kliknij ponownie „autoryzuj PBN API”."
)


def _safe_local_url(request, url):
    if isinstance(url, str) and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}
    ):
        return url
    return "/"


def _start_pending_auth(request, original_page):
    nonce = secrets.token_urlsafe(32)
    request.session[PBN_PENDING_AUTH_SESSION_KEY] = {
        "nonce": nonce,
        "started": timezone.now().timestamp(),
        "originalPage": _safe_local_url(request, original_page),
    }
    return nonce


def _pop_pending_auth(request):
    """Zdejmuje (jednorazowo) oczekującą autoryzację z sesji. Zwraca jej dane,
    jeżeli istniała i nie wygasła; w przeciwnym razie None."""
    pending = request.session.pop(PBN_PENDING_AUTH_SESSION_KEY, None)
    if not isinstance(pending, dict):
        return None
    started = pending.get("started")
    if not isinstance(started, (int, float)):
        return None
    age = timezone.now().timestamp() - started
    if age < 0 or age > PBN_PENDING_AUTH_MAX_AGE_SECONDS:
        return None
    return pending


def _is_cross_site_request(request):
    """Czy wejście na /pbn_api/authorize przyszło z obcej witryny.

    Oczekująca autoryzacja w sesji ma sens tylko wtedy, gdy rozpoczął ją
    sam użytkownik z poziomu BPP — nie strona trzecia, która przekierowała
    do nas jego przeglądarkę. Linki "autoryzuj PBN API" są w BPP, więc
    przeglądarka zgłasza ``Sec-Fetch-Site: same-origin`` (albo ``none`` przy
    wpisaniu adresu ręcznie). Starsze przeglądarki bez Sec-Fetch-* sprawdzamy
    po nagłówku Referer, jeżeli jest obecny."""
    sec_fetch_site = request.META.get("HTTP_SEC_FETCH_SITE")
    if sec_fetch_site:
        return sec_fetch_site == "cross-site"
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return not url_has_allowed_host_and_scheme(
            referer, allowed_hosts={request.get_host()}
        )
    return False


class TokenRedirectPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if _is_cross_site_request(self.request):
            self.request.session.pop(PBN_PENDING_AUTH_SESSION_KEY, None)
            messages.error(
                self.request,
                "Autoryzację w PBN API należy rozpocząć z poziomu BPP - "
                "kliknij „autoryzuj PBN API”.",
            )
            return "/"

        uczelnia = Uczelnia.objects.get_for_request(self.request)

        # Get the original page from 'next' parameter or HTTP referer
        next_url = self.request.GET.get("next")
        if not next_url:
            # Fall back to HTTP referer if no next parameter
            next_url = self.request.META.get("HTTP_REFERER", "/")

        nonce = _start_pending_auth(self.request, next_url)

        # PBN nie odsyła ``state`` z powrotem; wysyłamy go wyłącznie
        # informacyjnie, nic po stronie callbacku od niego nie zależy.
        state_data = {
            "originalPage": next_url,
            "timestamp": timezone.now().timestamp(),
            "nonce": nonce,
        }

        # Encode state as base64 JSON
        state = base64.b64encode(json.dumps(state_data).encode()).decode()

        return OAuthMixin.get_auth_url(
            uczelnia.pbn_api_root, uczelnia.pbn_app_name, state=state
        )


class TokenLandingPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        ott = self.request.GET.get("ott")

        if not ott:
            raise HttpResponseBadRequest("Brak parametru OTT lub pusty")

        pending = _pop_pending_auth(self.request)
        if pending is None:
            messages.error(self.request, PBN_AUTH_REJECTED_MESSAGE)
            return "/"

        uczelnia = Uczelnia.objects.get_for_request(self.request)

        redirect_url = _safe_local_url(self.request, pending.get("originalPage"))

        try:
            user_token = OAuthMixin.get_user_token(
                uczelnia.pbn_api_root,
                uczelnia.pbn_app_name,
                uczelnia.pbn_app_token,
                ott,
                timeout=getattr(
                    settings,
                    "PBN_CLIENT_HTTP_TIMEOUT",
                    pbn_defaults.PBN_CLIENT_HTTP_TIMEOUT,
                ),
            )
            user = self.request.user
            user.pbn_token = user_token
            user.pbn_token_updated = timezone.now()
            user.save()

            transaction.on_commit(lambda: token_set_successfully.send(sender=user))
            from pbn_export_queue.tasks import kolejka_ponow_wysylke_prac_po_zalogowaniu

            transaction.on_commit(
                lambda user_pk=user.pk: kolejka_ponow_wysylke_prac_po_zalogowaniu.delay(
                    user_pk
                )
            )

            messages.info(
                self.request, "Autoryzacja w PBN API przeprowadzona pomyślnie."
            )

        except AuthenticationConfigurationError as e:
            messages.error(
                self.request, f"Nie można autoryzować zalogowania do PBN - {e}"
            )
            rollbar.report_exc_info(sys.exc_info())

        except AuthenticationResponseError:
            messages.error(
                self.request,
                "Bez możliwości autoryzacji - błąd odpowiedzi z serwera "
                "autoryzacyjnego. Ze względów bezpieczeństwa wyświetlenie niewskazane - "
                "błąd przekazano do administratora serwisu.  ",
            )
            rollbar.report_exc_info(sys.exc_info())

        return redirect_url
