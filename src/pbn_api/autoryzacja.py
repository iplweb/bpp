"""Wspólna ścieżka zapisu tokenu PBN użytkownika.

Używana przez callback ``/pbn_api/callback`` (``TokenLandingPage``) oraz
komendę ``pbn_ott_na_token``.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pbn_client.conf import settings as pbn_defaults

from .client import OAuthMixin
from .exceptions import AuthenticationResponseError
from .signals import token_set_successfully


def zapisz_token(user, token):
    """Zapisuje token PBN użytkownikowi i (po commicie) uruchamia ponowną
    wysyłkę prac oczekujących na zalogowanie."""
    user.pbn_token = token
    user.pbn_token_updated = timezone.now()
    user.save()

    transaction.on_commit(lambda: token_set_successfully.send(sender=user))
    from pbn_export_queue.tasks import kolejka_ponow_wysylke_prac_po_zalogowaniu

    transaction.on_commit(
        lambda user_pk=user.pk: kolejka_ponow_wysylke_prac_po_zalogowaniu.delay(user_pk)
    )


def zapisz_token_z_ott(user, uczelnia, ott):
    """Wymienia jednorazowy ``ott`` na token PBN i zapisuje go użytkownikowi.

    Wyjątki ``AuthenticationConfigurationError`` /
    ``AuthenticationResponseError`` z klienta PBN są przepuszczane dalej.
    Zwraca token."""
    token = OAuthMixin.get_user_token(
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
    if not token:
        # PBN odpowiada JSON-em bez X-User-Token np. dla nieważnego ott.
        raise AuthenticationResponseError("Odpowiedź PBN nie zawiera tokenu.")
    zapisz_token(user, token)
    return token
