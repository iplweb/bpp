import pytest

from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.core import editors_emails
from bpp.models import BppUser


@pytest.mark.django_db
def test_editors_emails(admin_user: BppUser):
    ADMIN_EMAIL = "foo@bar.pl"

    g = Group.objects.get(name=GR_WPROWADZANIE_DANYCH)
    admin_user.email = ADMIN_EMAIL
    admin_user.save()

    admin_user.groups.add(g)

    assert ADMIN_EMAIL in editors_emails()
