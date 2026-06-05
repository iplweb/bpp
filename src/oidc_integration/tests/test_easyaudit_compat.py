"""Testy guarda kompatybilności z django-easy-audit.

easyaudit zapisuje nieudane logowania robiąc twardo
``credentials[USERNAME_FIELD]``. Backendy OAuth (OIDC/Microsoft) wołają
``auth.authenticate()`` bez ``username`` w credentials — bez guarda handler
rzuca ``KeyError`` (a przy ``PROPAGATE_EXCEPTIONS=True`` → HTTP 500).
"""

from oidc_integration import easyaudit_compat


def test_ensure_username_dorabia_z_preferred_username():
    out = easyaudit_compat._ensure_username(
        {"nonce": "x", "preferred_username": "jkowalski@uafm.edu.pl"}
    )
    assert out["username"] == "jkowalski@uafm.edu.pl"
    # oryginalne klucze zachowane
    assert out["nonce"] == "x"


def test_ensure_username_pusty_gdy_brak_preferred_username():
    # Realny przypadek OIDC: credentials = {nonce, code_verifier}.
    out = easyaudit_compat._ensure_username({"nonce": "x", "code_verifier": "y"})
    assert out["username"] == ""


def test_ensure_username_nie_rusza_gdy_username_jest():
    src = {"username": "admin", "password": "tajne"}
    out = easyaudit_compat._ensure_username(src)
    # bez zmian — formularzowe logowanie ma już username
    assert out is src


def test_guard_dokłada_username_i_deleguje_do_oryginalu():
    captured = {}

    def fake_original(sender, credentials, **kwargs):
        captured["sender"] = sender
        captured["credentials"] = credentials

    guard = easyaudit_compat._make_guard(fake_original)
    guard(
        sender="bpp",
        credentials={"nonce": "x", "preferred_username": "u@uafm.edu.pl"},
    )

    assert captured["sender"] == "bpp"
    assert captured["credentials"]["username"] == "u@uafm.edu.pl"


def test_install_zwraca_callable_i_nie_wybucha():
    # easyaudit jest zależnością (w venv), więc import auth_signals działa
    # niezależnie od tego, czy easyaudit jest w INSTALLED_APPS.
    guard = easyaudit_compat.install_easyaudit_login_failed_guard()
    assert callable(guard)
