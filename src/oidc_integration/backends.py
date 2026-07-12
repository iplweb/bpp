import logging
import os
import re

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from oidc_integration.conf import DEFAULT_EMAIL_CLAIMS, DEFAULT_USERNAME_CLAIMS

logger = logging.getLogger(__name__)

# „Zawiera domenę" = wygląda jak adres ``lokalna@domena.tld`` (z kropką w
# części domenowej). Świadomie minimalistyczne: to nie walidacja RFC, tylko
# odsianie loginów bez domeny (np. ``jkowalski``) od UPN-ów (``j@uczelnia.pl``).
_EMAIL_SHAPE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email_claim_keys():
    """Klucze claimów e-mail wg preferencji (settings → default mail-first).

    Default ``DEFAULT_EMAIL_CLAIMS`` (mail-first) ustala ``conf.py``; settings
    ``OIDC_EMAIL_CLAIMS`` (wpisywany z env w base.py) może to nadpisać.
    """
    return tuple(getattr(settings, "OIDC_EMAIL_CLAIMS", None) or DEFAULT_EMAIL_CLAIMS)


def _username_claim_keys():
    """Klucze claimów dla username wg preferencji (settings → default)."""
    return tuple(
        getattr(settings, "OIDC_USERNAME_CLAIMS", None) or DEFAULT_USERNAME_CLAIMS
    )


def _first_claim(claims, keys):
    """Pierwsza niepusta wartość claimu z ``keys`` (albo ``None``)."""
    for key in keys:
        value = claims.get(key)
        if value:
            return value
    return None


def _redact_claim_value(value):
    """Zredagowana reprezentacja wartości claimu — BEZ danych osobowych.

    Diagnostyka realmu potrzebuje *kształtu* claimu (typ, długość, klucze
    zagnieżdżonych obiektów), a nie treści: wartości niosą PII (adresy
    e-mail, nazwy grup/ról, identyfikatory osoby). Dla ``dict`` pokazujemy
    same klucze (strukturalne, nie PII); dla ``list``/``str`` — typ i długość.
    """
    if isinstance(value, dict):
        return f"<dict keys={sorted(value.keys())}>"
    if isinstance(value, (list, tuple)):
        return f"<{type(value).__name__} len={len(value)}>"
    if isinstance(value, str):
        return f"<str len={len(value)}>"
    return f"<{type(value).__name__}>"


