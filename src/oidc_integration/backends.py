import logging

from django.conf import settings
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


def _log_claims_debug(claims):
    """Zaloguj klucze i wartości claimów z Keycloaka na poziomie DEBUG.

    Po fazie discovery nie zaśmiecamy już stderr bannerem — podgląd claimów
    zostaje dostępny przez ``logging`` na DEBUG (np. do diagnostyki realmu),
    ale domyślnie milczy. Guard na ``isEnabledFor`` unika składania stringów,
    gdy DEBUG i tak jest wyłączony.
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    keys = sorted(claims.keys())
    logger.debug("OIDC: otrzymane claimy (%d): %s", len(keys), ", ".join(keys))
    for key in keys:
        logger.debug("OIDC:   %s = %r", key, claims[key])


class BppOIDCBackend(OIDCAuthenticationBackend):
    """Backend logowania OpenID Connect (Keycloak) dla BPP.

    Zachowanie: zakładaj konto KAŻDEMU zalogowanemu z realmu — zwykłe konto,
    **bez** ``is_staff``/``is_superuser``. Dopasowanie istniejących kont i
    tworzenie nowych odbywa się po e-mailu; ``username`` bierzemy z
    ``preferred_username``.

    ⚠️ „Konto każdemu" oznacza, że dowolna osoba z realmu KA (potencjalnie też
    studenci — patrz scope ``kierunek-oidc``) dostanie konto BPP. Bezpieczne o
    tyle, że bez ``is_staff`` nie ma dostępu do panelu/edycji.

    Normalizacja claimów: realm KA wystawia adres pod kluczem ``mail``, a
    ``mozilla-django-oidc`` (``verify_claims``/``filter_users_by_claims``/
    ``create_user``) oczekuje ``email``. Uzupełniamy ``email`` z ``mail`` w
    jednym miejscu — ``get_userinfo`` — przez które przechodzą wszystkie te
    metody (``get_or_create_user`` woła je na wyniku ``get_userinfo``).

    Przypisanie uczelni: konto dostaje ``accessible_uczelnie`` (M2M z PR #189)
    z uczelnią o ``skrot`` == skrótowi z konfiguracji OIDC. Ten sam skrót
    (np. ``UAFM``), który wybrał ``client_id``/``client_secret``, mapuje 1:1 na
    ``Uczelnia.skrot`` — dzięki czemu docelowe „3 backendy = 3 uczelnie" same
    przypisują właściwą uczelnię, bez dodatkowej konfiguracji.

    Możliwe rozszerzenia (poza zakresem): gating po rolach/grupach
    (``realm_access.roles``) w ``verify_claims``; mapowanie ról na grupy/
    uprawnienia w ``update_user``.
    """

    @staticmethod
    def _normalized(claims):
        """Zwróć claimy z uzupełnionym ``email`` z ``mail`` (jeśli trzeba).

        Gdy ``email`` już jest albo nie ma ``mail`` — zwraca wejście bez zmian.
        W przeciwnym razie zwraca **kopię** z dorobionym ``email`` (oryginalny
        ``mail`` zostaje zachowany).
        """
        if claims.get("email") or not claims.get("mail"):
            return claims
        return {**claims, "email": claims["mail"]}

    def get_userinfo(self, access_token, id_token, payload):
        # Jedyny chokepoint: znormalizuj claimy z userinfo, zanim trafią do
        # verify_claims / filter_users_by_claims / create_user.
        claims = super().get_userinfo(access_token, id_token, payload)
        return self._normalized(claims)

    def verify_claims(self, claims):
        _log_claims_debug(claims)
        return super().verify_claims(claims)

    def _assign_uczelnia(self, user):
        """Przypisz uczelnię docelową (``accessible_uczelnie``) wg skrótu OIDC.

        Idempotentne (``.add`` na M2M). Brak skrótu albo brak pasującej
        ``Uczelnia`` → konto bez przypisania (z logiem), nie błąd.
        """
        skrot = getattr(settings, "OIDC_LOGIN_SKROT", "") or ""
        if not skrot:
            logger.info("OIDC: brak skrótu uczelni w konfiguracji — bez przypisania")
            return

        # Import lokalny: backends.py bywa ładowany bardzo wcześnie (settings).
        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.filter(skrot__iexact=skrot).first()
        if uczelnia is None:
            logger.warning(
                "OIDC: nie znaleziono Uczelni o skrocie=%s — konto bez przypisania",
                skrot,
            )
            return

        user.accessible_uczelnie.add(uczelnia)
        logger.info(
            "OIDC: przypisano uczelnię skrot=%s do konta %s", skrot, user.username
        )

    def update_user(self, user, claims):
        # Dopilnuj przypisania uczelni także istniejącym kontom przy kolejnym
        # logowaniu (idempotentnie) — np. założonym przed wprowadzeniem tej logiki.
        self._assign_uczelnia(user)
        return user

    def _unique_username(self, base):
        """Zwróć ``base`` albo ``base-2``/``base-3``… jeśli zajęty.

        ``create_user`` woła się tylko, gdy nie ma konta dopasowanego po
        e-mailu — ale sam username mógłby kolidować z innym kontem (ten sam
        ``preferred_username`` przy innym e-mailu). Bez tego byłby IntegrityError.
        """
        manager = self.UserModel.objects
        if not manager.filter(username=base).exists():
            return base
        i = 2
        while manager.filter(username=f"{base}-{i}").exists():
            i += 1
        return f"{base}-{i}"

    def create_user(self, claims):
        """Załóż zwykłe konto (bez is_staff) na podstawie claimów.

        ``username`` = ``preferred_username`` → ``email`` → ``sub`` (pierwszy
        niepusty). Hasło ustawiane na nieużywalne — logowanie wyłącznie przez
        OIDC. Wywoływane tylko, gdy ``filter_users_by_claims`` (domyślnie po
        e-mailu) nie znajdzie istniejącego konta.
        """
        base_username = (
            claims.get("preferred_username") or claims.get("email") or claims.get("sub")
        )
        username = self._unique_username(base_username)
        email = claims.get("email") or ""

        user = self.UserModel.objects.create_user(username=username, email=email)
        user.first_name = claims.get("given_name") or ""
        user.last_name = claims.get("family_name") or ""
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_unusable_password()
        user.save()

        self._assign_uczelnia(user)

        logger.info(
            "OIDC: utworzono konto username=%s email=%s (zwykłe, bez is_staff)",
            username,
            email,
        )
        return user
