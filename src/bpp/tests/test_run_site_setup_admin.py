"""Testy komendy runsite_setup_admin."""

import os

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.fixture
def superuser_env(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")


@pytest.mark.django_db
def test_creates_admin_when_missing(superuser_env):
    User = get_user_model()
    assert not User.objects.filter(username="admin").exists()
    call_command("runsite_setup_admin")
    user = User.objects.get(username="admin")
    assert user.is_superuser
    assert user.is_staff
    assert user.is_active
    assert user.check_password("admin")


@pytest.mark.django_db
def test_overwrites_password_and_flags_when_exists(superuser_env):
    """Gdy admin już istnieje (np. po restore dump-a) — hasło i flagi nadpisane."""
    User = get_user_model()
    existing = User.objects.create_user(
        username="admin",
        password="old-secret",
        email="old@example.com",
        is_active=False,
        is_staff=False,
        is_superuser=False,
    )
    call_command("runsite_setup_admin")
    existing.refresh_from_db()
    assert existing.is_superuser
    assert existing.is_staff
    assert existing.is_active
    assert existing.check_password("admin")
    assert not existing.check_password("old-secret")
    assert existing.email == "admin@example.com"


@pytest.mark.django_db
def test_clears_password_change_required(superuser_env):
    """PasswordChangeRequired dla admina jest skasowane → brak propozycji zmiany hasła."""
    User = get_user_model()
    user = User.objects.create_user(username="admin", password="x")

    try:
        from password_policies.models import PasswordChangeRequired
    except ImportError:
        pytest.skip("password_policies nie zainstalowane")

    PasswordChangeRequired.objects.create(user=user)
    assert PasswordChangeRequired.objects.filter(user=user).exists()

    call_command("runsite_setup_admin")

    assert not PasswordChangeRequired.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_adds_fresh_password_history_entry(superuser_env):
    """Świeży PasswordHistory zapobiega wymuszeniu zmiany przez middleware."""
    User = get_user_model()
    User.objects.create_user(username="admin", password="x")

    try:
        from password_policies.models import PasswordHistory
    except ImportError:
        pytest.skip("password_policies nie zainstalowane")

    # Przed komendą: brak wpisów PasswordHistory dla admina
    user = User.objects.get(username="admin")
    assert not PasswordHistory.objects.filter(user=user).exists()

    call_command("runsite_setup_admin")

    user.refresh_from_db()
    entries = PasswordHistory.objects.filter(user=user)
    assert entries.count() == 1
    # newest jest świeży (młodszy niż 1 minuta)
    from django.utils import timezone
    from datetime import timedelta

    newest = entries.latest("created")
    assert (timezone.now() - newest.created) < timedelta(minutes=1)
    # password to faktyczny hash (zaczyna się od pbkdf2 / argon2 / etc.)
    assert "$" in newest.password


@pytest.mark.django_db
def test_uses_default_credentials_when_env_missing(monkeypatch):
    """Bez env vars używa default admin/admin/admin@example.com."""
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_EMAIL", raising=False)

    User = get_user_model()
    call_command("runsite_setup_admin")
    user = User.objects.get(username="admin")
    assert user.check_password("admin")
    assert user.email == "admin@example.com"


_ = os  # silence unused import warning if not needed
