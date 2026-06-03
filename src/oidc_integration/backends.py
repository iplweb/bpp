import logging

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


class BppOIDCBackend(OIDCAuthenticationBackend):
    """Backend logowania OpenID Connect (Keycloak) dla BPP.

    Faza 1 (spike): jedyne zadanie to ZOBACZYĆ, co realnie wystawia Keycloak —
    ``verify_claims`` loguje cały dict claimów i deleguje do domyślnej
    walidacji (która wymaga obecności ``email``, gdy scope ``email`` jest w
    ``OIDC_RP_SCOPES``). Konto ``BppUser`` jest auto-tworzone przez logikę
    bazową ``mozilla-django-oidc`` (``OIDC_CREATE_USER = True``).

    Faza 2 (po obejrzeniu claimów) — TU wchodzą reguły:
      * gating po rolach/grupach z tokenu (``realm_access.roles``):
        „tych ludzi nie wpuszczamy" → ``verify_claims`` zwraca ``False``;
      * „tym ludziom nie tworzymy kont" → nadpisać ``create_user``;
      * mapowanie ról Keycloaka na grupy/uprawnienia → ``update_user``;
      * powiązanie z istniejącym ``Autor`` przez claim ``person_id`` →
        ``filter_users_by_claims``.
    """

    def verify_claims(self, claims):
        # Spike: pełny podgląd tego, co przyszło z Keycloaka. Po fazie 2
        # zejść z poziomu INFO (claimy bywają wrażliwe — e-mail, person_id).
        logger.info("OIDC: otrzymane claimy: %r", claims)
        return super().verify_claims(claims)
