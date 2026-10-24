"""Reguły bezpieczeństwa logowania przez Microsoft (Office 365).

Moduł celowo NIE importuje ``microsoft_auth`` ani modeli Django — jest czytany
z ``settings/base.py`` zanim Django w pełni wstanie, a funkcje decyzyjne są
testowalne bez zainstalowanej aplikacji ``microsoft_auth``.
"""

import re

from django.core.exceptions import ImproperlyConfigured

# Wartości „tenant" Entra ID, które NIE wskazują jednej organizacji:
# akceptują konta z dowolnego katalogu (lub konta prywatne Microsoft).
MULTI_TENANT_VALUES = frozenset({"common", "organizations", "consumers"})

_GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_guid(value):
    return bool(value) and bool(_GUID_RE.match(str(value).strip().lower()))


def validate_microsoft_tenant_id(tenant_id):
    """Zwróć znormalizowany ``tenant_id`` albo rzuć ``ImproperlyConfigured``.

    Logowanie Microsoft wymaga wskazania konkretnej organizacji (GUID katalogu
    albo jego domena, np. ``uczelnia.onmicrosoft.com``).
    """
    value = (tenant_id or "").strip()
    if not value or value.lower() in MULTI_TENANT_VALUES:
        raise ImproperlyConfigured(
            "Zdefiniowano MICROSOFT_AUTH_CLIENT_ID, ale MICROSOFT_AUTH_TENANT_ID "
            f"jest pusty lub ogólny ({value!r}). Ustaw MICROSOFT_AUTH_TENANT_ID "
            "na identyfikator (GUID) lub domenę katalogu Entra ID uczelni — "
            "wartości 'common', 'organizations' i 'consumers' są niedozwolone."
        )
    return value


def claims_match_tenant(claims, tenant_id, expected_issuer):
    """Czy claimy ``id_token`` pochodzą ze skonfigurowanego katalogu?

    ``expected_issuer`` to ``issuer`` z dokumentu OpenID discovery pobranego
    dla skonfigurowanego tenanta (dla konkretnego katalogu zawiera jego GUID).
    """
    if not claims or not tenant_id or not expected_issuer:
        return False
    if "{" in expected_issuer:
        # Szablon issuera ({tenantid}) — discovery dla endpointu wielotenantowego.
        return False

    tid = str(claims.get("tid") or "").strip().lower()
    iss = str(claims.get("iss") or "").strip()
    if not tid or not iss:
        return False

    if iss != expected_issuer:
        return False
    if tid not in iss.lower():
        return False
    if is_guid(tenant_id) and tid != tenant_id.strip().lower():
        return False
    return True


def user_is_protected_from_email_linking(user):
    """Czy istniejącego użytkownika NIE wolno automatycznie powiązać po e-mailu.

    Chronione są konta z uprawnieniami administracyjnymi oraz konta posiadające
    lokalne hasło.
    """
    if user.is_staff or user.is_superuser:
        return True
    if user.password and user.has_usable_password():
        return True
    return False


def may_link_existing_users(users, link_by_email):
    """Czy wolno powiązać nowe konto Microsoft z (jedynym) użytkownikiem z listy.

    Pusta lista — nie ma kogo wiązać (zostanie założone nowe konto), więc
    ``True``. Więcej niż jeden pasujący użytkownik — odmowa.
    """
    users = list(users)
    if not users:
        return True
    if len(users) > 1:
        return False
    if link_by_email:
        return True
    return not user_is_protected_from_email_linking(users[0])
