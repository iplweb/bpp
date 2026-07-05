"""Uodpornienie handlera ``user_login_failed`` z django-easy-audit.

easyaudit audytuje nieudane logowania robiąc twardo
``credentials[USERNAME_FIELD]`` (a nie ``.get(...)``). Backendy OAuth
(OIDC/Microsoft/ORCID) wołają ``auth.authenticate()`` bez ``username`` w
credentials — wtedy handler rzuca ``KeyError``, a przy
``DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True`` zamienia się to w HTTP 500
na ścieżce *nieudanego* logowania (m.in. callback OIDC).

Tu podmieniamy receiver easyaudit na cienki wrapper: gdy w ``credentials``
brakuje klucza username, dokładamy go (best-effort), a potem delegujemy do
**oryginalnej** funkcji easyaudit — reużywamy ich logikę zapisu audytu, więc
jest to odporne na zmiany wersji biblioteki.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_login_failed

logger = logging.getLogger(__name__)

# Ten sam dispatch_uid, którego używa easyaudit przy connect() — dzięki temu
# rozłączamy dokładnie jego receiver i podstawiamy nasz w to miejsce.
EASYAUDIT_DISPATCH_UID = "easy_audit_signals_login_failed"


def _ensure_username(credentials):
    """Zwróć ``credentials`` z gwarantowanym kluczem ``USERNAME_FIELD``.

    Gdy klucz jest — zwraca wejście bez zmian. Gdy go brak (typowe dla OAuth) —
    zwraca kopię z dorobionym username: ``preferred_username`` jeśli akurat
    jest w credentials, inaczej pusty string.
    """
    username_field = get_user_model().USERNAME_FIELD
    if username_field in credentials:
        return credentials
    return {
        **credentials,
        username_field: credentials.get("preferred_username") or "",
    }


def _make_guard(original):
    """Zbuduj receiver opakowujący ``original`` o sanityzację credentials."""

    def guarded_user_login_failed(sender, credentials, **kwargs):
        return original(
            sender=sender, credentials=_ensure_username(credentials), **kwargs
        )

    return guarded_user_login_failed


def install_easyaudit_login_failed_guard():
    """Podmień kruchy receiver easyaudit na odporny na brak ``username``.

    Import ``easyaudit.signals.auth_signals`` gwarantuje, że easyaudit zdążył
    podłączyć swój receiver, zanim go rozłączymy — niezależnie od kolejności
    ``INSTALLED_APPS``. Idempotentne: ponowne wywołanie podstawia świeży guard.
    """
    from easyaudit.signals import auth_signals

    guard = _make_guard(auth_signals.user_login_failed)
    user_login_failed.disconnect(dispatch_uid=EASYAUDIT_DISPATCH_UID)
    user_login_failed.connect(guard, dispatch_uid=EASYAUDIT_DISPATCH_UID)
    logger.debug("easyaudit user_login_failed guard zainstalowany")
    return guard
