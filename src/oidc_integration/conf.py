"""Odczyt konfiguracji OpenID Connect ze zmiennych środowiskowych.

Reguła rozwiązywania pojedynczego pola: najpierw wariant z prefiksem skrótu
uczelni ``DJANGO_BPP_OIDC_<SKROT>_<POLE>``, a gdy go brak — wariant bez
skrótu ``DJANGO_BPP_OIDC_<POLE>``. Wariant z prefiksem ma więc pierwszeństwo
(specyficzny > generyczny), bare jest fallbackiem.

Aktywny ``<SKROT>`` wykrywany jest automatycznie: jeśli w środowisku jest
dokładnie jeden komplet ``DJANGO_BPP_OIDC_<SKROT>_CLIENT_ID``, brany jest ten
skrót. Twarde wiązanie z ``Uczelnia.skrot`` z bazy — faza 2.

Moduł celowo NIE importuje Django (czytany jest z ``settings/base.py`` zanim
Django w pełni wstanie) — operuje wyłącznie na ``os.environ``.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

_PREFIX = "DJANGO_BPP_OIDC_"
_FIELDS = ("CLIENT_ID", "CLIENT_SECRET", "ISSUER")

# Domyślne źródła claimów (kolejność = preferencja, pierwszy niepusty wygrywa).
# E-mail: `mail` (instytucjonalny w realmach LDAP-owych) PRZED `email`
# (bywa prywatny). Realm UAFM dowiódł, że `email` to adres prywatny, a
# instytucjonalny siedzi pod `mail` — stąd mail-first jako default. Override:
# DJANGO_BPP_OIDC_<SKROT>_EMAIL_CLAIMS / DJANGO_BPP_OIDC_EMAIL_CLAIMS (CSV).
DEFAULT_EMAIL_CLAIMS = ("mail", "email", "e-mail", "e_mail")
DEFAULT_USERNAME_CLAIMS = ("preferred_username", "email", "sub")

# Mapowanie wewnętrznych nazw endpointów → kluczy w .well-known/openid-configuration
_WELL_KNOWN_KEYS = {
    "authorization": "authorization_endpoint",
    "token": "token_endpoint",
    "userinfo": "userinfo_endpoint",
    "jwks": "jwks_uri",
    "end_session": "end_session_endpoint",
}

# Skrót składa się z liter/cyfr (bez podkreślników), żeby nie kolidować z
# bare-wariantem DJANGO_BPP_OIDC_CLIENT_ID (gdzie "CLIENT" nie jest skrótem).
_SKROT_RE = re.compile(rf"^{re.escape(_PREFIX)}(?P<skrot>[A-Z0-9]+)_CLIENT_ID$")


def _detect_skrot(environ):
    """Zwróć skrót uczelni, jeśli w środowisku jest dokładnie jeden komplet
    ``DJANGO_BPP_OIDC_<SKROT>_CLIENT_ID``. Inaczej ``None`` (0 lub ≥2)."""
    skroty = {m.group("skrot") for key in environ if (m := _SKROT_RE.match(key))}
    if len(skroty) == 1:
        return next(iter(skroty))
    return None


def _get(environ, field, skrot):
    """Pobierz pojedyncze pole: prefiks-skrót > bare."""
    if skrot:
        value = environ.get(f"{_PREFIX}{skrot}_{field}")
        if value:
            return value
    return environ.get(f"{_PREFIX}{field}")


def _get_bool(environ, field, skrot, default):
    """Bool z env wg preferencji (skrot → bare → default).

    „1/true/yes/on" (case-insensitive) = True; „0/false/no/off" = False.
    """
    raw = _get(environ, field, skrot)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_claim_list(environ, field, skrot, default):
    """Rozwiąż listę claimów (CSV) wg precedencji prefiks-skrót > bare.

    Wartość env to nazwy claimów po przecinku (np. ``mail,email``); białe
    znaki obcinane, puste elementy pomijane. Brak/pusto → ``default``.
    Zwraca krotkę (kolejność = preferencja).
    """
    raw = _get(environ, field, skrot)
    if not raw:
        return tuple(default)
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or tuple(default)


def _keycloak_endpoints(issuer):
    """Wyprowadź endpointy z URL issuera konwencją Keycloaka.

    Używane jako **fallback**, gdy nie uda się pobrać
    ``.well-known/openid-configuration`` (patrz ``fetch_well_known_endpoints``).
    """
    base = issuer.rstrip("/") + "/protocol/openid-connect"
    return {
        "authorization": f"{base}/auth",
        "token": f"{base}/token",
        "userinfo": f"{base}/userinfo",
        "jwks": f"{base}/certs",
        "end_session": f"{base}/logout",
    }


def fetch_well_known_endpoints(issuer, timeout=3):
    """Pobierz endpointy z ``{issuer}/.well-known/openid-configuration``.

    Zwraca dict w wewnętrznych nazwach (jak ``_keycloak_endpoints``) albo
    ``None``, gdy fetch/parse się nie powiedzie. Krótki timeout i połknięcie
    błędu są celowe: serwer BPP nie może zawisnąć na starcie, gdy IdP jest
    nieosiągalny — wołający degraduje wtedy do konwencji.

    NIE wołane w testach env-resolution (te używają konwencji); sieć dotykana
    tylko z ``settings/base.py`` przy realnej konfiguracji.
    """
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        import requests

        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        doc = resp.json()
    except Exception as e:  # noqa: BLE001 — degradacja do konwencji jest OK
        logger.warning(
            "OIDC: nie udało się pobrać %s (%s) — używam konwencji Keycloaka",
            url,
            e,
        )
        return None

    endpoints = {}
    for internal, well_known in _WELL_KNOWN_KEYS.items():
        value = doc.get(well_known)
        if value:
            endpoints[internal] = value

    # Bez kluczowych endpointów discovery jest bezużyteczne — degraduj.
    if not all(k in endpoints for k in ("authorization", "token", "jwks")):
        logger.warning(
            "OIDC: %s nie zawiera kompletu endpointów — używam konwencji", url
        )
        return None

    return endpoints


def discover_oidc_config(environ=None):
    """Zwróć konfigurację OIDC albo ``None``, gdy nie skonfigurowano.

    Zwracany słownik: ``client_id``, ``client_secret``, ``issuer``, ``skrot``
    (może być ``None``), ``endpoints`` (dict z 4 adresami), ``email_claims`` i
    ``username_claims`` (krotki nazw claimów wg preferencji),
    ``require_email_verified`` (bool, default ``True``) oraz ``grace_bind``
    (bool, default ``False``). ``None`` oznacza brak kompletu — aplikacja OIDC
    ma się wtedy w ogóle nie aktywować.
    """
    environ = os.environ if environ is None else environ
    skrot = _detect_skrot(environ)

    config = {field.lower(): _get(environ, field, skrot) for field in _FIELDS}

    if not (config["client_id"] and config["client_secret"] and config["issuer"]):
        return None

    config["skrot"] = skrot
    config["endpoints"] = _keycloak_endpoints(config["issuer"])
    config["email_claims"] = _get_claim_list(
        environ, "EMAIL_CLAIMS", skrot, DEFAULT_EMAIL_CLAIMS
    )
    config["username_claims"] = _get_claim_list(
        environ, "USERNAME_CLAIMS", skrot, DEFAULT_USERNAME_CLAIMS
    )
    config["require_email_verified"] = _get_bool(
        environ, "REQUIRE_EMAIL_VERIFIED", skrot, default=True
    )
    config["grace_bind"] = _get_bool(environ, "GRACE_BIND", skrot, default=False)
    return config
