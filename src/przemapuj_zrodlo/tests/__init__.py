import pytest
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def wprowadzanie_danych_group(db):
    """Fixture creating wprowadzanie danych group."""
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    return group


@pytest.fixture
def user_with_group(admin_user, wprowadzanie_danych_group):
    """Fixture creating admin user with wprowadzanie danych group."""
    admin_user.groups.add(wprowadzanie_danych_group)
    return admin_user


@pytest.fixture
def client_with_group(client, user_with_group):
    """Fixture creating authenticated client with user in wprowadzanie danych group."""
    client.force_login(user_with_group)
    return client


@pytest.fixture
def superuser_client(client, admin_user):
    """Fixture creating authenticated client with superuser (without any groups)."""
    admin_user.is_superuser = True
    admin_user.save()
    client.force_login(admin_user)
    return client
