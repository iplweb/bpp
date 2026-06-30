"""
Verify seed_demo idempotency by exercising the same get_or_create logic
directly (without depending on the example Django project settings).
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_seed_demo_get_or_create_idempotent(db):
    """Running seed_demo logic twice produces exactly one user."""
    username = "demo_seed_test"
    email = "demo@example.com"

    def seed():
        user, created = User.objects.get_or_create(
            **{User.USERNAME_FIELD: username},
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password("demo")
            user.save(update_fields=["password"])
        return created

    first = seed()
    second = seed()

    assert first is True
    assert second is False
    assert User.objects.filter(**{User.USERNAME_FIELD: username}).count() == 1


@pytest.mark.django_db
def test_seed_demo_user_is_superuser(db):
    """Seeded user is a superuser and can authenticate."""
    username = "demo_super_test"
    user, _ = User.objects.get_or_create(
        **{User.USERNAME_FIELD: username},
        defaults={"email": "x@x.com", "is_staff": True, "is_superuser": True},
    )
    user.set_password("demo")
    user.save(update_fields=["password"])

    fresh = User.objects.get(**{User.USERNAME_FIELD: username})
    assert fresh.is_superuser
    assert fresh.check_password("demo")
