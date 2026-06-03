"""Testy rozwiązywania konfiguracji OIDC ze zmiennych środowiskowych.

Czysty unit — bez bazy i bez sieci. Przekazujemy własny ``environ``.
"""

from oidc_integration.conf import discover_oidc_config

ISSUER = "https://auth.uafm.edu.pl/auth/realms/KA"


def test_brak_konfiguracji_zwraca_none():
    assert discover_oidc_config({}) is None


def test_niepelna_konfiguracja_zwraca_none():
    # brak CLIENT_SECRET
    env = {
        "DJANGO_BPP_OIDC_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_ISSUER": ISSUER,
    }
    assert discover_oidc_config(env) is None


def test_bare_konfiguracja():
    env = {
        "DJANGO_BPP_OIDC_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_ISSUER": ISSUER,
    }
    cfg = discover_oidc_config(env)
    assert cfg is not None
    assert cfg["client_id"] == "abc"
    assert cfg["client_secret"] == "sekret"
    assert cfg["skrot"] is None


def test_konfiguracja_z_prefiksem_skrotu():
    env = {
        "DJANGO_BPP_OIDC_UAFM_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_UAFM_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_UAFM_ISSUER": ISSUER,
    }
    cfg = discover_oidc_config(env)
    assert cfg is not None
    assert cfg["skrot"] == "UAFM"
    assert cfg["client_id"] == "abc"


def test_prefiks_ma_pierwszenstwo_nad_bare():
    env = {
        "DJANGO_BPP_OIDC_UAFM_CLIENT_ID": "specyficzny",
        "DJANGO_BPP_OIDC_UAFM_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_UAFM_ISSUER": ISSUER,
        "DJANGO_BPP_OIDC_CLIENT_ID": "generyczny",
    }
    cfg = discover_oidc_config(env)
    assert cfg["client_id"] == "specyficzny"


def test_dwa_skroty_nie_wykrywaja_jednego():
    # Niejednoznaczność: dwa komplety prefiksowane → skrot None, a wtedy
    # liczą się tylko wartości bare (których tu nie ma) → None.
    env = {
        "DJANGO_BPP_OIDC_UAFM_CLIENT_ID": "a",
        "DJANGO_BPP_OIDC_UAFM_CLIENT_SECRET": "s",
        "DJANGO_BPP_OIDC_UAFM_ISSUER": ISSUER,
        "DJANGO_BPP_OIDC_INNA_CLIENT_ID": "b",
        "DJANGO_BPP_OIDC_INNA_CLIENT_SECRET": "s2",
        "DJANGO_BPP_OIDC_INNA_ISSUER": ISSUER,
    }
    assert discover_oidc_config(env) is None


def test_endpointy_wyprowadzone_z_issuera():
    env = {
        "DJANGO_BPP_OIDC_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_ISSUER": ISSUER,
    }
    ep = discover_oidc_config(env)["endpoints"]
    base = ISSUER + "/protocol/openid-connect"
    assert ep["authorization"] == f"{base}/auth"
    assert ep["token"] == f"{base}/token"
    assert ep["userinfo"] == f"{base}/userinfo"
    assert ep["jwks"] == f"{base}/certs"
