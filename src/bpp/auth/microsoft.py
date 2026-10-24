"""Backend logowania Microsoft (Office 365) z dodatkowymi zabezpieczeniami.

Rozszerza ``microsoft_auth.backends.MicrosoftAuthenticationBackend``:

* przyjmuje wyłącznie tokeny wystawione przez skonfigurowany katalog Entra ID
  (claimy ``iss``/``tid``),
* nie wiąże automatycznie nowego konta Microsoft z istniejącym kontem
  z uprawnieniami lub z lokalnym hasłem, chyba że
  ``MICROSOFT_AUTH_LINK_BY_EMAIL = True``.

Konta Microsoft już powiązane z użytkownikiem BPP logują się bez zmian.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from microsoft_auth.backends import MicrosoftAuthenticationBackend

from bpp.auth.microsoft_conf import claims_match_tenant, may_link_existing_users

logger = logging.getLogger(__name__)


class BppMicrosoftAuthenticationBackend(MicrosoftAuthenticationBackend):
    def _expected_issuer(self):
        openid_config = self.microsoft.openid_config or {}
        return openid_config.get("issuer")

    def _authenticate_microsoft_user(self):
        claims = self.microsoft.get_claims()
        if claims is None:
            return None

        tenant_id = getattr(settings, "MICROSOFT_AUTH_TENANT_ID", None)
        if not claims_match_tenant(claims, tenant_id, self._expected_issuer()):
            logger.warning(
                "Odrzucono logowanie Microsoft: token spoza skonfigurowanego "
                "katalogu (tid=%r)",
                claims.get("tid"),
            )
            return None

        return self._get_user_from_microsoft(claims)

    def _verify_microsoft_user(self, microsoft_user, data):
        if microsoft_user.user is None:
            email = data.get("email")
            if email:
                matching = get_user_model().objects.filter(email=email)
                link_by_email = getattr(settings, "MICROSOFT_AUTH_LINK_BY_EMAIL", False)
                if not may_link_existing_users(matching, link_by_email):
                    logger.warning(
                        "Odmowa automatycznego powiązania konta Microsoft %r "
                        "z istniejącym użytkownikiem BPP (MICROSOFT_AUTH_LINK_"
                        "BY_EMAIL wyłączone). Powiąż konto ręcznie w adminie.",
                        microsoft_user.microsoft_id,
                    )
                    return None

        return super()._verify_microsoft_user(microsoft_user, data)
