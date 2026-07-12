import logging
import os
import re

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, transaction
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from oidc_integration.conf import DEFAULT_EMAIL_CLAIMS, DEFAULT_USERNAME_CLAIMS
from oidc_integration.models import OIDCIdentity

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

    @staticmethod
    def _clear_link_session(session):
        session.pop("oidc_link_mode", None)
        session.pop("oidc_link_target", None)
        session.save()

    def get_or_create_user(self, access_token, id_token, payload):
        """W trybie link (sesja) zwiąż ``sub`` z zalogowanym kontem i zwróć je.

        Standardowy callback ``/oidc/callback/`` jest reużyty do linkowania:
        widok ``SSOLinkInitView`` po re-auth hasłem ustawia w sesji
        ``oidc_link_mode``/``oidc_link_target`` i kieruje na init OIDC. Po
        powrocie z IdP jesteśmy tutaj z aktywną sesją zalogowanego usera —
        wiążemy jego konto z ``(issuer, sub)`` z tokenu i **pomijamy** zwykły
        tor filter/create (a więc i fail-closed po e-mailu: własny adres
        kolidowałby z samym sobą). Poza trybem link — bez zmian (``super``).
        """
        session = getattr(getattr(self, "request", None), "session", None)
        if session is not None and session.get("oidc_link_mode"):
            user_info = self.get_userinfo(access_token, id_token, payload)
            target_pk = session.get("oidc_link_target")
            request_user = getattr(self.request, "user", None)
            if not target_pk or request_user is None or request_user.pk != target_pk:
                self._clear_link_session(session)
                raise SuspiciousOperation("OIDC: cel linkowania niezgodny")
            issuer = user_info.get("iss") or ""
            sub = user_info.get("sub") or ""
            if not issuer or not sub:
                self._clear_link_session(session)
                raise SuspiciousOperation("OIDC: brak (issuer, sub) do związania")
            try:
                with transaction.atomic():
                    identity, created = OIDCIdentity.objects.get_or_create(
                        issuer=issuer,
                        sub=sub,
                        defaults={"user": request_user},
                    )
            except IntegrityError:
                # (user, issuer) już zajęte innym sub — konto ma już tożsamość
                # z tego realmu (jeden realm = jedno konto).
                self._clear_link_session(session)
                raise SuspiciousOperation(
                    "OIDC: to konto ma już powiązaną tożsamość z tego realmu"
                ) from None
            if not created and identity.user_id != request_user.pk:
                # Ta (issuer, sub) należy do innego konta — NIE przejmujemy jej.
                self._clear_link_session(session)
                raise SuspiciousOperation(
                    "OIDC: ta tożsamość SSO jest już powiązana z innym kontem"
                )
            self._clear_link_session(session)
            return request_user
        return super().get_or_create_user(access_token, id_token, payload)

    def verify_claims(self, claims):
        _log_claims_debug(claims)
        return super().verify_claims(claims)

    def filter_users_by_claims(self, claims):
        """Dopasuj konto WYŁĄCZNIE po powiązanym ``(issuer, sub)``.

        Bazowa implementacja dopasowuje po e-mailu — co pozwala przejąć konto
        przez wpisanie cudzego adresu w realmie. Tu wiążemy tożsamość po
        niezmiennym ``sub`` w obrębie danego ``issuer``: brak wpisu
        ``OIDCIdentity`` → brak dopasowania (konto powstanie lub trzeba je
        świadomie połączyć). Brak ``sub``/``iss`` → pusty queryset.
        """
        sub = claims.get("sub")
        issuer = claims.get("iss")
        if not sub or not issuer:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(
            oidc_identities__issuer=issuer,
            oidc_identities__sub=sub,
        )

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
        # dla kont założonych zanim doszło dopasowanie. Dopasowanie po e-mailu/
        # nazwiskach TYLKO gdy claim jest zaufany (``email_verified`` + zgodny
        # adres), inaczej ktoś mógłby przez niezweryfikowany claim „podpiąć się"
        # pod cudzego Autora.
        trusted = bool(claims.get("_bpp_email_trusted"))
        user.sprobuj_dopasowac_autora(match_email=trusted, match_names=trusted)
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

    def _try_grace_bind(self, claims):
        """Opt-in związanie starego konta czysto-OIDC po zaufanym e-mailu.

        Migracja istniejących kont sprzed wiązania po ``(issuer, sub)``: jeśli
        instalacja włączy ``OIDC_GRACE_BIND_ENABLED``, konto dopasowane po
        adresie może zostać JEDNORAZOWO związane z ``sub`` — ale tylko gdy jest
        „czysto-OIDC" i niskiego ryzyka:

        * ``_bpp_email_trusted`` (email_verified + zgodny adres),
        * dokładnie jedno konto z tym adresem,
        * bez ``is_staff``/``is_superuser``, aktywne,
        * bez używalnego hasła lokalnego (logowanie tylko przez OIDC),
        * bez grup, uprawnień indywidualnych, tokenu PBN,
        * bez żadnej istniejącej tożsamości OIDC (także z innego realmu).

        Każdy z tych warunków chroni przed przejęciem konta o realnych
        uprawnieniach. Zwraca związane konto albo ``None`` (→ normalny tor
        create_user / fail-closed). Domyślnie wyłączone.
        """
        if not getattr(settings, "OIDC_GRACE_BIND_ENABLED", False):
            return None
        if not claims.get("_bpp_email_trusted"):
            return None
        email = claims.get("email") or ""
        issuer = claims.get("iss") or ""
        sub = claims.get("sub") or ""
        if not email:
            return None
        qs = self.UserModel.objects.filter(email__iexact=email)
        if qs.count() != 1:
            return None
        user = qs.first()
        eligible = (
            not user.is_staff
            and not user.is_superuser
            and user.is_active
            and not user.has_usable_password()
            and not user.groups.exists()
            and not user.user_permissions.exists()
            and not (user.pbn_token or "")
            and not user.oidc_identities.exists()
        )
        if not eligible:
            return None
        try:
            with transaction.atomic():
                OIDCIdentity.objects.create(user=user, issuer=issuer, sub=sub)
        except IntegrityError:
            # Równoległe logowanie zdążyło związać ten (issuer, sub).
            existing = OIDCIdentity.objects.filter(issuer=issuer, sub=sub).first()
            return existing.user if existing else None
        logger.info("OIDC: grace-bind sub dla konta %s", user.username)
        return user

    def create_user(self, claims):
        """Załóż zwykłe konto (bez is_staff) i zwiąż je z ``(issuer, sub)``.

        Fail-closed: gdy istnieje już konto z tym adresem e-mail, NIE zakładamy
        drugiego (i nie „przejmujemy" istniejącego) — trzeba je świadomie
        połączyć z SSO przez profil (re-auth hasłem). Gdy
        ``OIDC_REQUIRE_EMAIL_VERIFIED``, wymagamy zaufanego adresu
        (``_bpp_email_trusted``). Tworzenie konta i wpisu ``OIDCIdentity`` jest
        atomowe; kolizja ``(issuer, sub)`` (wyścig równoległych logowań) zwraca
        wcześniej związane konto zamiast błędu.
        """
        email = claims.get("email") or ""
        issuer = claims.get("iss") or ""
        sub = claims.get("sub") or ""

        graced = self._try_grace_bind(claims)
        if graced is not None:
            return graced

        if email and self.UserModel.objects.filter(email__iexact=email).exists():
            raise SuspiciousOperation(
                "OIDC: konto z tym adresem już istnieje — połącz je z SSO "
                "przez profil (re-auth hasłem), nie tworzę konta."
            )

        require = getattr(settings, "OIDC_REQUIRE_EMAIL_VERIFIED", True)
        if require and not claims.get("_bpp_email_trusted"):
            raise SuspiciousOperation(
                "OIDC: e-mail niezweryfikowany (email_verified) — "
                "odrzucam założenie konta."
            )

        base_username = _first_claim(claims, _username_claim_keys())
        trusted = bool(claims.get("_bpp_email_trusted"))

        for _ in range(5):  # retry na wyścig o username
            username = self._unique_username(base_username)
            try:
                with transaction.atomic():
                    user = self.UserModel.objects.create_user(
                        username=username, email=email
                    )
                    user.first_name = claims.get("given_name") or ""
                    user.last_name = claims.get("family_name") or ""
                    user.is_staff = False
                    user.is_superuser = False
                    user.is_active = True
                    user.set_unusable_password()
                    user.save()
                    with transaction.atomic():  # savepoint na wpis tożsamości
                        OIDCIdentity.objects.create(user=user, issuer=issuer, sub=sub)
                break
            except IntegrityError:
                # albo username zajęty (retry), albo (issuer, sub) zajęte przez
                # równoległe logowanie tego samego usera → zwróć jego konto.
                existing = OIDCIdentity.objects.filter(issuer=issuer, sub=sub).first()
                if existing is not None:
                    return existing.user
                continue
        else:
            raise SuspiciousOperation("OIDC: nie udało się utworzyć konta")

        self._assign_uczelnia(user)
        # Powiąż autora po przypisaniu uczelni — dopasowanie jest scope'owane
        # do accessible_uczelnie. Po e-mailu/nazwiskach tylko dla zaufanego
        # claimu (inaczej niezweryfikowany adres mógłby podpiąć cudzego Autora).
        user.sprobuj_dopasowac_autora(match_email=trusted, match_names=trusted)

        logger.info(
            "OIDC: utworzono konto username=%s (bez is_staff), sub związany",
            username,
        )
        return user
