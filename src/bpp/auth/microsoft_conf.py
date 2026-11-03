"""Reguły bezpieczeństwa logowania przez Microsoft (Office 365).

Moduł celowo NIE importuje ``microsoft_auth`` ani modeli Django — jest czytany
z ``settings/base.py`` zanim Django w pełni wstanie, a funkcje decyzyjne są
testowalne bez zainstalowanej aplikacji ``microsoft_auth``.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Wartości „tenant" Entra ID, które NIE wskazują jednej organizacji:
# akceptują konta z dowolnego katalogu (lub konta prywatne Microsoft).
MULTI_TENANT_VALUES = frozenset({"common", "organizations", "consumers"})

_GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_guid(value):
    return bool(value) and bool(_GUID_RE.match(str(value).strip().lower()))


#: ID system checka ostrzegającego o braku konkretnego katalogu (tenanta).
W_TENANT_ID = "bpp.W201"

#: Wartość używana przez ``django_microsoft_auth``, gdy tenant nie jest podany.
DEFAULT_TENANT_ID = "common"


def normalize_microsoft_tenant_id(tenant_id):
    """Zwróć znormalizowany ``tenant_id``; pusty -> ``"common"``.

    Brak konkretnego katalogu nie blokuje startu — logowanie działa wtedy
    w trybie wielokatalogowym, a operator dostaje ostrzeżenie
    (system check ``bpp.W201`` i komunikat dla superusera po zalogowaniu).
    """
    value = (tenant_id or "").strip()
    return value or DEFAULT_TENANT_ID


def is_multi_tenant(tenant_id):
    """Czy ``tenant_id`` NIE wskazuje jednego, konkretnego katalogu?"""
    value = (tenant_id or "").strip().lower()
    return not value or value in MULTI_TENANT_VALUES


def microsoft_tenant_warning(client_id, tenant_id, allow_linking=False):
    """Treść ostrzeżenia o braku konkretnego tenanta albo ``None``.

    Ostrzeżenie dotyczy wyłącznie instalacji z włączonym logowaniem Microsoft
    (ustawione ``MICROSOFT_AUTH_CLIENT_ID``).
    """
    if not client_id or not is_multi_tenant(tenant_id):
        return None
    shown = (tenant_id or "").strip() or "(pusty)"
    tresc = (
        "Logowanie przez Microsoft działa w trybie wielokatalogowym "
        f"(MICROSOFT_AUTH_TENANT_ID = {shown}): BPP nie sprawdza, z którego "
        "katalogu Entra ID pochodzi token."
    )
    if allow_linking:
        return tresc + (
            " Włączono MICROSOFT_AUTH_MULTI_TENANT_ALLOW_LINKING — nowe konta "
            "Microsoft są zakładane i wiązane po adresie e-mail, którego "
            "w tym trybie nie da się zweryfikować."
        )
    return tresc + (
        " Logują się wyłącznie konta Microsoft już powiązane z kontem BPP; "
        "zakładanie nowych kont i wiązanie po adresie e-mail są wyłączone."
    )


#: Podpowiedź dołączana do ostrzeżenia (system check i komunikat po logowaniu).
TENANT_HINT = (
    "Ustaw MICROSOFT_AUTH_TENANT_ID na identyfikator katalogu uczelni (GUID, "
    "portal Azure: Microsoft Entra ID -> Przegląd -> Identyfikator dzierżawy) "
    "albo jego domenę, np. uczelnia.onmicrosoft.com, i zrestartuj serwer — "
    "wtedy działa pełna weryfikacja katalogu, a zakładanie i wiązanie kont "
    "wracają do zwykłych reguł."
)


def ostrzez_superusera_o_tenancie_microsoft(sender, request, user, **kwargs):
    """Handler ``user_logged_in``: superuser dostaje komunikat, gdy logowanie
    Microsoft jest włączone bez konkretnego katalogu (tenanta).

    Nigdy nie przerywa logowania — błędy są logowane.
    """
    if request is None or not getattr(user, "is_superuser", False):
        return

    try:
        from django.conf import settings
        from django.contrib import messages

        tresc = microsoft_tenant_warning(
            getattr(settings, "MICROSOFT_AUTH_CLIENT_ID", None),
            getattr(settings, "MICROSOFT_AUTH_TENANT_ID", None),
            getattr(settings, "MICROSOFT_AUTH_MULTI_TENANT_ALLOW_LINKING", False),
        )
        if tresc:
            messages.warning(request, f"{tresc} {TENANT_HINT}", fail_silently=True)
    except Exception:
        # Komunikat jest informacyjny — żaden błąd nie może zablokować
        # logowania. Pełny traceback trafia do logów.
        logger.exception(
            "Nieoczekiwany błąd przy sprawdzaniu konfiguracji tenanta Microsoft."
        )


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
