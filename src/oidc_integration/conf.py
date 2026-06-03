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

import os
import re

_PREFIX = "DJANGO_BPP_OIDC_"
_FIELDS = ("CLIENT_ID", "CLIENT_SECRET", "ISSUER")

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


def _keycloak_endpoints(issuer):
    """Wyprowadź 4 endpointy z URL issuera konwencją Keycloaka.

    Faza 2: zamienić na fetch ``.well-known/openid-configuration`` z cache.
    """
    base = issuer.rstrip("/") + "/protocol/openid-connect"
    return {
        "authorization": f"{base}/auth",
        "token": f"{base}/token",
        "userinfo": f"{base}/userinfo",
        "jwks": f"{base}/certs",
    }


def discover_oidc_config(environ=None):
    """Zwróć konfigurację OIDC albo ``None``, gdy nie skonfigurowano.

    Zwracany słownik: ``client_id``, ``client_secret``, ``issuer``, ``skrot``
    (może być ``None``), ``endpoints`` (dict z 4 adresami). ``None`` oznacza
    brak kompletu — aplikacja OIDC ma się wtedy w ogóle nie aktywować.
    """
    environ = os.environ if environ is None else environ
    skrot = _detect_skrot(environ)

    config = {field.lower(): _get(environ, field, skrot) for field in _FIELDS}

    if not (config["client_id"] and config["client_secret"] and config["issuer"]):
        return None

    config["skrot"] = skrot
    config["endpoints"] = _keycloak_endpoints(config["issuer"])
    return config
