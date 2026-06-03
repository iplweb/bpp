import logging
import sys

from django.conf import settings
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


def _dump_claims_to_stderr(claims):
    """Wypisz na stderr klucze i wartości claimów z Keycloaka.

    Cel discovery: zobaczyć, co realnie wystawia realm KA, bez interaktywnego
    klikania — wynik ląduje w konsoli runservera / logu serwera. Banner ułatwia
    wyłowienie tego w hałasie logów (`grep '\\[OIDC\\]'`).
    """
    keys = sorted(claims.keys())
    banner = "=" * 70
    print(banner, file=sys.stderr)
    print("[OIDC] Claimy otrzymane z Keycloaka (userinfo):", file=sys.stderr)
    print(f"[OIDC] Klucze ({len(keys)}): {', '.join(keys)}", file=sys.stderr)
    for key in keys:
        print(f"[OIDC]   {key} = {claims[key]!r}", file=sys.stderr)
    print(banner, file=sys.stderr, flush=True)


class BppOIDCBackend(OIDCAuthenticationBackend):
    """Backend logowania OpenID Connect (Keycloak) dla BPP.

    Faza 2a (discovery, obecna): zakładaj konto KAŻDEMU zalogowanemu —
    zwykłe konto, **bez** ``is_staff``/``is_superuser`` — i wypisz na stderr
    klucze claimów, żeby zobaczyć, co wystawia realm. To krok poznawczy: na
    podstawie realnych kluczy zaprojektujemy właściwe reguły.

    ⚠️ „Konto każdemu" oznacza, że dowolna osoba z realmu KA (potencjalnie też
    studenci — patrz scope ``kierunek-oidc``) dostanie konto BPP. Bezpieczne o
    tyle, że bez ``is_staff`` nie ma dostępu do panelu/edycji. To stan tymczasowy.

    Przypisanie uczelni: konto dostaje ``accessible_uczelnie`` (M2M z PR #189)
    z uczelnią o ``skrot`` == skrótowi z konfiguracji OIDC. Ten sam skrót
    (np. ``UAFM``), który wybrał ``client_id``/``client_secret``, mapuje 1:1 na
    ``Uczelnia.skrot`` — dzięki czemu docelowe „3 backendy = 3 uczelnie" same
    przypisują właściwą uczelnię, bez dodatkowej konfiguracji.

    Faza 2b (po obejrzeniu kluczy) — TU wejdą reguły:
      * gating po rolach/grupach (``realm_access.roles``): „kogo nie wpuszczamy"
        → ``verify_claims`` zwraca ``False``;
      * „komu nie tworzymy konta" → warunek w ``create_user``;
      * mapowanie ról Keycloaka na grupy/uprawnienia → ``update_user``;
      * powiązanie z istniejącym ``Autor`` przez claim ``person_id`` →
        ``filter_users_by_claims``.
    """

    def verify_claims(self, claims):
        _dump_claims_to_stderr(claims)
        logger.info("OIDC: otrzymane claimy: %r", claims)
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

    def create_user(self, claims):
        """Załóż zwykłe konto (bez is_staff) na podstawie claimów.

        ``username`` = ``preferred_username`` → ``email`` → ``sub`` (pierwszy
        niepusty). Hasło ustawiane na nieużywalne — logowanie wyłącznie przez
        OIDC. Wywoływane tylko, gdy ``filter_users_by_claims`` (domyślnie po
        e-mailu) nie znajdzie istniejącego konta.
        """
        username = (
            claims.get("preferred_username") or claims.get("email") or claims.get("sub")
        )
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
