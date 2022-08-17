import pytest

from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH, GR_ZGLOSZENIA_PUBLIKACJI
from bpp.core import editors_emails, zgloszenia_publikacji_emails
from bpp.models import BppUser


@pytest.mark.django_db
def test_editors_emails(admin_user: BppUser):
    ADMIN_EMAIL = "foo@bar.pl"

    g = Group.objects.get(name=GR_WPROWADZANIE_DANYCH)
    admin_user.email = ADMIN_EMAIL
    admin_user.save()

    admin_user.groups.add(g)

    assert ADMIN_EMAIL in editors_emails()


@pytest.mark.django_db
def test_zgloszenia_publikacji_emails(admin_user: BppUser, normal_django_user: BppUser):
    ADMIN_EMAIL = "foo@bar.pl"
    USER_EMAIL = "user@bar.pl"

    g = Group.objects.get(name=GR_WPROWADZANIE_DANYCH)
    admin_user.email = ADMIN_EMAIL
    admin_user.save()

    admin_user.groups.add(g)

    assert ADMIN_EMAIL in zgloszenia_publikacji_emails()

    g = Group.objects.get(name=GR_ZGLOSZENIA_PUBLIKACJI)
    normal_django_user.email = USER_EMAIL
    normal_django_user.save()

    normal_django_user.groups.add(g)
    assert ADMIN_EMAIL not in zgloszenia_publikacji_emails()
    assert USER_EMAIL in zgloszenia_publikacji_emails()
