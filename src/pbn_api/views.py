# Create your views here.
import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.views.generic import RedirectView

from bpp.models import Uczelnia

from .client import OAuthMixin
from .exceptions import AuthenticationConfigurationError, AuthenticationResponseError
from .signals import token_set_successfully


class TokenRedirectPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        import base64
        import json

        from django.utils import timezone

        uczelnia = Uczelnia.objects.get_default()

        # Get the original page from 'next' parameter or HTTP referer
        next_url = self.request.GET.get("next")
        if not next_url:
            # Fall back to HTTP referer if no next parameter
            next_url = self.request.META.get("HTTP_REFERER", "/")

        # Create state data
        state_data = {"originalPage": next_url, "timestamp": timezone.now().timestamp()}

        # Encode state as base64 JSON
        state = base64.b64encode(json.dumps(state_data).encode()).decode()

        return OAuthMixin.get_auth_url(
            uczelnia.pbn_api_root, uczelnia.pbn_app_name, state=state
        )


class TokenLandingPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        import base64
        import json

        ott = self.request.GET.get("ott")
        state = self.request.GET.get("state")

        if not ott:
            raise HttpResponseBadRequest("Brak parametru OTT lub pusty")

        uczelnia = Uczelnia.objects.get_default()

        # Default redirect URL
        redirect_url = "/"

        # Try to decode state parameter if present
        if state:
            try:
                # Decode base64 state
                state_json = base64.b64decode(state).decode()
                state_data = json.loads(state_json)
                redirect_url = state_data.get("originalPage", "/")
            except (ValueError, json.JSONDecodeError, KeyError):
                # If state decoding fails, fall back to default
                pass

        try:
            user_token = OAuthMixin.get_user_token(
                uczelnia.pbn_api_root,
                uczelnia.pbn_app_name,
                uczelnia.pbn_app_token,
                ott,
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