def _log_claims_debug(claims):
    """Zaloguj claimy z Keycloaka na poziomie DEBUG — domyślnie ZREDAGOWANE.

    Po fazie discovery nie zaśmiecamy stderr bannerem — podgląd claimów jest
    dostępny przez ``logging`` na DEBUG (diagnostyka realmu), ale domyślnie
    milczy. Guard ``isEnabledFor`` unika składania stringów, gdy DEBUG jest
    wyłączony.

    RODO/PII: domyślnie logujemy WYŁĄCZNIE nazwy claimów i zredagowany
    kształt wartości (``_redact_claim_value``) — bez adresów, grup ani
    identyfikatorów. Surowe wartości (``%r``) odblokowuje osobny, wyraźny
    opt-in ``DJANGO_BPP_OIDC_DEBUG_CLAIM_VALUES=1`` — tylko do krótkotrwałej
    diagnostyki, nigdy na stałe na produkcji.
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    keys = sorted(claims.keys())
    logger.debug("OIDC: otrzymane claimy (%d): %s", len(keys), ", ".join(keys))

    dump_values = os.getenv("DJANGO_BPP_OIDC_DEBUG_CLAIM_VALUES") == "1"
    for key in keys:
        if dump_values:
            logger.debug("OIDC:   %s = %r", key, claims[key])
        else:
            logger.debug("OIDC:   %s = %s", key, _redact_claim_value(claims[key]))


class BppOIDCBackend(OIDCAuthenticationBackend):
    """Backend logowania OpenID Connect (Keycloak) dla BPP.

    Zachowanie: zakładaj konto KAŻDEMU zalogowanemu z realmu — zwykłe konto,
    **bez** ``is_staff``/``is_superuser``. Dopasowanie istniejących kont i
    tworzenie nowych odbywa się po e-mailu; ``username`` bierzemy z
    ``preferred_username``.

    ⚠️ „Konto każdemu" oznacza, że dowolna osoba z realmu KA (potencjalnie też
    studenci — patrz scope ``kierunek-oidc``) dostanie konto BPP. Bezpieczne o
    tyle, że bez ``is_staff`` nie ma dostępu do panelu/edycji.

    Normalizacja claimów: ``mozilla-django-oidc``
    (``verify_claims``/``filter_users_by_claims``/``create_user``) oczekuje
    ``email``, a realm wystawia adres pod różnymi kluczami. Ustalamy ``email``
    w jednym miejscu — ``get_userinfo`` — przez które przechodzą wszystkie te
    metody (``get_or_create_user`` woła je na wyniku ``get_userinfo``).
    Kolejność preferencji konfigurowalna (``OIDC_EMAIL_CLAIMS``, default
    mail-first: ``mail`` → ``email`` → ``e-mail`` → ``e_mail``), a w
    ostateczności ``preferred_username`` jeśli zawiera domenę. Brak adresu →
    ``SuspiciousOperation`` (login failure). Default mail-first, bo w realmach
    LDAP-owych (np. UAFM) ``email`` bywa adresem prywatnym, a instytucjonalny
    siedzi pod ``mail`` — instalacje z odwrotną konwencją przestawiają
    kolejność env-em ``DJANGO_BPP_OIDC_<SKROT>_EMAIL_CLAIMS``.

    Przypisanie uczelni: konto dostaje ``accessible_uczelnie`` (M2M z PR #189)
    z uczelnią o ``skrot`` == skrótowi z konfiguracji OIDC. Ten sam skrót
    (np. ``UAFM``), który wybrał ``client_id``/``client_secret``, mapuje 1:1 na
    ``Uczelnia.skrot`` — dzięki czemu docelowe „3 backendy = 3 uczelnie" same
    przypisują właściwą uczelnię, bez dodatkowej konfiguracji.

    ⚠️ GATE PRZED PRODUKCJĄ (TODO): obecnie konto powstaje KAŻDEMU ważnemu
    userowi realmu — to świadoma decyzja fazy discovery, NIE wolno z tym wejść
    na produkcję. Zanim deployment produkcyjny: dodać jawny gate (rola/grupa,
    claim pracownik/student, domena e-mail albo inna polityka instytucji) w
    ``verify_claims``. Którego claimu użyć dowiemy się dopiero z realnych
    kluczy — dlatego gate'u nie da się sensownie dodać wcześniej.

    Możliwe rozszerzenia (poza zakresem MVP):
      * gating po rolach/grupach (``realm_access.roles``) w ``verify_claims``
        (to jest TEN gate produkcyjny — „kogo nie wpuszczamy");
      * „komu nie tworzymy konta" → warunek w ``create_user``;
      * mapowanie ról Keycloaka na grupy/uprawnienia → ``update_user``;
      * powiązanie z istniejącym ``Autor`` przez claim ``person_id`` →
        ``filter_users_by_claims``.
    """

    @staticmethod
    def _resolve_email_with_source(claims):
        """Ustal adres e-mail z claimów oraz czy padł na fallback username.

        Kolejność z ``_email_claim_keys()`` (default mail-first:
        ``mail`` → ``email`` → ``e-mail`` → ``e_mail``; pierwszy niepusty
        wygrywa). Gdy żaden nie niesie wartości, spada na
        ``preferred_username`` — ale tylko jeśli ten wygląda jak adres
        (zawiera domenę, np. UPN ``99999@student-afm.edu.pl``).

        Zwraca krotkę ``(email, from_fallback)``, gdzie ``from_fallback`` jest
        ``True``, gdy adres pochodzi z ``preferred_username`` (a nie z
        właściwego claimu e-mail) — taki adres NIGDY nie jest „zaufany"
        (``email_verified`` nie dotyczy loginu), więc anotacja trust go odsiewa.

        Gdy nie da się ustalić adresu (brak claimów e-mail, a
        ``preferred_username`` bez domeny), podnosi ``SuspiciousOperation``.
        To celowo — ``mozilla_django_oidc`` łapie ten wyjątek w
        ``authenticate`` (auth.py) i degraduje do *login failure* (zamiast
        500), a ``django.security`` loguje go na WARNING. Bez instytucjonalnego
        adresu nie chcemy zakładać/dopasowywać konta.
        """
        keys = _email_claim_keys()
        value = _first_claim(claims, keys)
        if value:
            return value, False

        username = claims.get("preferred_username") or ""
        if _EMAIL_SHAPE_RE.match(username):
            return username, True

        raise SuspiciousOperation(
            "OIDC: nie znaleziono adresu e-mail w claimach "
            f"({'/'.join(keys)}), a preferred_username={username!r} "
            "nie zawiera domeny — odrzucam logowanie."
        )

    @classmethod
    def _resolve_email(cls, claims):
        """Cienki wrapper (wsteczna zgodność) — sam adres, bez źródła."""
        return cls._resolve_email_with_source(claims)[0]

    @classmethod
    def _normalized(cls, claims):
        """Zwróć claimy z kanonicznym ``email`` + anotacją zaufania i ``iss``.

        ``mozilla-django-oidc`` (``verify_claims``/``filter_users_by_claims``/
        ``create_user``) czyta wyłącznie ``email``; realm bywa wystawia adres
        pod ``mail``/``e-mail``/``e_mail`` albo wcale (wtedy fallback na
        ``preferred_username`` z domeną). Zwraca **kopię** claimów z:

        * ``email`` — kanoniczny adres (patrz ``_resolve_email_with_source``),
        * ``email_verified`` — znormalizowany bool z payloadu/userinfo,
        * ``_bpp_email_trusted`` — czy adresowi wolno ufać przy fail-closed:
          ``email_verified is True`` ORAZ adres pochodzi z właściwego claimu
          (nie z fallbacku ``preferred_username``) ORAZ równa się poświadczonemu
          claimowi ``email`` (``email_verified`` dotyczy tego właśnie claimu),
        * ``iss`` — issuer bez końcowego ``/`` (do dopasowania po ``(iss, sub)``).
        """
        email, from_fallback = cls._resolve_email_with_source(claims)
        verified = bool(claims.get("email_verified") is True)
        payload_email = (claims.get("email") or "").lower()
        trusted = verified and not from_fallback and email.lower() == payload_email
        iss = (claims.get("iss") or "").rstrip("/")
        out = dict(claims)
        out["email"] = email
        out["email_verified"] = verified
        out["_bpp_email_trusted"] = trusted
        out["iss"] = iss
        return out

    def verify_token(self, token, **kwargs):
        """Waliduj podpis (bazowo) i dodatkowo issuer (``iss``) tokenu.

        Bazowy ``verify_token`` sprawdza podpis/nonce. Dokładamy twardą
        kontrolę ``iss`` względem ``OIDC_OP_ISSUER`` — token z innego realmu
        (nawet poprawnie podpisany przez ten sam serwer wielorealmowy) nie może
        zalogować do tej instancji. Bez skonfigurowanego issuera (instalacja
        bez OIDC) kontrola jest no-op.
        """
        payload = super().verify_token(token, **kwargs)
        expected = (getattr(settings, "OIDC_OP_ISSUER", "") or "").rstrip("/")
        got = (payload.get("iss") or "").rstrip("/")
        if expected and got != expected:
            raise SuspiciousOperation(f"OIDC: iss={got!r} != oczekiwany {expected!r}")
        return payload

    def get_userinfo(self, access_token, id_token, payload):
        # Jedyny chokepoint: znormalizuj claimy z userinfo, zanim trafią do
        # verify_claims / filter_users_by_claims / create_user. Domieszaj z
        # id_token (payload) klucze zaufania, których userinfo może nie mieć
        # (iss, email, email_verified pochodzą zwykle z id_token).
        claims = super().get_userinfo(access_token, id_token, payload)
        merged = dict(claims)
        for key in ("iss", "email", "email_verified"):
            if key not in merged and payload.get(key) is not None:
                merged[key] = payload.get(key)
        return self._normalized(merged)

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
        # Spróbuj powiązać autora (no-op jeśli już powiązany) — self-healing
        # dla kont założonych zanim doszło dopasowanie.
        user.sprobuj_dopasowac_autora()
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

        ``username`` z ``_username_claim_keys()`` (default
        ``preferred_username`` → ``email`` → ``sub``; pierwszy niepusty).
        Hasło ustawiane na nieużywalne — logowanie wyłącznie przez OIDC.
        Wywoływane tylko, gdy ``filter_users_by_claims`` (domyślnie po
        e-mailu) nie znajdzie istniejącego konta.
        """
        base_username = _first_claim(claims, _username_claim_keys())
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
        # Powiąż autora po przypisaniu uczelni — dopasowanie jest scope'owane
        # do accessible_uczelnie, więc kolejność ma znaczenie.
        user.sprobuj_dopasowac_autora()

        logger.info(
            "OIDC: utworzono konto username=%s email=%s (zwykłe, bez is_staff)",
            username,
            email,
        )
        return user
