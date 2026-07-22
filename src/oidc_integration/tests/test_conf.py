"""Testy rozwiązywania konfiguracji OIDC ze zmiennych środowiskowych.

Czysty unit — bez bazy i bez sieci. Przekazujemy własny ``environ``.
"""

from oidc_integration.conf import (
    _get_bool,
    discover_oidc_config,
    fetch_well_known_endpoints,
)

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
    assert ep["end_session"] == f"{base}/logout"


def _bare_env():
    return {
        "DJANGO_BPP_OIDC_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_ISSUER": ISSUER,
    }


def test_email_claims_default_mail_first():
    # Bez konfiguracji: domyślnie `mail` ma pierwszeństwo (instytucjonalny),
    # `email` (prywatny) jest fallbackiem.
    cfg = discover_oidc_config(_bare_env())
    assert cfg["email_claims"] == ("mail", "email", "e-mail", "e_mail")


def test_username_claims_default():
    cfg = discover_oidc_config(_bare_env())
    assert cfg["username_claims"] == ("preferred_username", "email", "sub")


def test_email_claims_z_env_csv():
    env = _bare_env()
    env["DJANGO_BPP_OIDC_EMAIL_CLAIMS"] = "email, mail"
    cfg = discover_oidc_config(env)
    assert cfg["email_claims"] == ("email", "mail")


def test_email_claims_prefiks_ma_pierwszenstwo_nad_bare():
    env = {
        "DJANGO_BPP_OIDC_UAFM_CLIENT_ID": "abc",
        "DJANGO_BPP_OIDC_UAFM_CLIENT_SECRET": "sekret",
        "DJANGO_BPP_OIDC_UAFM_ISSUER": ISSUER,
        "DJANGO_BPP_OIDC_UAFM_EMAIL_CLAIMS": "mail",
        "DJANGO_BPP_OIDC_EMAIL_CLAIMS": "email",
    }
    cfg = discover_oidc_config(env)
    assert cfg["email_claims"] == ("mail",)


def test_username_claims_z_env_csv():
    env = _bare_env()
    env["DJANGO_BPP_OIDC_USERNAME_CLAIMS"] = "sub,preferred_username"
    cfg = discover_oidc_config(env)
    assert cfg["username_claims"] == ("sub", "preferred_username")


def test_fetch_well_known_fallback_na_bledzie_sieci(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise requests.RequestException("brak sieci")

    monkeypatch.setattr("requests.get", boom)
    assert fetch_well_known_endpoints(ISSUER) is None


def test_fetch_well_known_parsuje_endpointy(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "authorization_endpoint": "https://kc/auth",
                "token_endpoint": "https://kc/token",
                "userinfo_endpoint": "https://kc/userinfo",
                "jwks_uri": "https://kc/certs",
                "end_session_endpoint": "https://kc/logout",
            }

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    ep = fetch_well_known_endpoints(ISSUER)
    assert ep == {
        "authorization": "https://kc/auth",
        "token": "https://kc/token",
        "userinfo": "https://kc/userinfo",
        "jwks": "https://kc/certs",
        "end_session": "https://kc/logout",
    }


def test_fetch_well_known_niekompletny_to_none(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"userinfo_endpoint": "https://kc/userinfo"}  # brak auth/token/jwks

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    assert fetch_well_known_endpoints(ISSUER) is None


def test_get_bool_prefers_skrot_variant():
    env = {
        "DJANGO_BPP_OIDC_UAFM_GRACE_BIND": "1",
        "DJANGO_BPP_OIDC_GRACE_BIND": "0",
    }
    assert _get_bool(env, "GRACE_BIND", "UAFM", default=False) is True


def test_get_bool_default_when_absent():
    assert _get_bool({}, "REQUIRE_EMAIL_VERIFIED", None, default=True) is True
