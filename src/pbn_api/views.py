# Create your views here.
import base64
import binascii
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
from django.views.generic import RedirectView
from pbn_client.conf import settings as pbn_defaults

from bpp.models import Uczelnia

from .client import OAuthMixin
from .exceptions import AuthenticationConfigurationError, AuthenticationResponseError
from .signals import token_set_successfully

# Klucz sesji z listą jednorazowych nonce'ów wydanych przy rozpoczęciu
# autoryzacji PBN. Lista (a nie pojedyncza wartość), żeby równoległa
# autoryzacja z dwóch kart nie unieważniała się nawzajem.
PBN_STATE_NONCES_SESSION_KEY = "pbn_api_state_nonces"
PBN_STATE_NONCES_MAX = 5


def _issue_state_nonce(request):
    nonce = secrets.token_urlsafe(32)
    nonces = list(request.session.get(PBN_STATE_NONCES_SESSION_KEY, []))
    nonces.append(nonce)
    request.session[PBN_STATE_NONCES_SESSION_KEY] = nonces[-PBN_STATE_NONCES_MAX:]
    return nonce


def _consume_state_nonce(request, nonce):
    """Sprawdza nonce ze ``state`` z wartościami w sesji; zgodny usuwa
    (jednorazowy). Zwraca True tylko przy zgodności."""
    if not isinstance(nonce, str) or not nonce:
        return False
    nonces = list(request.session.get(PBN_STATE_NONCES_SESSION_KEY, []))
    for stored in nonces:
        if isinstance(stored, str) and secrets.compare_digest(
            stored.encode(), nonce.encode()
        ):
            nonces.remove(stored)
            request.session[PBN_STATE_NONCES_SESSION_KEY] = nonces
            return True
    return False


def _decode_state(state):
    if not state:
        return None
    # "+" z base64 bywa po drodze zamieniany na spację w query stringu.
    state = state.replace(" ", "+")
    try:
        state_data = json.loads(base64.b64decode(state).decode())
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    if not isinstance(state_data, dict):
        return None
    return state_data


class TokenRedirectPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(self.request)

        # Get the original page from 'next' parameter or HTTP referer
        next_url = self.request.GET.get("next")
        if not next_url:
            # Fall back to HTTP referer if no next parameter
            next_url = self.request.META.get("HTTP_REFERER", "/")

        # Create state data
        state_data = {
            "originalPage": next_url,
            "timestamp": timezone.now().timestamp(),
            "nonce": _issue_state_nonce(self.request),
        }

        # Encode state as base64 JSON
        state = base64.b64encode(json.dumps(state_data).encode()).decode()

        return OAuthMixin.get_auth_url(
            uczelnia.pbn_api_root, uczelnia.pbn_app_name, state=state
        )


class TokenLandingPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        from django.utils.http import url_has_allowed_host_and_scheme

        ott = self.request.GET.get("ott")
        state = self.request.GET.get("state")

        if not ott:
            raise HttpResponseBadRequest("Brak parametru OTT lub pusty")

        state_data = _decode_state(state)
        if state_data is None or not _consume_state_nonce(
            self.request, state_data.get("nonce")
        ):
            messages.error(
                self.request,
                "Nie można zakończyć autoryzacji w PBN API - odpowiedź nie "
                "pochodzi z autoryzacji rozpoczętej w tej sesji. Rozpocznij "
                "autoryzację ponownie.",
            )
            return "/"

        uczelnia = Uczelnia.objects.get_for_request(self.request)

        # Default redirect URL
        redirect_url = "/"

        candidate = state_data.get("originalPage", "/")
        # The state parameter round-trips through the browser and is
        # therefore attacker-controllable; never redirect off-host.
        if isinstance(candidate, str) and url_has_allowed_host_and_scheme(
            candidate, allowed_hosts={self.request.get_host()}
        ):
            redirect_url = candidate

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
