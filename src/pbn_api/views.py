# Create your views here.
import sentry_sdk
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.views.generic import RedirectView

from .client import OAuthMixin
from .exceptions import AuthenticationConfigurationError, AuthenticationResponseError
from .signals import token_set_successfully

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

from django.utils import timezone

from bpp.models import Uczelnia


class TokenRedirectPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_default()
        return OAuthMixin.get_auth_url(uczelnia.pbn_api_root, uczelnia.pbn_app_name)


class TokenLandingPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        ott = self.request.GET.get("ott")

        if not ott:
            raise HttpResponseBadRequest("Brak parametru OTT lub pusty")

        uczelnia = Uczelnia.objects.get_default()

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
            from pbn_api.tasks import kolejka_ponow_wysylke_prac_po_zalogowaniu

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
            sentry_sdk.capture_exception(e)

        except AuthenticationResponseError as e:
            messages.error(
                self.request,
                "Bez możliwości autoryzacji - błąd odpowiedzi z serwera "
                "autoryzacyjnego. Ze względów bezpieczeństwa wyświetlenie niewskazane - "
                "błąd przekazano do administratora serwisu.  ",
            )
            sentry_sdk.capture_exception(e)

        return "/"
