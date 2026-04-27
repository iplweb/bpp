from bpp.templatetags.bpp_version import (
    bpp_branch_tag,
    bpp_git_sha_short,
    bpp_image_tag,
)


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


def test_bpp_image_tag_zwraca_pusty_gdy_brak_env(monkeypatch):
    monkeypatch.delenv("BPP_IMAGE_TAG", raising=False)
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_image_tag() == ""


def test_bpp_image_tag_zwraca_pusty_gdy_unknown(monkeypatch):
    monkeypatch.setenv("BPP_IMAGE_TAG", "unknown")
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_image_tag() == ""


def test_bpp_image_tag_zwraca_pusty_dla_release(monkeypatch):
    monkeypatch.setenv("BPP_IMAGE_TAG", "119-merge")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "release")
    assert bpp_image_tag() == ""


def test_bpp_image_tag_zwraca_tag_dla_dev(monkeypatch):
    monkeypatch.setenv("BPP_IMAGE_TAG", "119-merge")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "dev")
    assert bpp_image_tag() == "119-merge"


def test_bpp_image_tag_zachowuje_pelny_tag_brancha(monkeypatch):
    """Branch builds mają tag = nazwa brancha (sanitized) — bez skracania."""
    monkeypatch.setenv("BPP_IMAGE_TAG", "feature-nowe-zglos-publikacje")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "dev")
    assert bpp_image_tag() == "feature-nowe-zglos-publikacje"


def test_bpp_branch_tag_zwraca_pusty_gdy_brak_env(monkeypatch):
    monkeypatch.delenv("BPP_BRANCH_TAG", raising=False)
    monkeypatch.delenv("BPP_BUILD_FLAVOR", raising=False)
    assert bpp_branch_tag() == ""


def test_bpp_branch_tag_zwraca_pusty_dla_release(monkeypatch):
    monkeypatch.setenv("BPP_BRANCH_TAG", "feature-foo")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "release")
    assert bpp_branch_tag() == ""


def test_bpp_branch_tag_zwraca_alias_dla_dev(monkeypatch):
    monkeypatch.setenv("BPP_BRANCH_TAG", "feature-nowe-zglos-publikacje")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "dev")
    assert bpp_branch_tag() == "feature-nowe-zglos-publikacje"


def test_bpp_branch_tag_pusty_string_traktowany_jak_brak(monkeypatch):
    """Workflow przekazuje empty string dla master/non-PR — nie pokazuj."""
    monkeypatch.setenv("BPP_BRANCH_TAG", "")
    monkeypatch.setenv("BPP_BUILD_FLAVOR", "dev")
    assert bpp_branch_tag() == ""
