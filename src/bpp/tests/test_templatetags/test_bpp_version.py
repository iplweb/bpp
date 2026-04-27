from bpp.templatetags.bpp_version import bpp_git_sha_short


def test_bpp_git_sha_short_zwraca_pusty_gdy_brak_env(monkeypatch):
    monkeypatch.delenv("BPP_GIT_SHA", raising=False)
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_git_sha_short() == ""


def test_bpp_git_sha_short_zwraca_pusty_gdy_unknown(monkeypatch):
    monkeypatch.setenv("BPP_GIT_SHA", "unknown")
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_git_sha_short() == ""


def test_bpp_git_sha_short_zwraca_pusty_dla_release(monkeypatch):
    monkeypatch.setenv("BPP_GIT_SHA", "abc1234567890def")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "release")
    assert bpp_git_sha_short() == ""


def test_bpp_git_sha_short_zwraca_pierwsze_7_znakow_dla_dev(monkeypatch):
    monkeypatch.setenv("BPP_GIT_SHA", "abc1234567890def")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "dev")
    assert bpp_git_sha_short() == "abc1234"


def test_bpp_git_sha_short_default_flavor_dev(monkeypatch):
    """Brak BPP_BUILD_FLAVOR zachowuje się jak dev (pokazuj SHA)."""
    monkeypatch.setenv("BPP_GIT_SHA", "0123456789abcdef")
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_git_sha_short() == "0123456"
