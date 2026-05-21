import pytest
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def wprowadzanie_danych_group(db):
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    return group


@pytest.fixture
def client_with_group(client, admin_user, wprowadzanie_danych_group):
    admin_user.groups.add(wprowadzanie_danych_group)
    client.force_login(admin_user)
    return client
