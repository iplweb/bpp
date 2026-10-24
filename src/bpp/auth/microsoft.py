"""Backend logowania Microsoft (Office 365) z dodatkowymi zabezpieczeniami.

Rozszerza ``microsoft_auth.backends.MicrosoftAuthenticationBackend``:

* przy ustawionym konkretnym katalogu Entra ID (GUID lub domena) przyjmuje
  wyłącznie tokeny wystawione przez ten katalog (claimy ``iss``/``tid``);
  bez konkretnego katalogu (``common``/``organizations``/``consumers`` lub
  pusty) działa w trybie wielokatalogowym — tę konfigurację zgłasza system
  check ``bpp.W201``; w tym trybie logują się wyłącznie konta Microsoft już
  powiązane z kontem BPP (bez wiązania po e-mailu i bez zakładania nowych
  kont), chyba że ``MICROSOFT_AUTH_MULTI_TENANT_ALLOW_LINKING = True``,
* nie wiąże nowego konta Microsoft z kontem BPP, gdy token nie ma e-maila
  albo e-mail pasuje do więcej niż jednego konta,
* nie wiąże automatycznie nowego konta Microsoft z istniejącym kontem
  z uprawnieniami lub z lokalnym hasłem, chyba że
  ``MICROSOFT_AUTH_LINK_BY_EMAIL = True``.

Konta Microsoft już powiązane z użytkownikiem BPP logują się bez zmian.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from microsoft_auth.backends import MicrosoftAuthenticationBackend
from microsoft_auth.conf import CACHE_KEY_JWKS, CACHE_KEY_OPENID

from bpp.auth.microsoft_conf import (
    claims_match_tenant,
    is_guid,
    is_multi_tenant,
    may_link_existing_users,
)

logger = logging.getLogger(__name__)

#: Komunikat dla użytkownika, gdy konto Microsoft nie jest powiązane z BPP.
KOMUNIKAT_NIEPOWIAZANE = (
    "Konto Microsoft nie jest powiązane z kontem w BPP — skontaktuj się "
    "z administratorem."
)


class BppMicrosoftAuthenticationBackend(MicrosoftAuthenticationBackend):
    def authenticate(self, request, code=None):
        self._request = request
        return super().authenticate(request, code=code)

    def _odmowa_niepowiazane(self):
        request = getattr(self, "_request", None)
        if request is not None:
            messages.error(request, KOMUNIKAT_NIEPOWIAZANE, fail_silently=True)
        return None

    def _get_linked_user_only(self, claims):
        """Tryb wielokatalogowy bez opt-in: tylko konta już powiązane."""
        from microsoft_auth.models import MicrosoftAccount

        account = (
            MicrosoftAccount.objects.filter(microsoft_id=claims.get("sub"))
            .select_related("user")
            .first()
        )
        if account is not None and account.user is not None:
            return account.user
        logger.warning(
            "Odrzucono logowanie Microsoft (tryb wielokatalogowy): konto "
            "%r nie jest powiązane z użytkownikiem BPP.",
            claims.get("sub"),
        )
        return self._odmowa_niepowiazane()

    def _expected_issuer(self, tenant_id):
        issuer = (self.microsoft.openid_config or {}).get("issuer") or ""
        if self._issuer_is_stale(issuer, tenant_id):
            # Dokument discovery jest cache'owany pod kluczem niezależnym od
            # tenanta — po zmianie MICROSOFT_AUTH_TENANT_ID w cache może leżeć
            # wersja dla innego endpointu. Odśwież jednorazowo.
            cache.delete(CACHE_KEY_OPENID)
            cache.delete(CACHE_KEY_JWKS)
            issuer = (self.microsoft.openid_config or {}).get("issuer") or ""
        return issuer

    @staticmethod
    def _issuer_is_stale(issuer, tenant_id):
        if not issuer or "{" in issuer:
            return True
        if is_guid(tenant_id) and tenant_id.strip().lower() not in issuer.lower():
            return True
        return False

    def _authenticate_microsoft_user(self):
        claims = self.microsoft.get_claims()
        if claims is None:
            return None

        tenant_id = getattr(settings, "MICROSOFT_AUTH_TENANT_ID", None)
        if is_multi_tenant(tenant_id):
            # Tryb wielokatalogowy: nie ma katalogu, względem którego można
            # sprawdzić iss/tid (podpis i audience sprawdza biblioteka).
            # Adres e-mail w tokenie nie jest wtedy wiarygodny — bez jawnego
            # opt-in logują się wyłącznie konta już powiązane.
            if not getattr(
                settings, "MICROSOFT_AUTH_MULTI_TENANT_ALLOW_LINKING", False
            ):
                return self._get_linked_user_only(claims)
            return self._get_user_from_microsoft(claims)

        expected_issuer = self._expected_issuer(tenant_id)
        if not claims_match_tenant(claims, tenant_id, expected_issuer):
            logger.warning(
                "Odrzucono logowanie Microsoft: token spoza skonfigurowanego "
                "katalogu (tid=%r)",
                claims.get("tid"),
            )
            return None

        return self._get_user_from_microsoft(claims)

    @staticmethod
    def _split_name(fullname):
        first_name, last_name = "", ""
        if fullname:
            try:
                # Format „Nazwisko, Imię"
                last_name, first_name = fullname.split(", ")
            except ValueError:
                try:
                    first_name, last_name = fullname.split(" ", 1)
                except ValueError:
                    first_name = fullname
        return first_name, last_name

    def _verify_microsoft_user(self, microsoft_user, data):
        """Zwróć użytkownika BPP dla konta Microsoft (fail-closed).

        Konto już powiązane — bez zmian. Nowe konto Microsoft: wymagany
        niepusty e-mail; wyszukanie bez rozróżniania wielkości liter; więcej
        niż jedno trafienie, konto z uprawnieniami lub z hasłem lokalnym
        (bez ``MICROSOFT_AUTH_LINK_BY_EMAIL``) — odmowa.
        """
        if microsoft_user.user is not None:
            return microsoft_user.user

        email = (data.get("email") or "").strip()
        if not email:
            logger.warning(
                "Odrzucono logowanie Microsoft %r: token bez adresu e-mail.",
                microsoft_user.microsoft_id,
            )
            return self._odmowa_niepowiazane()

        User = get_user_model()
        matching = list(User.objects.filter(email__iexact=email)[:2])
        link_by_email = getattr(settings, "MICROSOFT_AUTH_LINK_BY_EMAIL", False)
        if not may_link_existing_users(matching, link_by_email):
            logger.warning(
                "Odmowa automatycznego powiązania konta Microsoft %r "
                "z istniejącym użytkownikiem BPP. Powiąż konto ręcznie "
                "w adminie lub ustaw MICROSOFT_AUTH_LINK_BY_EMAIL.",
                microsoft_user.microsoft_id,
            )
            return self._odmowa_niepowiazane()

        first_name, last_name = self._split_name(data.get("name"))

        if matching:
            user = matching[0]
            if user.first_name == "" and user.last_name == "":
                user.first_name = first_name
                user.last_name = last_name
                user.save()
        else:
            username = (data.get("preferred_username") or email)[:150]
            user = User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            user.save()

        existing_account = self._get_existing_microsoft_account(user)
        if existing_account is not None:
            if self.config.MICROSOFT_AUTH_AUTO_REPLACE_ACCOUNTS:
                existing_account.user = None
                existing_account.save()
            else:
                logger.warning(
                    "Użytkownik %r ma już powiązane konto Microsoft, a "
                    "MICROSOFT_AUTH_AUTO_REPLACE_ACCOUNTS jest wyłączone.",
                    user.pk,
                )
                return None

        microsoft_user.user = user
        microsoft_user.save()
        return user
